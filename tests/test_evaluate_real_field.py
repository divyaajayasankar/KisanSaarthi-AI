"""Hand-computed checks for scripts/evaluate_real_field.py using a
synthetic folder and a fake analyzer. These are unit tests of the metric
code, not experimental results."""

import csv
from io import BytesIO

import pytest
from PIL import Image

from app.services.vision_inference_service import VisionResult
from scripts import evaluate_real_field as ev


def _jpeg(seed: int) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 64), (seed * 20 % 255, 100, 50)).save(buffer, format="JPEG")
    return buffer.getvalue()


# (filename, ground truth in metadata, fake model output)
RICE = [
    ("r1.jpg", "blast", ("blast", 0.90, "ANSWER")),
    ("r2.jpg", "blast", ("brown_spot", 0.85, "ANSWER")),
    ("r3.jpg", "brown_spot", ("brown_spot", 0.70, "ASK_FOLLOW_UP")),
    ("r4.jpg", "brown_spot", ("brown_spot", 0.95, "ANSWER")),
    ("r5.jpg", "bacterial_leaf_blight", ("blast", 0.40, "ABSTAIN")),
    ("r6.jpg", "TO_VERIFY", ("blast", 0.90, "ANSWER")),
]


@pytest.fixture()
def eval_dir(tmp_path):
    (tmp_path / "rice").mkdir()
    (tmp_path / "banana").mkdir()
    for index, (name, _, _) in enumerate(RICE):
        (tmp_path / "rice" / name).write_bytes(_jpeg(index))
    (tmp_path / "banana" / "b1.jpg").write_bytes(_jpeg(99))
    with (tmp_path / "metadata.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["crop", "disease", "filename", "source", "dataset", "license"])
        for name, disease, _ in RICE:
            writer.writerow(["rice", disease, name, "TO_VERIFY", "TO_VERIFY", "TO_VERIFY"])
        writer.writerow(["banana", "TO_VERIFY", "b1.jpg", "TO_VERIFY", "TO_VERIFY", "TO_VERIFY"])
    return tmp_path


@pytest.fixture()
def fake_analyzer(monkeypatch):
    outputs = {name: out for name, _, out in RICE}

    def analyze(crop, data, top_k=3):
        if crop != "rice":
            return VisionResult(crop=crop, model_supported=False, decision="ABSTAIN", reason="image_model_not_validated_for_crop")
        # identify the image by order of calls: bytes differ per file
        for index, (name, _, _) in enumerate(RICE):
            if data == _jpeg(index):
                label, confidence, decision = outputs[name]
                return VisionResult(crop=crop, model_supported=True, prediction=label, confidence=confidence, decision=decision)
        raise AssertionError("unknown image")

    monkeypatch.setattr(ev, "analyze_image", analyze)


def test_metrics_match_hand_computation(eval_dir, fake_analyzer):
    rows = ev.evaluate(eval_dir, ["rice", "banana"])
    summary = ev.compute_metrics(rows)

    assert summary["images_found"] == 7
    assert summary["images_labeled"] == 5          # r6 is TO_VERIFY, banana is TO_VERIFY
    assert summary["images_scored"] == 5           # labeled AND model-supported
    assert summary["accuracy"] == pytest.approx(0.6)
    assert summary["per_class"]["blast"]["f1"] == pytest.approx(0.5)
    assert summary["per_class"]["brown spot"]["precision"] == pytest.approx(2 / 3)
    assert summary["per_class"]["brown spot"]["recall"] == pytest.approx(1.0)
    assert summary["per_class"]["bacterial leaf blight"]["f1"] == 0
    assert summary["macro_f1"] == pytest.approx((0 + 0.5 + 0.8) / 3)
    assert summary["brier_score_top_label"] == pytest.approx(0.197)
    assert summary["ece_10_bins"] == pytest.approx(0.34)
    assert summary["coverage"] == pytest.approx(0.6)
    assert summary["selective_accuracy"] == pytest.approx(2 / 3)
    assert summary["abstention_rate_all_valid"] == pytest.approx(3 / 7)
    assert summary["confusion"]["blast"] == {"blast": 1, "brown spot": 1}


def test_unlabeled_and_unsupported_images_are_not_scored(eval_dir, fake_analyzer):
    rows = {(r["crop"], r["filename"]): r for r in ev.evaluate(eval_dir, ["rice", "banana"])}
    assert rows[("rice", "r6.jpg")]["scored"] is False and rows[("rice", "r6.jpg")]["correct"] == ""
    banana = rows[("banana", "b1.jpg")]
    assert banana["model_supported"] is False and banana["prediction"] == "" and banana["decision"] == "ABSTAIN"


def test_no_validated_model_produces_no_accuracy(eval_dir):
    rows = ev.evaluate(eval_dir, ["banana"])
    summary = ev.compute_metrics(rows)
    assert summary["images_scored"] == 0
    assert "accuracy" not in summary and "macro_f1" not in summary
    assert "No image is both labeled" in summary["note"]
    assert summary["abstention_rate_all_valid"] == 1.0


def test_invalid_image_is_reported_not_crashed(tmp_path):
    (tmp_path / "rice").mkdir()
    (tmp_path / "rice" / "bad.jpg").write_bytes(b"not an image")
    rows = ev.evaluate(tmp_path, ["rice"])
    assert rows[0]["image_status"].startswith("invalid")
    assert ev.compute_metrics(rows)["images_invalid"] == 1


def test_label_names_are_compared_through_the_alias_layer():
    assert ev.canonical_label("rice", "rice_blast") == ev.canonical_label("rice", "Blast")
    assert ev.canonical_label("rice", "brownspot") == ev.canonical_label("rice", "brown_spot")


def test_ece_perfectly_calibrated_is_zero():
    pairs = [(1.0, 1)] * 5 + [(0.0, 0)] * 5
    assert ev.expected_calibration_error(pairs) == pytest.approx(0.0)
