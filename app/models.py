from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


# ============================================================
# FARMER PROFILE
# ============================================================

class FarmerProfile(Base):
    __tablename__ = "farmer_profiles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    farmer_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    preferred_language: Mapped[str] = mapped_column(
        String(30),
        default="English",
    )

    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    district: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    crop: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    pest: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    field_area: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    area_unit: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    expected_harvest_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    growth_stage: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


# ============================================================
# CIB&RC / PPQS REGISTRY
# ============================================================

class RegistryEntry(Base):
    __tablename__ = "registry_entries"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    crop: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    pest: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    active_ingredient: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    formulation: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    # --------------------------------------------------------
    # REGISTERED DOSE RANGE PER HECTARE
    #
    # Example:
    # 500–750 ml/ha
    #
    # If registry has one exact dose:
    # min = max
    # Example:
    # 750 g/ha
    # min = 750
    # max = 750
    # --------------------------------------------------------

    dose_min_per_hectare: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    dose_max_per_hectare: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    dose_unit: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    # --------------------------------------------------------
    # WATER VOLUME
    # --------------------------------------------------------

    water_volume_l_per_ha: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

        # --------------------------------------------------------
    # PRE-HARVEST INTERVAL / WAITING PERIOD
    # --------------------------------------------------------

    phi_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    phi_not_applicable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # --------------------------------------------------------
    # SOURCE PROVENANCE
    # --------------------------------------------------------

    source_document: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source_page: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_date: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    # --------------------------------------------------------
    # VERIFICATION STATUS
    # --------------------------------------------------------

    verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    is_test_data: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    

    # --------------------------------------------------------
    # SOURCE PROVENANCE
    # --------------------------------------------------------

    source_document: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source_page: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_date: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    # --------------------------------------------------------
    # VERIFICATION STATUS
    # --------------------------------------------------------

    verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Synthetic records are allowed only for software tests.
    is_test_data: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


# ============================================================
# DATA PROVENANCE
# ============================================================

class DataProvenance(Base):
    __tablename__ = "data_provenance"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    artifact_name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    local_file: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    version_date: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


# ============================================================
# ADVISORY HISTORY
# ============================================================

class AdvisoryRun(Base):
    __tablename__ = "advisory_runs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    farmer_id: Mapped[int | None] = mapped_column(
        ForeignKey("farmer_profiles.id"),
        nullable=True,
    )

    crop: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    pest: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # JSON-formatted rule trace for research evaluation.
    fired_rules: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )