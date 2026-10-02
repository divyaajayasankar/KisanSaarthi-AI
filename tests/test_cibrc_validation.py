from app.data.cibrc import validate_registry_row


def valid_row():
    return {
        "crop": "TEST_CROP",
        "pest": "TEST_PEST",
        "active_ingredient": "TEST_AI",
        "formulation": "TEST_FORM",
        "dose_min_per_hectare": "500",
        "dose_max_per_hectare": "750",
        "dose_unit": "ml",
        "water_volume_l_per_ha": "500",
        "phi_days": "10",
        "source_document": "test.pdf",
        "source_page": "15",
        "source_url": "https://ppqs.gov.in/test.pdf",
        "source_date": "2024-01-01",
        "verified": "1",
    }


def test_valid_verified_row():
    status, _, reason = validate_registry_row(valid_row())
    assert status == "accepted"
    assert reason == "ok"


def test_missing_phi_rejected():
    row = valid_row()
    row["phi_days"] = ""
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "phi_missing"


def test_non_numeric_phi_rejected():
    row = valid_row()
    row["phi_days"] = "abc"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "phi_not_numeric"


def test_negative_phi_rejected():
    row = valid_row()
    row["phi_days"] = "-5"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "phi_negative"


def test_implausible_phi_rejected():
    row = valid_row()
    row["phi_days"] = "150"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "phi_implausible"


def test_zero_minimum_dose_rejected():
    row = valid_row()
    row["dose_min_per_hectare"] = "0"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "dose_min_not_positive"


def test_zero_maximum_dose_rejected():
    row = valid_row()
    row["dose_max_per_hectare"] = "0"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "dose_max_not_positive"


def test_non_numeric_minimum_dose_rejected():
    row = valid_row()
    row["dose_min_per_hectare"] = "abc"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "dose_min_not_numeric"


def test_non_numeric_maximum_dose_rejected():
    row = valid_row()
    row["dose_max_per_hectare"] = "abc"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "dose_max_not_numeric"


def test_invalid_dose_range_rejected():
    row = valid_row()
    row["dose_min_per_hectare"] = "750"
    row["dose_max_per_hectare"] = "500"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "dose_range_invalid"


def test_exact_dose_is_allowed():
    row = valid_row()
    row["dose_min_per_hectare"] = "750"
    row["dose_max_per_hectare"] = "750"
    status, _, reason = validate_registry_row(row)
    assert status == "accepted"
    assert reason == "ok"


def test_invalid_water_volume_rejected():
    row = valid_row()
    row["water_volume_l_per_ha"] = "abc"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "water_volume_invalid"


def test_zero_water_volume_rejected():
    row = valid_row()
    row["water_volume_l_per_ha"] = "0"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "water_volume_invalid"


def test_blank_water_volume_allowed():
    row = valid_row()
    row["water_volume_l_per_ha"] = ""
    status, _, reason = validate_registry_row(row)
    assert status == "accepted"
    assert reason == "ok"


def test_missing_source_document_rejected():
    row = valid_row()
    row["source_document"] = ""
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "missing_source_document"


def test_invalid_source_page_rejected():
    row = valid_row()
    row["source_page"] = "abc"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "source_page_invalid"


def test_zero_source_page_rejected():
    row = valid_row()
    row["source_page"] = "0"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "source_page_invalid"


def test_non_ppqs_source_rejected():
    row = valid_row()
    row["source_url"] = "https://example.com/test.pdf"
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "non_ppqs_source"


def test_missing_crop_rejected():
    row = valid_row()
    row["crop"] = ""
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "missing_crop"


def test_missing_pest_rejected():
    row = valid_row()
    row["pest"] = ""
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "missing_pest"


def test_missing_active_ingredient_rejected():
    row = valid_row()
    row["active_ingredient"] = ""
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "missing_active_ingredient"


def test_missing_dose_unit_rejected():
    row = valid_row()
    row["dose_unit"] = ""
    status, _, reason = validate_registry_row(row)
    assert status == "rejected"
    assert reason == "missing_dose_unit"


def test_unverified_row_goes_pending():
    row = valid_row()
    row["verified"] = "0"
    status, _, reason = validate_registry_row(row)
    assert status == "pending"
    assert reason == "manual_verification_required"


def test_verified_yes_is_accepted():
    row = valid_row()
    row["verified"] = "yes"
    status, _, reason = validate_registry_row(row)
    assert status == "accepted"
    assert reason == "ok"
