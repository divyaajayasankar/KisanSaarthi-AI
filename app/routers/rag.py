from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.services.rag_service import (
    build_rag_context,
    retrieve_verified_evidence,
)


router = APIRouter(
    prefix="/api/rag",
    tags=["rag"],
)


class RAGSearchRequest(BaseModel):

    query: str = Field(
        ...,
        min_length=1,
    )

    crop: str | None = None

    top_k: int = Field(
        default=3,
        ge=1,
        le=5,
    )


@router.post("/search")
def search_verified_agricultural_knowledge(
    request: RAGSearchRequest,
):

    retrieval = retrieve_verified_evidence(
        query=request.query,
        crop=request.crop,
        top_k=request.top_k,
    )

    context = build_rag_context(
        retrieval
    )

    return {
        **retrieval,
        "rag_context": context,
    }