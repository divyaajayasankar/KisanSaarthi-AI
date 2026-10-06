"""Fine-tune a crop-specific MobileNetV3 disease classifier on CPU.

    python -m scripts.train_crop_model --crop rice
    python -m scripts.train_crop_model --crop rice --epochs 10 --arch mobilenet_v3_large

Reads class folders from data/vision/crop_datasets.json.

Safeguards
  - images whose SHA-256 matches any file in data/real_field_eval/ are
    excluded (no train/test leakage with the independent evaluation set)
  - stratified train/validation split with a fixed seed
  - temperature scaling fitted on the validation split for calibrated
    confidence
  - the model is registered as validated only if validation macro-F1
    reaches --min-macro-f1; otherwise the app keeps abstaining on images
  - dataset license must be set in the config, or explicitly accepted
    as unverified with --accept-unverified-license (recorded in the card)

Outputs
  data/models/<crop>_mobilenetv3.pt
  data/models/model_registry.json (entry for <crop>)
  reports/vision_training_<crop>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "data" / "vision" / "crop_datasets.json"
EVAL_DIR = PROJECT_ROOT / "data" / "real_field_eval"
MODEL_DIR = PROJECT_ROOT / "data" / "models"
REGISTRY_FILE = MODEL_DIR / "model_registry.json"
REPORT_DIR = PROJECT_ROOT / "reports"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluation_hashes() -> set[str]:
    if not EVAL_DIR.exists():
        return set()
    return {sha256(path) for path in EVAL_DIR.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES}


def collect_samples(root: Path, classes: dict[str, list[str]], max_per_class: int | None, seed: int):
    blocked = evaluation_hashes()
    samples: list[tuple[Path, int]] = []
    excluded = 0
    labels = sorted(classes)
    for index, label in enumerate(labels):
        files: list[Path] = []
        for folder in classes[label]:
            directory = (root / folder).resolve()
            if EVAL_DIR.resolve() in directory.parents or directory == EVAL_DIR.resolve():
                raise SystemExit(f"Refusing to train on the evaluation set: {directory}")
            if not directory.exists():
                raise SystemExit(f"Class folder not found: {directory}")
            files.extend(path for path in directory.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)
        files = sorted(set(files))
        random.Random(seed).shuffle(files)
        kept = []
        for path in files:
            if blocked and sha256(path) in blocked:
                excluded += 1
                continue
            kept.append(path)
        if max_per_class:
            kept = kept[:max_per_class]
        samples.extend((path, index) for path in kept)
    return labels, samples, excluded


def stratified_split(samples, val_fraction: float, seed: int):
    by_class: dict[int, list] = {}
    for item in samples:
        by_class.setdefault(item[1], []).append(item)
    train, val = [], []
    rng = random.Random(seed)
    for items in by_class.values():
        rng.shuffle(items)
        cut = max(1, int(round(len(items) * val_fraction)))
        val.extend(items[:cut])
        train.extend(items[cut:])
    return train, val


def macro_metrics(y_true: list[int], y_pred: list[int], n: int) -> dict:
    confusion = [[0] * n for _ in range(n)]
    for truth, pred in zip(y_true, y_pred):
        confusion[truth][pred] += 1
    per_class = []
    for k in range(n):
        tp = confusion[k][k]
        fp = sum(confusion[r][k] for r in range(n)) - tp
        fn = sum(confusion[k]) - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class.append({"precision": precision, "recall": recall, "f1": f1, "support": sum(confusion[k])})
    accuracy = sum(confusion[k][k] for k in range(n)) / max(1, len(y_true))
    return {
        "accuracy": accuracy,
        "macro_precision": sum(c["precision"] for c in per_class) / n,
        "macro_recall": sum(c["recall"] for c in per_class) / n,
        "macro_f1": sum(c["f1"] for c in per_class) / n,
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


def expected_calibration_error(confidences: list[float], correct: list[bool], bins: int = 10) -> float:
    total = len(confidences)
    if not total:
        return float("nan")
    ece = 0.0
    for b in range(bins):
        low, high = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(confidences) if (low < c <= high) or (b == 0 and c == 0)]
        if not idx:
            continue
        accuracy = sum(correct[i] for i in idx) / len(idx)
        confidence = sum(confidences[i] for i in idx) / len(idx)
        ece += len(idx) / total * abs(accuracy - confidence)
    return ece


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crop", required=True)
    parser.add_argument("--config", default=str(CONFIG_FILE))
    parser.add_argument("--arch", default="mobilenet_v3_small", choices=["mobilenet_v3_small", "mobilenet_v3_large"])
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--input-size", type=int, default=224)
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--min-macro-f1", type=float, default=0.70)
    parser.add_argument("--min-images-per-class", type=int, default=20)
    parser.add_argument("--max-per-class", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-pretrained", action="store_true", help="Random init (no ImageNet download).")
    parser.add_argument("--accept-unverified-license", action="store_true")
    parser.add_argument("--workers", type=int, default=0)
    args = parser.parse_args()

    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
    from torchvision import transforms

    from app.services.vision_inference_service import IMAGENET_MEAN, IMAGENET_STD, build_model, eval_transform

    crop = args.crop.strip().lower()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    crop_cfg = config.get("crops", {}).get(crop)
    if not crop_cfg or not crop_cfg.get("classes"):
        raise SystemExit(f"No classes configured for '{crop}' in {args.config}. Run scripts.inspect_source_datasets first.")
    if len(crop_cfg["classes"]) < 2:
        raise SystemExit("A disease classifier needs at least 2 classes.")
    license_value = str(crop_cfg.get("license", "TO_VERIFY"))
    if license_value.upper() == "TO_VERIFY" and not args.accept_unverified_license:
        raise SystemExit(
            f"License for '{crop}' training data is TO_VERIFY. Set it in {args.config} "
            "or pass --accept-unverified-license (recorded in the model card)."
        )

    random.seed(args.seed)
    torch.manual_seed(args.seed)

    root = (PROJECT_ROOT / config.get("root", "data/source_datasets")).resolve()
    labels, samples, excluded = collect_samples(root, crop_cfg["classes"], args.max_per_class, args.seed)
    counts = Counter(label for _, label in samples)
    for index, label in enumerate(labels):
        if counts[index] < args.min_images_per_class:
            raise SystemExit(f"Class '{label}' has {counts[index]} images; need >= {args.min_images_per_class}.")

    train_items, val_items = stratified_split(samples, args.val_fraction, args.seed)
    print(f"{crop}: classes={labels}")
    print(f"  images={len(samples)} train={len(train_items)} val={len(val_items)} excluded_eval_duplicates={excluded}")

    train_tf = transforms.Compose(
        [
            transforms.RandomResizedCrop(args.input_size, scale=(0.6, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomRotation(20),
            transforms.ColorJitter(0.3, 0.3, 0.3, 0.05),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    val_tf = eval_transform(args.input_size)

    class Folder(Dataset):
        def __init__(self, items, transform):
            self.items, self.transform = items, transform

        def __len__(self):
            return len(self.items)

        def __getitem__(self, index):
            path, label = self.items[index]
            with Image.open(path) as image:
                return self.transform(image.convert("RGB")), label

    train_loader = DataLoader(Folder(train_items, train_tf), batch_size=args.batch_size, shuffle=True, num_workers=args.workers)
    val_loader = DataLoader(Folder(val_items, val_tf), batch_size=args.batch_size, shuffle=False, num_workers=args.workers)

    pretrained = not args.no_pretrained
    try:
        model = build_model(args.arch, len(labels), pretrained=pretrained)
    except Exception as exc:  # network blocked etc.
        print(f"  ImageNet weights unavailable ({exc.__class__.__name__}); using random init.")
        pretrained = False
        model = build_model(args.arch, len(labels), pretrained=False)

    # torchvision MobileNetV3 uses BatchNorm momentum 0.01, so on small
    # CPU fine-tuning runs the eval-mode running statistics lag far behind
    # the weights and validation collapses to one class. 0.1 is the
    # PyTorch default and tracks the data within a few hundred steps.
    for module in model.modules():
        if isinstance(module, nn.BatchNorm2d):
            module.momentum = 0.1

    class_weights = torch.tensor(
        [len(train_items) / (len(labels) * max(1, sum(1 for _, y in train_items if y == k))) for k in range(len(labels))],
        dtype=torch.float32,
    )
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, args.epochs))

    def evaluate():
        model.eval()
        logits_all, targets = [], []
        with torch.no_grad():
            for images, target in val_loader:
                logits_all.append(model(images))
                targets.append(target)
        return torch.cat(logits_all), torch.cat(targets)

    best_f1, best_state, history = -1.0, None, []
    started = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        running, seen = 0.0, 0
        for images, target in train_loader:
            optimizer.zero_grad()
            loss = criterion(model(images), target)
            loss.backward()
            optimizer.step()
            running += loss.item() * len(target)
            seen += len(target)
        scheduler.step()
        logits, targets = evaluate()
        metrics = macro_metrics(targets.tolist(), logits.argmax(1).tolist(), len(labels))
        history.append({"epoch": epoch, "train_loss": running / max(1, seen), "val_accuracy": metrics["accuracy"], "val_macro_f1": metrics["macro_f1"]})
        print(f"  epoch {epoch}/{args.epochs} loss={running / max(1, seen):.4f} val_acc={metrics['accuracy']:.4f} val_macro_f1={metrics['macro_f1']:.4f}")
        if metrics["macro_f1"] > best_f1:
            best_f1 = metrics["macro_f1"]
            best_state = {key: value.detach().clone() for key, value in model.state_dict().items()}

    model.load_state_dict(best_state)
    logits, targets = evaluate()

    # temperature scaling by NLL grid search on the validation split
    nll = nn.CrossEntropyLoss()
    grid = [round(0.25 + 0.05 * i, 2) for i in range(96)]  # 0.25 .. 5.0
    temperature = min(grid, key=lambda temp: nll(logits / temp, targets).item())

    def calibration(temp: float):
        probs = torch.softmax(logits / temp, dim=1)
        conf, pred = probs.max(1)
        correct = (pred == targets).tolist()
        brier = float(((probs - torch.nn.functional.one_hot(targets, len(labels)).float()) ** 2).sum(1).mean())
        return expected_calibration_error(conf.tolist(), correct), brier

    ece_raw, brier_raw = calibration(1.0)
    ece_cal, brier_cal = calibration(temperature)
    final = macro_metrics(targets.tolist(), logits.argmax(1).tolist(), len(labels))
    validated = final["macro_f1"] >= args.min_macro_f1

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / f"{crop}_mobilenetv3.pt"
    torch.save({"state_dict": model.state_dict(), "labels": labels, "architecture": args.arch}, model_path)

    trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    validation = {
        "split": f"stratified {int(args.val_fraction * 100)}% holdout, seed {args.seed}",
        "n_train": len(train_items),
        "n_val": len(val_items),
        "accuracy": round(final["accuracy"], 4),
        "macro_precision": round(final["macro_precision"], 4),
        "macro_recall": round(final["macro_recall"], 4),
        "macro_f1": round(final["macro_f1"], 4),
        "ece_before_temperature": round(ece_raw, 4),
        "ece_after_temperature": round(ece_cal, 4),
        "brier_before_temperature": round(brier_raw, 4),
        "brier_after_temperature": round(brier_cal, 4),
        "min_macro_f1_required": args.min_macro_f1,
        "note": "Validation images come from the same source dataset as training; real-field performance is measured separately by scripts/evaluate_real_field.py.",
    }

    registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8")) if REGISTRY_FILE.exists() else {"models": {}}
    registry.setdefault("models", {})[crop] = {
        "path": str(model_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "architecture": args.arch,
        "labels": labels,
        "input_size": args.input_size,
        "temperature": temperature,
        "validated": validated,
        "pretrained_imagenet": pretrained,
        "trained_at": trained_at,
        "training_source": crop_cfg.get("source", "TO_VERIFY"),
        "training_license": license_value,
        "license_accepted_unverified": license_value.upper() == "TO_VERIFY",
        "classes_config": crop_cfg["classes"],
        "excluded_eval_duplicates": excluded,
        "validation": validation,
    }
    REGISTRY_FILE.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    report = {
        "crop": crop,
        "labels": labels,
        "history": history,
        "validation": validation,
        "per_class": {labels[k]: final["per_class"][k] for k in range(len(labels))},
        "confusion_matrix": {"labels": labels, "matrix": final["confusion_matrix"]},
        "temperature": temperature,
        "validated": validated,
        "minutes": round((time.time() - started) / 60, 2),
    }
    (REPORT_DIR / f"vision_training_{crop}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"\n  val macro-F1={final['macro_f1']:.4f} accuracy={final['accuracy']:.4f} temperature={temperature}")
    print(f"  ECE {ece_raw:.4f} -> {ece_cal:.4f} after temperature scaling")
    print(f"  validated={validated} (needs macro-F1 >= {args.min_macro_f1})")
    print(f"  model: {model_path}")
    if not validated:
        print("  Not validated: the app will keep abstaining on images for this crop.")


if __name__ == "__main__":
    main()
