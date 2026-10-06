from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


# ============================================================
# VERIFIED CROP-SOIL RULE
# ============================================================

class CropSoilRule(Base):

    __tablename__ = "crop_soil_rules"


    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )


    crop: Mapped[str] = mapped_column(
        String,
        index=True,
        nullable=False,
    )


    min_ph: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )


    max_ph: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )


    preferred_texture: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )


    source_document: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )


    source_page: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )


    source_url: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )


    source_date: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )


    verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )


    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
