"""Vision/Disease Agent: crop-aware image diagnosis with a model registry.

    image -> quality validation -> crop -> crop model registry
          -> validated model? inference + calibrated confidence
          -> no validated model? ABSTAIN on image (no diagnosis claimed)

data/models/model_registry.json lists one MobileNetV3 classifier per crop.
An entry is used only when "validated": true, which scripts/train_crop_model.py
sets only if the held-out macro-F1 reaches the configured minimum.
Confidence is softmax(logits / temperature); the temperature is fitted
on the validation split during training (temperature scaling).

PyTorch is optional. Without it, or without a validated model for the
crop, analyze() returns model_supported=False and the decision
controller abstains on the image.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from app.services.decision_controller import decide_vision


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "data" / "models"
REGISTRY_FILE = MODEL_DIR / "model_registry.json"

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


@dataclass
class VisionResult:
    crop: str | None
    model_supported: bool
    prediction: str | None = None
    confidence: float | None = None
    top_k: list[dict[str, Any]] = field(default_factory=list)
    decision: str = "ABSTAIN"
    reason: str = ""
    model: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def torch_available() -> bool:
    try:
        import torch  # noqa: F401
        import torchvision  # noqa: F401
    except Exception:
        return False
    return True


def load_registry() -> dict[str, Any]:
    if not REGISTRY_FILE.exists():
        return {"models": {}}
    return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))


def registry_entry(crop: str | None) -> dict[str, Any] | None:
    if not crop:
        return None
    entry = load_registry().get("models", {}).get(crop.strip().lower())
    if not entry or not entry.get("validated"):
        return None
    if not (PROJECT_ROOT / entry["path"]).exists():
        return None
    return entry


def supported_crops() -> list[str]:
    return sorted(
        crop
        for crop, entry in load_registry().get("models", {}).items()
        if entry.get("validated") and (PROJECT_ROOT / entry["path"]).exists()
    )


def build_model(architecture: str, num_classes: int, pretrained: bool = False):
    import torch.nn as nn
    from torchvision import models

    if architecture == "mobilenet_v3_small":
        weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        model = models.mobilenet_v3_small(weights=weights)
    elif architecture == "mobilenet_v3_large":
        weights = models.MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
        model = models.mobilenet_v3_large(weights=weights)
    else:
        raise ValueError(f"Unsupported architecture: {architecture}")
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    return model


def eval_transform(input_size: int):
    from torchvision import transforms

    return transforms.Compose(
        [
            transforms.Resize(int(input_size * 1.14)),
            transforms.CenterCrop(input_size),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )


@lru_cache(maxsize=16)
def _load_predictor(crop: str, path: str, mtime: float) -> Callable[[Image.Image], list[float]]:
    import torch

    entry = registry_entry(crop)
    checkpoint = torch.load(PROJECT_ROOT / path, map_location="cpu", weights_only=True)
    model = build_model(entry["architecture"], len(entry["labels"]))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    transform = eval_transform(int(entry.get("input_size", 224)))
    temperature = float(entry.get("temperature", 1.0)) or 1.0

    def predict(image: Image.Image) -> list[float]:
        with torch.no_grad():
            tensor = transform(image.convert("RGB")).unsqueeze(0)
            logits = model(tensor) / temperature
            return torch.softmax(logits, dim=1)[0].tolist()

    return predict


def get_predictor(crop: str) -> Callable[[Image.Image], list[float]] | None:
    entry = registry_entry(crop)
    if entry is None or not torch_available():
        return None
    path = entry["path"]
    return _load_predictor(crop.strip().lower(), path, (PROJECT_ROOT / path).stat().st_mtime)


def analyze_image(crop: str | None, image_bytes: bytes, top_k: int = 3) -> VisionResult:
    crop_key = (crop or "").strip().lower() or None
    if crop_key is None:
        return VisionResult(crop=None, model_supported=False, reason="crop_unknown")

    entry = registry_entry(crop_key)
    if entry is None:
        decision = decide_vision(model_supported=False, confidence=None)
        return VisionResult(crop=crop_key, model_supported=False, decision=decision.decision, reason=decision.reason)

    predictor = get_predictor(crop_key)
    if predictor is None:
        return VisionResult(
            crop=crop_key, model_supported=False, decision="ABSTAIN", reason="vision_runtime_unavailable"
        )

    with Image.open(BytesIO(image_bytes)) as image:
        probabilities = predictor(image)

    labels = entry["labels"]
    ranked = sorted(zip(labels, probabilities), key=lambda item: item[1], reverse=True)
    best_label, best_prob = ranked[0]
    decision = decide_vision(model_supported=True, confidence=float(best_prob))

    return VisionResult(
        crop=crop_key,
        model_supported=True,
        prediction=best_label,
        confidence=round(float(best_prob), 4),
        top_k=[{"label": label, "confidence": round(float(prob), 4)} for label, prob in ranked[:top_k]],
        decision=decision.decision,
        reason=decision.reason,
        model={
            "architecture": entry.get("architecture"),
            "labels": labels,
            "validation": entry.get("validation", {}),
            "temperature": entry.get("temperature"),
            "trained_at": entry.get("trained_at"),
        },
    )
