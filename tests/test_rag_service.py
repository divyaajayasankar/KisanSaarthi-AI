from pathlib import Path
import json

import pytest

from app.services.rag_service import (
    build_rag_context,
    load_verified_knowledge,
    retrieve_verified_evidence,
)


@pytest.fixture()
def rag_file(
    tmp_path: Path,
) -> Path:

    data = [

        {
            "id": "rice_blast_001",
            "crop": "Rice",
            "topic": "Blast",
            "category": "disease_management",
            "text": (
                "Verified guidance for management "
                "of blast in rice."
            ),
            "source": "ICAR",
            "source_type": "ICAR",
            "source_url": "https://example.com/rice",
            "verified": True,
        },

        {
            "id": "groundnut_termite_001",
            "crop": "Groundnut",
            "topic": "Termite",
            "category": "pest_management",
            "text": (
                "Verified guidance for termite "
                "management in groundnut."
            ),
            "source": "ICAR",
            "source_type": "ICAR",
            "source_url": "https://example.com/groundnut",
            "verified": True,
        },

        {
            "id": "unverified_001",
            "crop": "Rice",
            "topic": "Blast",
            "category": "disease_management",
            "text": "Unverified test knowledge.",
            "source": "Unknown",
            "source_type": "Unknown",
            "source_url": "https://example.com/unverified",
            "verified": False,
        },
    ]


    file_path = (
        tmp_path
        / "knowledge_base.json"
    )


    file_path.write_text(
        json.dumps(
            data,
            indent=2,
        ),
        encoding="utf-8",
    )


    return file_path


def test_loads_only_verified_records(
    rag_file,
):

    records = load_verified_knowledge(
        rag_file
    )


    assert len(records) == 2

    assert all(
        record["verified"]
        is True
        for record in records
    )


def test_rice_blast_retrieval(
    rag_file,
):

    result = retrieve_verified_evidence(
        query="How can I manage blast in my rice crop?",
        crop="Rice",
        top_k=2,
        knowledge_base_path=rag_file,
    )


    assert (
        result["status"]
        == "retrieved"
    )


    assert (
        "rag_verified_evidence_retrieved"
        in result["fired_rules"]
    )


    assert (
        result["results"][0]["crop"]
        == "Rice"
    )


    assert (
        result["results"][0]["topic"]
        == "Blast"
    )


def test_groundnut_termite_retrieval(
    rag_file,
):

    result = retrieve_verified_evidence(
        query=(
            "What should I do about "
            "termite in groundnut?"
        ),
        crop="Groundnut",
        top_k=1,
        knowledge_base_path=rag_file,
    )


    assert (
        result["status"]
        == "retrieved"
    )


    assert len(
        result["results"]
    ) == 1


    assert (
        result["results"][0]["topic"]
        == "Termite"
    )


def test_empty_query_not_evaluated(
    rag_file,
):

    result = retrieve_verified_evidence(
        query="",
        crop="Rice",
        knowledge_base_path=rag_file,
    )


    assert (
        result["status"]
        == "not_evaluated"
    )


    assert (
        "rag_query_missing"
        in result["fired_rules"]
    )


def test_no_relevant_evidence(
    rag_file,
):

    result = retrieve_verified_evidence(
        query="banana micronutrient deficiency",
        crop="Banana",
        minimum_score=3.0,
        knowledge_base_path=rag_file,
    )


    assert (
        result["status"]
        == "no_evidence"
    )


    assert (
        "rag_no_verified_evidence"
        in result["fired_rules"]
    )


def test_build_rag_context(
    rag_file,
):

    retrieval = retrieve_verified_evidence(
        query="rice blast management",
        crop="Rice",
        top_k=1,
        knowledge_base_path=rag_file,
    )


    context = build_rag_context(
        retrieval
    )


    assert (
        "Evidence 1"
        in context
    )

    assert (
        "Rice"
        in context
    )

    assert (
        "Blast"
        in context
    )

    assert (
        "ICAR"
        in context
    )
