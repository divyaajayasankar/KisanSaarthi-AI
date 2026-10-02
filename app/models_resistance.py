from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ResistanceRule(Base):

    __tablename__ = "resistance_rules"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    crop: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    pest: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    active_ingredient: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    framework: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    moa_group: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    moa_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    resistance_risk: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    rotation_recommended: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    source_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    source_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )