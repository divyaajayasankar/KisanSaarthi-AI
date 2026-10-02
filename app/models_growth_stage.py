from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
)

from app.db import Base


class GrowthStageRule(Base):

    __tablename__ = "growth_stage_rules"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    crop = Column(
        String,
        nullable=False,
        index=True,
    )

    pest = Column(
        String,
        nullable=False,
        index=True,
    )

    active_ingredient = Column(
        String,
        nullable=False,
        index=True,
    )

    allowed_stages = Column(
        String,
        nullable=False,
    )

    application_timing = Column(
        Text,
        nullable=False,
    )

    source_document = Column(
        Text,
        nullable=False,
    )

    source_page = Column(
        Integer,
        nullable=False,
    )

    source_url = Column(
        Text,
        nullable=False,
    )

    source_date = Column(
        String,
        nullable=False,
    )

    verified = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )