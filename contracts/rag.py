from pydantic import BaseModel, Field


class RetrievedDocument(BaseModel):
    doc_id: str
    title: str
    section: str
    version: str
    segment: str
    text: str
    score: float
    source_path: str
    citation: str
    retrieval_stage: str = "final"
    vector_score: float | None = None
    bm25_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


class RetrievalDebug(BaseModel):
    query: str
    filters: dict[str, str] = Field(default_factory=dict)
    mode: str = "hybrid-rerank"
    vector_ids: list[str] = Field(default_factory=list)
    bm25_ids: list[str] = Field(default_factory=list)
    fused_ids: list[str] = Field(default_factory=list)
    reranked_ids: list[str] = Field(default_factory=list)
    latency_ms: dict[str, float] = Field(default_factory=dict)
