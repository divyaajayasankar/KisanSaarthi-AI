from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

KNOWLEDGE_BASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "rag"
    / "knowledge_base.json"
)


def _normalize_text(
    value: str | None,
) -> str:
    """
    Convert text into a normalized lowercase form.
    """

    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value.strip().lower(),
    )


def _tokenize(
    value: str | None,
) -> set[str]:
    """
    Convert text into simple searchable tokens.
    """

    normalized = _normalize_text(
        value
    )

    if not normalized:
        return set()

    return set(
        re.findall(
            r"[a-z0-9]+",
            normalized,
        )
    )


def load_verified_knowledge(
    knowledge_base_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Load only verified agricultural knowledge records.
    """

    path = (
        knowledge_base_path
        or KNOWLEDGE_BASE_PATH
    )

    if not path.exists():

        raise FileNotFoundError(
            f"RAG knowledge base not found: {path}"
        )


    with path.open(
        "r",
        encoding="utf-8-sig",
    ) as file:

        data = json.load(
            file
        )


    if not isinstance(
        data,
        list,
    ):

        raise ValueError(
            "RAG knowledge base must contain a JSON list."
        )


    verified_records = []


    for record in data:

        if not isinstance(
            record,
            dict,
        ):
            continue


        if (
            record.get(
                "verified"
            )
            is True
        ):

            verified_records.append(
                record
            )


    return verified_records


def _score_record(
    record: dict[str, Any],
    crop: str | None,
    query: str,
) -> float:
    """
    Score a verified knowledge record.

    Strongest signals:
        exact crop match
        exact topic phrase match

    Additional signals:
        query-token overlap
        category/source overlap
    """

    score = 0.0


    normalized_crop = (
        _normalize_text(
            crop
        )
    )


    record_crop = (
        _normalize_text(
            record.get(
                "crop"
            )
        )
    )


    query_text = (
        _normalize_text(
            query
        )
    )


    topic = (
        _normalize_text(
            record.get(
                "topic"
            )
        )
    )


    category = (
        _normalize_text(
            record.get(
                "category"
            )
        )
    )


    evidence_text = (
        _normalize_text(
            record.get(
                "text"
            )
        )
    )


    source = (
        _normalize_text(
            record.get(
                "source"
            )
        )
    )


    # ========================================================
    # CROP MATCH SCORE
    # ========================================================

    if normalized_crop:

        if (
            normalized_crop
            ==
            record_crop
        ):

            score += 5.0


    # ========================================================
    # TOPIC MATCH SCORE
    # ========================================================

    if (
        topic
        and
        topic in query_text
    ):

        score += 6.0


    # ========================================================
    # TOKEN OVERLAP SCORE
    # ========================================================

    query_tokens = (
        _tokenize(
            query
        )
    )


    searchable_tokens = (
        _tokenize(
            " ".join(
                [
                    str(
                        record.get(
                            "crop",
                            "",
                        )
                    ),
                    str(
                        record.get(
                            "topic",
                            "",
                        )
                    ),
                    str(
                        record.get(
                            "category",
                            "",
                        )
                    ),
                    str(
                        record.get(
                            "text",
                            "",
                        )
                    ),
                    str(
                        record.get(
                            "source",
                            "",
                        )
                    ),
                ]
            )
        )
    )


    overlap = (
        query_tokens
        &
        searchable_tokens
    )


    score += float(
        len(
            overlap
        )
    )


    # ========================================================
    # SMALL BOOSTS
    # ========================================================

    if (
        category
        and
        category in query_text
    ):

        score += 1.0


    if (
        source
        and
        source in query_text
    ):

        score += 0.5


    if (
        evidence_text
        and
        query_text in evidence_text
    ):

        score += 1.0


    return score


def retrieve_verified_evidence(
    query: str,
    crop: str | None = None,
    top_k: int = 3,
    minimum_score: float = 1.0,
    knowledge_base_path: Path | None = None,
) -> dict[str, Any]:
    """
    Retrieve verified agricultural evidence relevant
    to the farmer query.

    Important:
        If a crop is supplied, retrieval is STRICTLY
        restricted to that crop.

    The RAG retriever does NOT make pesticide safety
    decisions. Safety decisions remain in the
    deterministic advisory pipeline.
    """


    # ========================================================
    # VALIDATE QUERY
    # ========================================================

    if (
        not query
        or
        not query.strip()
    ):

        return {
            "status":
                "not_evaluated",

            "query":
                query,

            "crop":
                crop,

            "results":
                [],

            "fired_rules": [
                "rag_query_missing"
            ],

            "explanation": (
                "Verified agricultural knowledge retrieval "
                "was not performed because no query was provided."
            ),
        }


    # ========================================================
    # VALIDATE TOP K
    # ========================================================

    if top_k <= 0:

        return {
            "status":
                "not_evaluated",

            "query":
                query,

            "crop":
                crop,

            "results":
                [],

            "fired_rules": [
                "rag_invalid_top_k"
            ],

            "explanation": (
                "Verified agricultural knowledge retrieval "
                "was not performed because top_k must be positive."
            ),
        }


    # ========================================================
    # LOAD VERIFIED KNOWLEDGE
    # ========================================================

    verified_records = (
        load_verified_knowledge(
            knowledge_base_path
        )
    )


    # ========================================================
    # STRICT CROP FILTER
    # ========================================================
    #
    # Example:
    #
    # Crop = Rice
    #
    # Allowed:
    #   Rice -> Blast
    #   Rice -> Sheath blight
    #
    # Removed:
    #   Groundnut -> Termite
    #   Groundnut -> White grub
    #
    # This prevents unrelated crops from appearing simply
    # because some generic words overlap with the query.
    # ========================================================

    normalized_crop = (
        _normalize_text(
            crop
        )
    )


    if normalized_crop:

        verified_records = [

            record

            for record
            in verified_records

            if (
                _normalize_text(
                    record.get(
                        "crop"
                    )
                )
                ==
                normalized_crop
            )
        ]


        # ----------------------------------------------------
        # NO VERIFIED RECORD EXISTS FOR REQUESTED CROP
        # ----------------------------------------------------

        if not verified_records:

            return {
                "status":
                    "no_evidence",

                "query":
                    query,

                "crop":
                    crop,

                "results":
                    [],

                "fired_rules": [
                    "rag_crop_filter_applied",
                    "rag_no_verified_evidence",
                ],

                "explanation": (
                    f"No verified agricultural evidence "
                    f"was found for crop '{crop}'."
                ),
            }


    # ========================================================
    # TOPIC-AWARE FILTER
    # ========================================================
    #
    # If the user's query explicitly contains one of the
    # topics available for the selected crop, prefer only
    # those records.
    #
    # Example:
    #
    # Query:
    #   "How can I manage blast in my rice crop?"
    #
    # Rice records:
    #   Blast        -> retained
    #   Sheath blight -> removed
    #
    # If no topic can be confidently matched, the normal
    # scoring stage is still used.
    # ========================================================

    query_tokens = (
        _tokenize(
            query
        )
    )


    topic_matched_records = []


    for record in verified_records:

        topic_tokens = (
            _tokenize(
                record.get(
                    "topic"
                )
            )
        )


        if (
            topic_tokens
            and
            query_tokens.intersection(
                topic_tokens
            )
        ):

            topic_matched_records.append(
                record
            )


    if topic_matched_records:

        verified_records = (
            topic_matched_records
        )


    # ========================================================
    # SCORE FILTERED RECORDS
    # ========================================================

    scored_records = []


    for record in verified_records:

        score = (
            _score_record(
                record=record,
                crop=crop,
                query=query,
            )
        )


        if (
            score
            >=
            minimum_score
        ):

            scored_records.append(
                {
                    "score":
                        score,

                    "id":
                        record.get(
                            "id"
                        ),

                    "crop":
                        record.get(
                            "crop"
                        ),

                    "topic":
                        record.get(
                            "topic"
                        ),

                    "category":
                        record.get(
                            "category"
                        ),

                    "text":
                        record.get(
                            "text"
                        ),

                    "source":
                        record.get(
                            "source"
                        ),

                    "source_type":
                        record.get(
                            "source_type"
                        ),

                    "source_url":
                        record.get(
                            "source_url"
                        ),

                    "verified":
                        record.get(
                            "verified"
                        ),
                }
            )


    # ========================================================
    # SORT BEST MATCH FIRST
    # ========================================================

    scored_records.sort(
        key=lambda item: (
            -item["score"],
            str(
                item.get(
                    "id"
                )
                or
                ""
            ),
        )
    )


    results = (
        scored_records[
            :top_k
        ]
    )


    # ========================================================
    # NO RELEVANT EVIDENCE
    # ========================================================

    if not results:

        fired_rules = []


        if normalized_crop:

            fired_rules.append(
                "rag_crop_filter_applied"
            )


        fired_rules.append(
            "rag_no_verified_evidence"
        )


        return {
            "status":
                "no_evidence",

            "query":
                query,

            "crop":
                crop,

            "results":
                [],

            "fired_rules":
                fired_rules,

            "explanation": (
                "No sufficiently relevant verified agricultural "
                "evidence was found for the farmer query."
            ),
        }


    # ========================================================
    # SUCCESS
    # ========================================================

    fired_rules = []


    if normalized_crop:

        fired_rules.append(
            "rag_crop_filter_applied"
        )


    if topic_matched_records:

        fired_rules.append(
            "rag_topic_filter_applied"
        )


    fired_rules.append(
        "rag_verified_evidence_retrieved"
    )


    return {
        "status":
            "retrieved",

        "query":
            query,

        "crop":
            crop,

        "results":
            results,

        "fired_rules":
            fired_rules,

        "explanation": (
            f"Retrieved {len(results)} verified agricultural "
            "evidence item(s) relevant to the farmer query."
        ),
    }


def build_rag_context(
    retrieval_result: dict[str, Any],
) -> str:
    """
    Convert retrieved records into a compact context block
    that can later be supplied to the agent / LLM.
    """

    results = (
        retrieval_result.get(
            "results",
            [],
        )
    )


    if not results:
        return ""


    context_parts = []


    for index, item in enumerate(
        results,
        start=1,
    ):

        context_parts.append(
            "\n".join(
                [
                    f"Evidence {index}",

                    (
                        f"Crop: "
                        f"{item.get('crop')}"
                    ),

                    (
                        f"Topic: "
                        f"{item.get('topic')}"
                    ),

                    (
                        f"Source: "
                        f"{item.get('source')}"
                    ),

                    (
                        f"Source Type: "
                        f"{item.get('source_type')}"
                    ),

                    (
                        f"Evidence: "
                        f"{item.get('text')}"
                    ),

                    (
                        f"Source URL: "
                        f"{item.get('source_url')}"
                    ),
                ]
            )
        )


    return "\n\n".join(
        context_parts
    )
