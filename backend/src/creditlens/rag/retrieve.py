from __future__ import annotations

import time
from functools import lru_cache
from typing import Literal

from contracts.application import Application
from contracts.rag import RetrievalDebug, RetrievedDocument
from rank_bm25 import BM25Okapi

from creditlens.rag.documents import KnowledgeDoc, load_documents
from creditlens.rag.embeddings import cosine, embed_query, embed_texts

RAG_VERSION = "hybrid-v1"
RetrievalMode = Literal["vector", "hybrid", "hybrid-rerank"]


@lru_cache(maxsize=1)
def _index() -> tuple[list[KnowledgeDoc], list[list[float]], BM25Okapi, list[list[str]]]:
    docs = load_documents()
    texts = [f"{doc.title}\n{doc.text}" for doc in docs]
    vectors = embed_texts(texts)
    tokens = [text.lower().split() for text in texts]
    bm25 = BM25Okapi(tokens)
    return docs, vectors, bm25, tokens


def _filter_docs(docs: list[KnowledgeDoc], segment: str) -> list[int]:
    return [i for i, doc in enumerate(docs) if doc.segment in {segment, "all"}]


def _rrf(rank_lists: list[list[int]], k: int = 60) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranks in rank_lists:
        for rank, idx in enumerate(ranks):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return scores


def _local_rerank(query: str, docs: list[KnowledgeDoc], candidates: list[int]) -> list[tuple[int, float]]:
    q_tokens = set(query.lower().split())
    scored: list[tuple[int, float]] = []
    for idx in candidates:
        text = f"{docs[idx].title} {docs[idx].section} {docs[idx].text}".lower()
        overlap = len(q_tokens.intersection(text.split()))
        section_bonus = 0.4 if any(tok in docs[idx].section for tok in q_tokens) else 0.0
        scored.append((idx, overlap + section_bonus))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def build_query(app: Application, extra: str = "", *, naive: bool = False) -> str:
    if naive:
        return f"сегмент {app.segment} сумма {app.requested_amount} {extra}".strip()
    parts = [
        f"сегмент {app.segment}",
        f"долговая нагрузка {app.debt_to_revenue}",
        f"сумма {app.requested_amount}",
        f"срок {app.requested_term}",
        f"просрочки 30 {app.overdue_30d_count}",
        f"просрочки 90 {app.overdue_90d_count}",
        "кредитная политика лимиты исключения ручное рассмотрение SHAP методика",
        extra,
    ]
    return " ".join(parts)


def _to_document(
    docs: list[KnowledgeDoc],
    idx: int,
    *,
    score: float,
    q_vec: list[float],
    vectors: list[list[float]],
    bm25_scores: list[float] | None,
    fused: dict[int, float],
    rerank_score: float | None,
    stage: str,
) -> RetrievedDocument:
    return RetrievedDocument(
        doc_id=docs[idx].doc_id,
        title=docs[idx].title,
        section=docs[idx].section,
        version=docs[idx].version,
        segment=docs[idx].segment,
        text=docs[idx].text[:1200],
        score=round(float(score), 4),
        source_path=docs[idx].source_path,
        citation=docs[idx].citation,
        retrieval_stage=stage,
        vector_score=round(cosine(q_vec, vectors[idx]), 4),
        bm25_score=round(float(bm25_scores[idx]), 4) if bm25_scores is not None else None,
        rrf_score=round(float(fused.get(idx, 0.0)), 4) if fused else None,
        rerank_score=round(float(rerank_score), 4) if rerank_score is not None else None,
    )


def retrieve_policy(
    app: Application,
    extra_query: str = "",
    top_k: int = 4,
    mode: RetrievalMode | str = "hybrid-rerank",
) -> tuple[list[RetrievedDocument], RetrievalDebug]:
    docs, vectors, bm25, _tokens = _index()
    query = build_query(app, extra_query, naive=mode == "vector")
    allowed = _filter_docs(docs, app.segment)
    debug = RetrievalDebug(query=query, filters={"segment": app.segment}, mode=str(mode))

    t0 = time.perf_counter()
    q_vec = embed_query(query)
    vector_ranked = sorted(
        allowed,
        key=lambda idx: cosine(q_vec, vectors[idx]),
        reverse=True,
    )
    debug.latency_ms["vector"] = round((time.perf_counter() - t0) * 1000, 2)
    debug.vector_ids = [docs[i].doc_id for i in vector_ranked[:10]]

    if mode == "vector":
        chosen = vector_ranked[:top_k]
        results = [
            _to_document(
                docs,
                idx,
                score=cosine(q_vec, vectors[idx]),
                q_vec=q_vec,
                vectors=vectors,
                bm25_scores=None,
                fused={},
                rerank_score=None,
                stage="vector",
            )
            for idx in chosen
        ]
        return results, debug

    t1 = time.perf_counter()
    bm25_scores = bm25.get_scores(query.lower().split())
    bm25_ranked = sorted(allowed, key=lambda idx: float(bm25_scores[idx]), reverse=True)
    debug.latency_ms["bm25"] = round((time.perf_counter() - t1) * 1000, 2)
    debug.bm25_ids = [docs[i].doc_id for i in bm25_ranked[:10]]

    t2 = time.perf_counter()
    fused = _rrf([vector_ranked[:10], bm25_ranked[:10]])
    fused_ranked = [idx for idx, _ in sorted(fused.items(), key=lambda item: item[1], reverse=True)]
    debug.latency_ms["rrf"] = round((time.perf_counter() - t2) * 1000, 2)
    debug.fused_ids = [docs[i].doc_id for i in fused_ranked[:10]]

    if mode == "hybrid":
        chosen = fused_ranked[:top_k]
        debug.reranked_ids = []
        results = [
            _to_document(
                docs,
                idx,
                score=float(fused.get(idx, 0.0)),
                q_vec=q_vec,
                vectors=vectors,
                bm25_scores=list(bm25_scores),
                fused=fused,
                rerank_score=None,
                stage="rrf",
            )
            for idx in chosen
        ]
        return results, debug

    t3 = time.perf_counter()
    reranked = _local_rerank(query, docs, fused_ranked[:10])
    debug.latency_ms["rerank"] = round((time.perf_counter() - t3) * 1000, 2)
    debug.reranked_ids = [docs[i].doc_id for i, _ in reranked[:top_k]]

    results = [
        _to_document(
            docs,
            idx,
            score=float(fused.get(idx, 0.0) + rerank_score),
            q_vec=q_vec,
            vectors=vectors,
            bm25_scores=list(bm25_scores),
            fused=fused,
            rerank_score=rerank_score,
            stage="rerank",
        )
        for idx, rerank_score in reranked[:top_k]
    ]
    return results, debug


def knowledge_stats() -> dict:
    docs = load_documents()
    return {"documents": len(docs), "rag_version": RAG_VERSION, "ready": len(docs) > 0, "backend": "in-memory"}
