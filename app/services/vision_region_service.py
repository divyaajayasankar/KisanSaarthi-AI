"""Affected-region estimate for a photo diagnosis (Grad-CAM).

Shows WHERE the validated crop model looked when it named the disease: the
most strongly activated area of the last convolutional block for the predicted
class. It is a model-attention map, not a measured lesion area and not a
segmentation. Wording in the chat reply says so.

Never raises into the chat flow: any failure returns None and the reply simply
omits the region line. Needs PyTorch and a validated model for the crop.
"""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from app.services import vision_inference_service as vis

GRID_NAMES = [
    ["upper_left", "upper_center", "upper_right"],
    ["middle_left", "center", "middle_right"],
    ["lower_left", "lower_center", "lower_right"],
]
THRESHOLD = 0.5  # share of the peak activation that counts as "affected"


def describe_position(x_frac: float, y_frac: float) -> str:
    """Nine-cell grid name for a point given as fractions of the image width and height."""
    col = min(2, max(0, int(x_frac * 3)))
    row = min(2, max(0, int(y_frac * 3)))
    return GRID_NAMES[row][col]


def region_from_cam(cam: list[list[float]], crop_box: tuple[float, float, float, float]) -> dict[str, Any] | None:
    """Turn a normalised class-activation grid into a region description.

    cam: rows of values in [0, 1] covering the model's view of the image.
    crop_box: (left, top, right, bottom) of that view as fractions of the original photo.
    """
    rows, cols = len(cam), len(cam[0]) if cam else 0
    if not rows or not cols:
        return None
    peak = max(max(row) for row in cam)
    if peak <= 0:
        return None
    left, top, right, bottom = crop_box
    hot = [(r, c) for r in range(rows) for c in range(cols) if cam[r][c] >= THRESHOLD * peak]
    weight_sum = sum(cam[r][c] for r, c in hot)
    cy = sum((r + 0.5) * cam[r][c] for r, c in hot) / weight_sum / rows
    cx = sum((c + 0.5) * cam[r][c] for r, c in hot) / weight_sum / cols
    x_frac = left + cx * (right - left)
    y_frac = top + cy * (bottom - top)
    rmin, rmax = min(r for r, _ in hot), max(r for r, _ in hot)
    cmin, cmax = min(c for _, c in hot), max(c for _, c in hot)
    box = [
        round(left + cmin / cols * (right - left), 3),
        round(top + rmin / rows * (bottom - top), 3),
        round(left + (cmax + 1) / cols * (right - left), 3),
        round(top + (rmax + 1) / rows * (bottom - top), 3),
    ]
    return {
        "position": describe_position(x_frac, y_frac),
        "center": [round(x_frac, 3), round(y_frac, 3)],
        "box": box,
        "share_of_view_percent": round(100 * len(hot) / (rows * cols)),
        "method": "grad-cam (model attention, not a measured lesion area)",
    }


@lru_cache(maxsize=8)
def _load(crop: str, path: str, mtime: float):
    import torch

    entry = vis.registry_entry(crop)
    checkpoint = torch.load(vis.PROJECT_ROOT / path, map_location="cpu", weights_only=True)
    model = vis.build_model(entry["architecture"], len(entry["labels"]))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, vis.eval_transform(int(entry.get("input_size", 224))), entry


def _view_box(width: int, height: int, input_size: int) -> tuple[float, float, float, float]:
    """The part of the photo the model sees: resize short side to 1.14 x input, then centre crop."""
    short = min(width, height)
    visible = input_size / int(input_size * 1.14) * short  # side of the centre square, in original pixels
    left = (width - visible) / 2 / width
    top = (height - visible) / 2 / height
    return left, top, 1 - left, 1 - top


def compute_cam(model, tensor, class_index: int) -> list[list[float]]:
    import torch

    store: dict[str, Any] = {}
    layer = model.features[-1]

    def forward_hook(_module, _inputs, output):
        store["act"] = output
        output.register_hook(lambda grad: store.__setitem__("grad", grad))

    handle = layer.register_forward_hook(forward_hook)
    try:
        model.zero_grad()
        with torch.enable_grad():
            logits = model(tensor.requires_grad_(True))
            logits[0, class_index].backward()
    finally:
        handle.remove()
    act, grad = store["act"][0].detach(), store["grad"][0].detach()
    weights = grad.mean(dim=(1, 2), keepdim=True)
    cam = torch.relu((weights * act).sum(dim=0))
    top = float(cam.max())
    if top <= 0:
        return [[0.0]]
    return (cam / top).tolist()


def locate_affected_region(crop: str | None, image_bytes: bytes, label: str, overlay_dir: Path | None = None) -> dict[str, Any] | None:
    try:
        crop_key = (crop or "").strip().lower()
        entry = vis.registry_entry(crop_key)
        if entry is None or not vis.torch_available() or label not in entry["labels"]:
            return None
        path = entry["path"]
        model, transform, entry = _load(crop_key, path, (vis.PROJECT_ROOT / path).stat().st_mtime)
        with Image.open(BytesIO(image_bytes)) as photo:
            rgb = photo.convert("RGB")
            tensor = transform(rgb).unsqueeze(0)
            cam = compute_cam(model, tensor, entry["labels"].index(label))
            region = region_from_cam(cam, _view_box(rgb.width, rgb.height, int(entry.get("input_size", 224))))
            if region is not None and overlay_dir is not None:
                region["overlay"] = _save_overlay(rgb, cam, region, overlay_dir)
        return region
    except Exception:
        return None


def _save_overlay(photo: Image.Image, cam: list[list[float]], region: dict[str, Any], folder: Path) -> str | None:
    try:
        import numpy as np
        from PIL import ImageDraw

        folder.mkdir(parents=True, exist_ok=True)
        grid = np.array(cam, dtype=float)
        heat = Image.fromarray((grid * 255).astype("uint8")).resize(photo.size, Image.BILINEAR)
        red = Image.new("RGB", photo.size, (220, 40, 30))
        blended = Image.composite(red, photo, heat.point(lambda v: int(v * 0.55)))
        draw = ImageDraw.Draw(blended)
        w, h = photo.size
        x0, y0, x1, y1 = region["box"]
        draw.rectangle([x0 * w, y0 * h, x1 * w, y1 * h], outline=(255, 255, 0), width=max(2, w // 120))
        target = folder / "affected_region.png"
        blended.save(target)
        return str(target)
    except Exception:
        return None
