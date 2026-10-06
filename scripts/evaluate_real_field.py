"""Evaluate image diagnosis on the independent real-field set.

    python -m scripts.evaluate_real_field
    python -m scripts.evaluate_real_field --crop tomato

For every image in data/real_field_eval/<crop>/ this runs the same
pipeline as the app: image quality validation, then crop-aware analysis
(validated model for that crop, otherwise image ABSTAIN).

Outputs (reports/):
    real_field_eval_predictions.csv   crop, filename, ground_truth, prediction,
                                      confidence, decision, correct (+ status columns)
    real_field_eval_confusion.csv     confusion matrix
    real_field_eval_summary.json/.md  metrics

Metric rules
    * An image is SCORED only if it has a real disease label in
      metadata.csv (not TO_VERIFY/empty) AND its crop has a validated model.
      Everything else is reported as unlabeled / unsupported and is not
      counted in accuracy, precision, recall or F1.
    * Brier score is the top-label Brier score: mean((confidence - correct)^2).
    * ECE uses 10 equal-width confidence bins on the top-label confidence.
    * Coverage = share of scored images with decision ANSWER.
    * Selective accuracy = accuracy on the scored images with decision ANSWER.
    * Abstention rate = share of ALL valid images whose decision is not ANSWER.
    * Nothing is computed from empty data; with no validated model the
      report states that and no accuracy figure is produced.

This set is for evaluation only. Nothing here is used for training.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.image_quality_service import ImageValidationError, validate_image
from app.services.pest_alias_service import find_alias_in_text
from app.services.text_utils import normalize_text
from app.services.vision_inference_service import analyze_image, supported_crops


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_DIR = PROJECT_ROOT / "data" / "real_field_eval"
REPORTS = PROJECT_ROOT / "reports"

CROPS = [
    "rice", "wheat", "maize", "tomato", "chilli", "brinjal", "onion", "potato",
    "okra", "cabbage", "groundnut", "chickpea", "mustard", "cotton", "banana",
]
TARGET_PER_CROP = 5
UNKNOWN = {"", "to_verify", "unknown", "n/a", "na", "none"}
CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


# ---------------------------------------------------------------- labels

def canonical_label(crop: str, label: str | None) -> str:
    """Compare labels through the alias layer so 'rice_blast', 'Blast'
    and 'blast' are the same class."""
    if not label:
        return ""
    alias = find_alias_in_text(crop, label.replace("_", " "))
    return normalize_text(alias.canonical if alias else label.replace("_", " "))


def is_labeled(disease: str | None) -> bool:
    return (disease or "").strip().lower() not in UNKNOWN


# ---------------------------------------------------------------- metrics

def prf(confusion: dict[str, Counter], labels: list[str]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in labels if other != label)
        fn = sum(confusion[label][other] for other in labels if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        result[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    return result


def expected_calibration_error(pairs: list[tuple[float, int]], bins: int = 10) -> float:
    if not pairs:
        return 0.0
    total = len(pairs)
    error = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        bucket = [(c, k) for c, k in pairs if (low <= c < high) or (index == bins - 1 and c == 1.0)]
        if bucket:
            confidence = sum(c for c, _ in bucket) / len(bucket)
            accuracy = sum(k for _, k in bucket) / len(bucket)
            error += len(bucket) / total * abs(accuracy - confidence)
    return error


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [r for r in rows if r["image_status"] == "valid"]
    scored = [r for r in valid if r["scored"]]
    summary: dict[str, Any] = {
        "images_found": len(rows),
        "images_valid": len(valid),
        "images_invalid": len(rows) - len(valid),
        "images_labeled": sum(1 for r in valid if r["labeled"]),
        "images_with_model": sum(1 for r in valid if r["model_supported"]),
        "images_scored": len(scored),
        "abstention_rate_all_valid": (sum(1 for r in valid if r["decision"] != "ANSWER") / len(valid)) if valid else None,
    }
    if not scored:
        summary["note"] = (
            "No image is both labeled and covered by a validated model, so no accuracy, "
            "precision, recall, F1, calibration or selective-accuracy figure is computed."
        )
        return summary

    labels = sorted({r["gt_canonical"] for r in scored} | {r["pred_canonical"] for r in scored})
    confusion: dict[str, Counter] = {label: Counter() for label in labels}
    for r in scored:
        confusion[r["gt_canonical"]][r["pred_canonical"]] += 1

    per_class = prf(confusion, labels)
    correct = [1 if r["correct"] else 0 for r in scored]
    pairs = [(float(r["confidence"]), k) for r, k in zip(scored, correct)]
    answered = [r for r in scored if r["decision"] == "ANSWER"]

    summary.update(
        {
            "accuracy": sum(correct) / len(scored),
            "macro_f1": sum(v["f1"] for v in per_class.values()) / len(per_class),
            "per_class": per_class,
            "labels": labels,
            "brier_score_top_label": sum((c - k) ** 2 for c, k in pairs) / len(pairs),
            "ece_10_bins": expected_calibration_error(pairs),
            "coverage": len(answered) / len(scored),
            "selective_accuracy": (sum(1 for r in answered if r["correct"]) / len(answered)) if answered else None,
            "confusion": {label: dict(confusion[label]) for label in labels},
        }
    )
    return summary


# ---------------------------------------------------------------- run

def load_labels(eval_dir: Path) -> dict[tuple[str, str], dict[str, str]]:
    path = eval_dir / "metadata.csv"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            ((r.get("crop") or "").strip().lower(), (r.get("filename") or "").strip()): r
            for r in csv.DictReader(handle)
        }


def evaluate(eval_dir: Path, crops: list[str]) -> list[dict[str, Any]]:
    labels = load_labels(eval_dir)
    rows: list[dict[str, Any]] = []
    for crop in crops:
        folder = eval_dir / crop
        if not folder.exists():
            continue
        for path in sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in CONTENT_TYPES):
            meta = labels.get((crop, path.name), {})
            disease = (meta.get("disease") or "").strip()
            row: dict[str, Any] = {
                "crop": crop, "filename": path.name, "ground_truth": disease if is_labeled(disease) else "",
                "labeled": is_labeled(disease), "prediction": "", "confidence": "", "decision": "",
                "correct": "", "model_supported": False, "image_status": "valid", "reason": "",
                "scored": False, "gt_canonical": "", "pred_canonical": "",
            }
            data = path.read_bytes()
            try:
                validate_image(filename=path.name, content_type=CONTENT_TYPES[path.suffix.lower()], image_bytes=data)
            except ImageValidationError as exc:
                row.update(image_status=f"invalid: {exc}", decision="ABSTAIN", reason="image_invalid")
                rows.append(row)
                continue

            result = analyze_image(crop, data)
            row.update(
                model_supported=result.model_supported,
                prediction=result.prediction or "",
                confidence="" if result.confidence is None else result.confidence,
                decision=result.decision,
                reason=result.reason,
            )
            if row["labeled"] and result.model_supported and result.prediction:
                row["gt_canonical"] = canonical_label(crop, disease)
                row["pred_canonical"] = canonical_label(crop, result.prediction)
                row["correct"] = row["gt_canonical"] == row["pred_canonical"]
                row["scored"] = True
            rows.append(row)
    return rows


def write_reports(rows: list[dict[str, Any]], summary: dict[str, Any], crops: list[str], eval_dir: Path) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)

    columns = ["crop", "filename", "ground_truth", "prediction", "confidence", "decision", "correct",
               "model_supported", "image_status", "reason"]
    with (REPORTS / "real_field_eval_predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    if "confusion" in summary:
        labels = summary["labels"]
        with (REPORTS / "real_field_eval_confusion.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["ground_truth \\ predicted", *labels])
            for gt in labels:
                writer.writerow([gt, *[summary["confusion"][gt].get(p, 0) for p in labels]])

    counts = Counter(r["crop"] for r in rows)
    summary["images_per_crop"] = {crop: counts.get(crop, 0) for crop in crops}
    summary["target_per_crop"] = TARGET_PER_CROP
    summary["dataset_complete"] = all(counts.get(c, 0) >= TARGET_PER_CROP for c in CROPS)
    summary["validated_model_crops"] = supported_crops()
    (REPORTS / "real_field_eval_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    def pct(value: float | None) -> str:
        return "n/a" if value is None else f"{value * 100:.1f}%"

    lines = [
        "# Real-field evaluation",
        "",
        f"Evaluation folder: `{eval_dir}`",
        f"Images found: {summary['images_found']} of {TARGET_PER_CROP * len(CROPS)} target "
        f"({'complete' if summary['dataset_complete'] else 'NOT complete'})",
        f"Valid: {summary['images_valid']}  |  Labeled: {summary['images_labeled']}  |  "
        f"With a validated model: {summary['images_with_model']}  |  Scored: {summary['images_scored']}",
        f"Crops with a validated model: {', '.join(summary['validated_model_crops']) or 'none'}",
        f"Abstention rate (all valid images): {pct(summary['abstention_rate_all_valid'])}",
        "",
    ]
    if "note" in summary:
        lines += [summary["note"], ""]
    else:
        lines += [
            f"Accuracy: {pct(summary['accuracy'])}  |  Macro-F1: {summary['macro_f1']:.3f}  |  "
            f"Brier (top-label): {summary['brier_score_top_label']:.3f}  |  ECE: {summary['ece_10_bins']:.3f}",
            f"Coverage: {pct(summary['coverage'])}  |  Selective accuracy: {pct(summary['selective_accuracy'])}",
            "",
            "| class | precision | recall | F1 | support |",
            "|---|---|---|---|---|",
        ]
        for label, v in summary["per_class"].items():
            lines.append(f"| {label} | {v['precision']:.3f} | {v['recall']:.3f} | {v['f1']:.3f} | {v['support']} |")
        lines.append("")
    lines += ["| crop | images | target |", "|---|---|---|"]
    lines += [f"| {crop} | {summary['images_per_crop'][crop]} | {TARGET_PER_CROP} |" for crop in crops]
    (REPORTS / "real_field_eval_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crop", help="evaluate one crop only")
    parser.add_argument("--eval-dir", default=str(DEFAULT_EVAL_DIR))
    args = parser.parse_args()

    eval_dir = Path(args.eval_dir)
    crops = [args.crop.lower()] if args.crop else CROPS
    rows = evaluate(eval_dir, crops)
    summary = compute_metrics(rows)
    write_reports(rows, summary, crops, eval_dir)

    print(f"images found {summary['images_found']} | scored {summary['images_scored']} | "
          f"abstention rate {summary['abstention_rate_all_valid']}")
    print(summary.get("note") or f"accuracy {summary['accuracy']:.3f}  macro-F1 {summary['macro_f1']:.3f}")
    print(f"Reports written to {REPORTS}")


if __name__ == "__main__":
    main()
