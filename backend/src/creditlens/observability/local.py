from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from contracts.observability import Span, SpanEvent, Trace

from creditlens.db import DB_LOCK, get_conn


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _span_status(value: str | None) -> str:
    return value if value in {"running", "ok", "error"} else "ok"


class LocalObservability:
    name = "local"

    def start_trace(self, run_id: str, name: str, metadata: dict[str, Any]) -> str:
        trace_id = str(uuid.uuid4())
        with DB_LOCK:
            conn = get_conn()
            conn.execute(
                """
                INSERT INTO traces(trace_id, run_id, name, started_at, ended_at, duration_ms, status, metadata_json)
                VALUES (?, ?, ?, ?, NULL, NULL, 'running', ?)
                """,
                (trace_id, run_id, name, _iso(_now()), json.dumps(metadata, ensure_ascii=False)),
            )
            conn.commit()
        return trace_id

    def start_span(
        self,
        trace_id: str,
        name: str,
        *,
        parent_span_id: str | None = None,
        kind: str = "chain",
        attributes: dict[str, Any] | None = None,
        code_path: str | None = None,
        mmd_node: str | None = None,
    ) -> str:
        span_id = str(uuid.uuid4())
        with DB_LOCK:
            conn = get_conn()
            conn.execute(
                """
                INSERT INTO spans(
                    span_id, trace_id, parent_span_id, name, kind, status, started_at,
                    ended_at, duration_ms, attributes_json, error, code_path, mmd_node
                ) VALUES (?, ?, ?, ?, ?, 'running', ?, NULL, NULL, ?, NULL, ?, ?)
                """,
                (
                    span_id,
                    trace_id,
                    parent_span_id,
                    name,
                    kind,
                    _iso(_now()),
                    json.dumps(attributes or {}, ensure_ascii=False),
                    code_path,
                    mmd_node,
                ),
            )
            conn.commit()
        return span_id

    def end_span(self, span_id: str, status: str = "ok", error: str | None = None) -> None:
        status = _span_status(status)
        with DB_LOCK:
            conn = get_conn()
            row = conn.execute("SELECT started_at FROM spans WHERE span_id=?", (span_id,)).fetchone()
            ended = _now()
            duration = None
            if row:
                started = datetime.fromisoformat(row["started_at"])
                duration = (ended - started).total_seconds() * 1000
            conn.execute(
                "UPDATE spans SET status=?, ended_at=?, duration_ms=?, error=? WHERE span_id=?",
                (status, _iso(ended), duration, error, span_id),
            )
            conn.commit()

    def event(self, span_id: str, name: str, payload: dict[str, Any] | None = None) -> None:
        with DB_LOCK:
            conn = get_conn()
            conn.execute(
                "INSERT INTO span_events(span_id, timestamp, name, payload_json) VALUES (?, ?, ?, ?)",
                (span_id, _iso(_now()), name, json.dumps(payload or {}, ensure_ascii=False)),
            )
            conn.commit()

    def generation(
        self,
        span_id: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        input_preview: str = "",
        output_preview: str = "",
    ) -> None:
        with DB_LOCK:
            conn = get_conn()
            conn.execute(
                """
                INSERT INTO generations(span_id, model, prompt_tokens, completion_tokens, input_preview, output_preview)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (span_id, model, prompt_tokens, completion_tokens, input_preview[:2000], output_preview[:2000]),
            )
            conn.commit()

    def end_trace(self, trace_id: str, status: str = "ok") -> None:
        with DB_LOCK:
            conn = get_conn()
            row = conn.execute("SELECT started_at FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
            ended = _now()
            duration = None
            if row:
                started = datetime.fromisoformat(row["started_at"])
                duration = (ended - started).total_seconds() * 1000
            conn.execute(
                "UPDATE traces SET status=?, ended_at=?, duration_ms=? WHERE trace_id=?",
                (status, _iso(ended), duration, trace_id),
            )
            conn.commit()

    def get_trace(self, trace_id: str) -> Trace | None:
        with DB_LOCK:
            conn = get_conn()
            row = conn.execute("SELECT * FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
            if not row:
                return None
            return self._hydrate(row)

    def get_trace_by_run(self, run_id: str) -> Trace | None:
        with DB_LOCK:
            conn = get_conn()
            row = conn.execute(
                "SELECT * FROM traces WHERE run_id=? ORDER BY started_at DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            if not row:
                return None
            return self._hydrate(row)

    def list_traces(self, limit: int = 30) -> list[Trace]:
        with DB_LOCK:
            conn = get_conn()
            rows = conn.execute(
                "SELECT * FROM traces ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._hydrate(row) for row in rows]

    def _hydrate(self, row: Any) -> Trace:
        conn = get_conn()
        span_rows = conn.execute(
            "SELECT * FROM spans WHERE trace_id=? ORDER BY started_at",
            (row["trace_id"],),
        ).fetchall()
        spans: list[Span] = []
        for span in span_rows:
            events = [
                SpanEvent(
                    timestamp=datetime.fromisoformat(ev["timestamp"]),
                    name=ev["name"],
                    payload=json.loads(ev["payload_json"]),
                )
                for ev in conn.execute(
                    "SELECT * FROM span_events WHERE span_id=? ORDER BY id",
                    (span["span_id"],),
                ).fetchall()
            ]
            spans.append(
                Span(
                    span_id=span["span_id"],
                    trace_id=span["trace_id"],
                    parent_span_id=span["parent_span_id"],
                    name=span["name"],
                    kind=span["kind"],
                    status=_span_status(span["status"]),
                    started_at=datetime.fromisoformat(span["started_at"]),
                    ended_at=datetime.fromisoformat(span["ended_at"]) if span["ended_at"] else None,
                    duration_ms=span["duration_ms"],
                    attributes=json.loads(span["attributes_json"]),
                    events=events,
                    error=span["error"],
                    code_path=span["code_path"],
                    mmd_node=span["mmd_node"],
                )
            )
        return Trace(
            trace_id=row["trace_id"],
            run_id=row["run_id"],
            name=row["name"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            duration_ms=row["duration_ms"],
            status=_span_status(row["status"]),
            metadata=json.loads(row["metadata_json"]),
            spans=spans,
        )
