from dataclasses import dataclass


REQUIRED_COLUMNS = {
    "crop",
    "pest",
    "active_ingredient",
    "allowed_stages",
    "application_timing",
    "source_document",
    "source_page",
    "source_url",
    "source_date",
    "verified",
}


VALID_STAGES = {
    "sowing",
    "seedling",
    "vegetative",
    "reproductive",
    "pre_harvest",
}


@dataclass
class GrowthStageValidationResult:
    status: str
    reason: str | None
    row: dict


def parse_verified(value) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


def normalize_stage(value: str) -> str:
    cleaned = (
        value.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    aliases = {
        "sowing_stage": "sowing",
        "seedling_stage": "seedling",
        "vegetative_stage": "vegetative",
        "flowering": "reproductive",
        "flowering_stage": "reproductive",
        "fruiting": "reproductive",
        "fruiting_stage": "reproductive",
        "reproductive_stage": "reproductive",
        "preharvest": "pre_harvest",
        "pre_harvest_stage": "pre_harvest",
    }

    return aliases.get(cleaned, cleaned)


def validate_growth_stage_columns(
    columns: list[str] | None,
) -> tuple[bool, list[str]]:

    if not columns:
        return False, sorted(REQUIRED_COLUMNS)

    missing = REQUIRED_COLUMNS - set(columns)

    return len(missing) == 0, sorted(missing)


def validate_growth_stage_row(
    row: dict,
) -> GrowthStageValidationResult:

    crop = str(row.get("crop", "")).strip()
    pest = str(row.get("pest", "")).strip()
    active_ingredient = str(
        row.get("active_ingredient", "")
    ).strip()

    allowed_raw = str(
        row.get("allowed_stages", "")
    ).strip()

    application_timing = str(
        row.get("application_timing", "")
    ).strip()

    source_document = str(
        row.get("source_document", "")
    ).strip()

    source_page_raw = str(
        row.get("source_page", "")
    ).strip()

    source_url = str(
        row.get("source_url", "")
    ).strip()

    source_date = str(
        row.get("source_date", "")
    ).strip()

    verified = parse_verified(
        row.get("verified")
    )

    if not crop:
        return GrowthStageValidationResult(
            "rejected",
            "missing_crop",
            row,
        )

    if not pest:
        return GrowthStageValidationResult(
            "rejected",
            "missing_pest",
            row,
        )

    if not active_ingredient:
        return GrowthStageValidationResult(
            "rejected",
            "missing_active_ingredient",
            row,
        )

    if not allowed_raw:
        return GrowthStageValidationResult(
            "rejected",
            "missing_allowed_stages",
            row,
        )

    raw_stages = [
        item.strip()
        for item in allowed_raw.split(";")
        if item.strip()
    ]

    normalized_stages = [
        normalize_stage(item)
        for item in raw_stages
    ]

    for stage in normalized_stages:
        if stage not in VALID_STAGES:
            return GrowthStageValidationResult(
                "rejected",
                "invalid_growth_stage",
                row,
            )

    if not application_timing:
        return GrowthStageValidationResult(
            "rejected",
            "missing_application_timing",
            row,
        )

    if not source_document:
        return GrowthStageValidationResult(
            "rejected",
            "missing_source_document",
            row,
        )

    if not source_url:
        return GrowthStageValidationResult(
            "rejected",
            "missing_source_url",
            row,
        )

    if not source_date:
        return GrowthStageValidationResult(
            "rejected",
            "missing_source_date",
            row,
        )

    try:
        source_page = int(source_page_raw)

        if source_page <= 0:
            raise ValueError

    except (ValueError, TypeError):
        return GrowthStageValidationResult(
            "rejected",
            "invalid_source_page",
            row,
        )

    normalized_row = dict(row)

    normalized_row["allowed_stages"] = ";".join(
        normalized_stages
    )

    normalized_row["verified"] = verified

    if verified:
        return GrowthStageValidationResult(
            "accepted",
            None,
            normalized_row,
        )

    return GrowthStageValidationResult(
        "pending",
        "not_verified",
        normalized_row,
    )