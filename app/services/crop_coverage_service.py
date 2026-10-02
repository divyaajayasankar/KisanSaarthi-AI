from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
    .parent
)

COVERAGE_FILE = (
    PROJECT_ROOT
    / "data"
    / "coverage"
    / "crop_coverage.json"
)


def _normalize(
    value: str | None,
) -> str:
    """
    Normalize crop names for matching.
    """

    if not value:
        return ""

    return value.strip().lower()


def load_crop_coverage() -> list[dict[str, Any]]:
    """
    Load the configured crop coverage information.
    """

    if not COVERAGE_FILE.exists():

        raise FileNotFoundError(
            f"Crop coverage file not found: {COVERAGE_FILE}"
        )

    with COVERAGE_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(file)

    if not isinstance(data, list):

        raise ValueError(
            "Crop coverage file must contain a JSON list."
        )

    return data


def get_crop_coverage(
    crop: str,
) -> dict[str, Any]:
    """
    Return capability information for one crop.
    """

    normalized_crop = _normalize(
        crop
    )

    for record in load_crop_coverage():

        record_crop = _normalize(
            record.get("crop")
        )

        if record_crop == normalized_crop:

            return {
                **record,
                "supported": (
                    record.get("status")
                    == "supported"
                ),
            }

    return {
        "crop": crop,
        "status": "unsupported",
        "supported": False,
        "registry": False,
        "phi": False,
        "growth_stage": False,
        "treatment_history": False,
        "resistance": False,
        "weather": False,
        "soil": False,
        "rag": False,
    }


def get_supported_crops() -> list[str]:
    """
    Return crops with complete verified support.
    """

    return [
        record["crop"]
        for record in load_crop_coverage()
        if record.get("status") == "supported"
    ]


def get_all_configured_crops() -> list[str]:
    """
    Return all configured crops.
    """

    return [
        record["crop"]
        for record in load_crop_coverage()
    ]