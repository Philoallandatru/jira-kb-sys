from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from app.models import (
    DailyAIAnalysis,
    DocChunk,
    IssueChangeEvent,
    IssueAIAnalysis,
    IssueDelta,
    IssueRecord,
    ManagementSummaryMetrics,
    ManagementSummaryRequest,
    ManagementSummaryResult,
)
from app.retrieval.schema import RetrievalResult


class Repository:
    def __init__(self, database_path: str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_type TEXT NOT NULL,
                    run_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    payload_json TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS issues_current (
                    issue_key TEXT PRIMARY KEY,
                    snapshot_date TEXT NOT NULL,
                    data_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS issues_daily_snapshot (
                    snapshot_date TEXT NOT NULL,
                    issue_key TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    PRIMARY KEY (snapshot_date, issue_key)
                );
                CREATE TABLE IF NOT EXISTS issue_events_derived (
                    snapshot_date TEXT NOT NULL,
                    issue_key TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    PRIMARY KEY (snapshot_date, issue_key, change_type)
                );
                CREATE TABLE IF NOT EXISTS issue_change_events (
                    event_id TEXT PRIMARY KEY,
                    issue_key TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    field TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    data_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS doc_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    source_id TEXT,
                    source_path TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    doc_title TEXT NOT NULL,
                    section_path_json TEXT NOT NULL,
                    heading_path_json TEXT,
                    page_or_sheet TEXT,
                    page_title TEXT,
                    space_key TEXT,
                    page_id TEXT,
                    ancestor_titles_json TEXT,
                    labels_json TEXT,
                    authors_json TEXT,
                    comment_snippets_json TEXT,
                    content TEXT NOT NULL,
                    raw_text TEXT,
                    context_prefix TEXT,
                    retrieval_text TEXT,
                    exact_terms_json TEXT,
                    tags_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT
                );
                CREATE TABLE IF NOT EXISTS retrieval_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    query_type TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS retrieval_candidates (
                    retrieval_run_id INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    rank INTEGER NOT NULL,
                    chunk_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    score REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (retrieval_run_id, stage, rank)
                );
                CREATE TABLE IF NOT EXISTS qa_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    issue_key TEXT,
                    selected_chunk_ids_json TEXT NOT NULL,
                    root_cause TEXT,
                    accepted INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS ai_analysis_daily (
                    report_date TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ai_analysis_issue (
                    report_date TEXT NOT NULL,
                    issue_key TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    PRIMARY KEY (report_date, issue_key)
                );
                CREATE TABLE IF NOT EXISTS ai_management_summary (
                    run_id INTEGER PRIMARY KEY,
                    request_json TEXT NOT NULL,
                    data_json TEXT NOT NULL
                );
                """
            )
            self._ensure_column(conn, "runs", "payload_json", "TEXT")
            self._ensure_column(conn, "runs", "attempt_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "runs", "last_error", "TEXT")
            self._ensure_column(conn, "runs", "started_at", "TEXT")
            self._ensure_column(conn, "runs", "finished_at", "TEXT")
            self._ensure_column(conn, "doc_chunks", "source_id", "TEXT")
            self._ensure_column(conn, "doc_chunks", "heading_path_json", "TEXT")
            self._ensure_column(conn, "doc_chunks", "page_title", "TEXT")
            self._ensure_column(conn, "doc_chunks", "space_key", "TEXT")
            self._ensure_column(conn, "doc_chunks", "page_id", "TEXT")
            self._ensure_column(conn, "doc_chunks", "ancestor_titles_json", "TEXT")
            self._ensure_column(conn, "doc_chunks", "labels_json", "TEXT")
            self._ensure_column(conn, "doc_chunks", "authors_json", "TEXT")
            self._ensure_column(conn, "doc_chunks", "comment_snippets_json", "TEXT")
            self._ensure_column(conn, "doc_chunks", "raw_text", "TEXT")
            self._ensure_column(conn, "doc_chunks", "context_prefix", "TEXT")
            self._ensure_column(conn, "doc_chunks", "retrieval_text", "TEXT")
            self._ensure_column(conn, "doc_chunks", "exact_terms_json", "TEXT")
            self._ensure_column(conn, "doc_chunks", "metadata_json", "TEXT")
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {row["name"] for row in rows}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def create_run(
        self,
        run_type: str,
        run_date: str,
        status: str,
        details: str = "",
        payload: dict | None = None,
    ) -> int:
        started_at = datetime.utcnow().replace(microsecond=0).isoformat() if status == "running" else None
        finished_at = datetime.utcnow().replace(microsecond=0).isoformat() if status in {"success", "failed", "cancelled"} else None
        attempt_count = 1 if status == "running" else 0
        last_error = details if status == "failed" and details else None
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO runs (
                    run_type, run_date, status, details, payload_json, attempt_count, last_error, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_type,
                    run_date,
                    status,
                    details,
                    json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                    attempt_count,
                    last_error,
                    started_at,
                    finished_at,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def update_run(self, run_id: int, status: str, details: str = "") -> None:
        with self.connect() as conn:
            if status == "running":
                conn.execute(
                    """
                    UPDATE runs
                    SET status = ?,
                        details = ?,
                        started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                        finished_at = NULL,
                        attempt_count = CASE WHEN attempt_count <= 0 THEN 1 ELSE attempt_count END
                    WHERE id = ?
                    """,
                    (status, details, run_id),
                )
            elif status in {"success", "failed", "cancelled"}:
                conn.execute(
                    """
                    UPDATE runs
                    SET status = ?,
                        details = ?,
                        finished_at = CURRENT_TIMESTAMP,
                        last_error = CASE WHEN ? = 'failed' THEN ? ELSE last_error END
                    WHERE id = ?
                    """,
                    (status, details, status, details, run_id),
                )
            else:
                conn.execute("UPDATE runs SET status = ?, details = ? WHERE id = ?", (status, details, run_id))
            conn.commit()

    def requeue_running_runs(self, reason: str) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE runs
                SET status = 'queued',
                    details = ?,
                    finished_at = NULL
                WHERE status = 'running'
                """,
                (reason,),
            )
            conn.commit()
            return int(cursor.rowcount)

    def schedule_retry(self, run_id: int, error: str, max_attempts: int) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT attempt_count FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                return False
            attempt_count = int(row["attempt_count"] or 0)
            if attempt_count >= max_attempts:
                conn.execute(
                    """
                    UPDATE runs
                    SET status = 'failed',
                        details = ?,
                        last_error = ?,
                        finished_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (error, error, run_id),
                )
                conn.commit()
                return False
            conn.execute(
                """
                UPDATE runs
                SET status = 'queued',
                    details = ?,
                    last_error = ?,
                    finished_at = NULL
                WHERE id = ?
                """,
                (f"Retry scheduled after attempt {attempt_count}/{max_attempts}: {error}", error, run_id),
                )
            conn.commit()
            return True

    def claim_next_queued_run(self) -> dict[str, str | int | None] | None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT id, run_type, run_date, status, details, payload_json, attempt_count, last_error, created_at, started_at, finished_at
                FROM runs
                WHERE status = 'queued'
                ORDER BY id ASC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                conn.commit()
                return None
            conn.execute(
                """
                UPDATE runs
                SET status = 'running',
                    started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                    finished_at = NULL,
                    attempt_count = attempt_count + 1
                WHERE id = ? AND status = 'queued'
                """,
                (row["id"],),
            )
            conn.commit()
        claimed = dict(row)
        claimed["status"] = "running"
        claimed["attempt_count"] = int(claimed.get("attempt_count") or 0) + 1
        if claimed.get("started_at") is None:
            claimed["started_at"] = datetime.utcnow().replace(microsecond=0).isoformat()
        return claimed

    def list_runs(self, limit: int = 50) -> list[dict[str, str | int | None]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, run_type, run_date, status, details, payload_json, attempt_count, last_error, created_at, started_at, finished_at
                FROM runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def load_run(self, run_id: int) -> dict[str, str | int | None] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, run_type, run_date, status, details, payload_json, attempt_count, last_error, created_at, started_at, finished_at
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def save_daily_snapshot(self, snapshot_date: str, issues: list[IssueRecord]) -> None:
        with self.connect() as conn:
            for issue in issues:
                payload = json.dumps(issue.to_dict(), ensure_ascii=False)
                conn.execute(
                    "INSERT OR REPLACE INTO issues_daily_snapshot (snapshot_date, issue_key, data_json) VALUES (?, ?, ?)",
                    (snapshot_date, issue.issue_key, payload),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO issues_current (issue_key, snapshot_date, data_json) VALUES (?, ?, ?)",
                    (issue.issue_key, snapshot_date, payload),
                )
            conn.commit()

    def load_snapshot(self, snapshot_date: str) -> list[IssueRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT data_json FROM issues_daily_snapshot WHERE snapshot_date = ? ORDER BY issue_key",
                (snapshot_date,),
            ).fetchall()
        return [IssueRecord(**json.loads(row["data_json"])) for row in rows]

    def load_current_issues(self) -> list[IssueRecord]:
        with self.connect() as conn:
            rows = conn.execute("SELECT data_json FROM issues_current ORDER BY issue_key").fetchall()
        return [IssueRecord(**json.loads(row["data_json"])) for row in rows]

    def load_issue(self, issue_key: str, snapshot_date: str | None = None) -> IssueRecord | None:
        if snapshot_date:
            with self.connect() as conn:
                row = conn.execute(
                    "SELECT data_json FROM issues_daily_snapshot WHERE snapshot_date = ? AND issue_key = ?",
                    (snapshot_date, issue_key),
                ).fetchone()
        else:
            with self.connect() as conn:
                row = conn.execute(
                    "SELECT data_json FROM issues_current WHERE issue_key = ?",
                    (issue_key,),
                ).fetchone()
        return IssueRecord(**json.loads(row["data_json"])) if row else None

    def get_previous_snapshot_date(self, snapshot_date: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT snapshot_date FROM issues_daily_snapshot WHERE snapshot_date < ? ORDER BY snapshot_date DESC LIMIT 1",
                (snapshot_date,),
            ).fetchone()
        return row["snapshot_date"] if row else None

    def save_deltas(self, snapshot_date: str, deltas: list[IssueDelta]) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM issue_events_derived WHERE snapshot_date = ?", (snapshot_date,))
            for delta in deltas:
                conn.execute(
                    "INSERT OR REPLACE INTO issue_events_derived (snapshot_date, issue_key, change_type, details_json) VALUES (?, ?, ?, ?)",
                    (snapshot_date, delta.issue_key, delta.change_type, json.dumps(delta.to_dict(), ensure_ascii=False)),
                )
            conn.commit()

    def load_deltas(self, snapshot_date: str) -> list[IssueDelta]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT details_json FROM issue_events_derived WHERE snapshot_date = ? ORDER BY issue_key",
                (snapshot_date,),
            ).fetchall()
        return [IssueDelta(**json.loads(row["details_json"])) for row in rows]

    def save_change_events(self, events: list[IssueChangeEvent]) -> None:
        with self.connect() as conn:
            for event in events:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO issue_change_events (
                        event_id, issue_key, changed_at, field, change_type, data_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.issue_key,
                        event.changed_at,
                        event.field,
                        event.change_type,
                        json.dumps(event.to_dict(), ensure_ascii=False),
                    ),
                )
            conn.commit()

    def load_change_events_in_range(self, date_from: str, date_to: str) -> list[IssueChangeEvent]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT data_json
                FROM issue_change_events
                WHERE substr(changed_at, 1, 10) >= ? AND substr(changed_at, 1, 10) <= ?
                ORDER BY changed_at, issue_key
                """,
                (date_from, date_to),
            ).fetchall()
        return [IssueChangeEvent(**json.loads(row["data_json"])) for row in rows]

    def load_deltas_in_range(self, date_from: str, date_to: str) -> list[IssueDelta]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT details_json
                FROM issue_events_derived
                WHERE snapshot_date >= ? AND snapshot_date <= ?
                ORDER BY snapshot_date, issue_key
                """,
                (date_from, date_to),
            ).fetchall()
        return [IssueDelta(**json.loads(row["details_json"])) for row in rows]

    def save_doc_chunks(self, chunks: list[DocChunk]) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM doc_chunks")
            for chunk in chunks:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO doc_chunks (
                        chunk_id, source_id, source_path, source_type, doc_title, section_path_json,
                        heading_path_json, page_or_sheet, page_title, space_key, page_id, ancestor_titles_json,
                        labels_json, authors_json, comment_snippets_json, content, raw_text, context_prefix,
                        retrieval_text, exact_terms_json, tags_json, updated_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.source_id,
                        chunk.source_path,
                        chunk.source_type,
                        chunk.doc_title,
                        json.dumps(chunk.section_path, ensure_ascii=False),
                        json.dumps(chunk.heading_path, ensure_ascii=False),
                        chunk.page_or_sheet,
                        chunk.page_title,
                        chunk.space_key,
                        chunk.page_id,
                        json.dumps(chunk.ancestor_titles, ensure_ascii=False),
                        json.dumps(chunk.labels, ensure_ascii=False),
                        json.dumps(chunk.authors, ensure_ascii=False),
                        json.dumps(chunk.comment_snippets, ensure_ascii=False),
                        chunk.content,
                        chunk.raw_text,
                        chunk.context_prefix,
                        chunk.retrieval_text,
                        json.dumps(chunk.exact_terms, ensure_ascii=False),
                        json.dumps(chunk.tags, ensure_ascii=False),
                        chunk.updated_at,
                        json.dumps(chunk.metadata_json, ensure_ascii=False),
                    ),
                )
            conn.commit()

    def load_doc_chunks(self) -> list[DocChunk]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM doc_chunks ORDER BY doc_title, chunk_id").fetchall()
        return [
            DocChunk(
                chunk_id=row["chunk_id"],
                source_id=row["source_id"] or row["source_path"] or row["chunk_id"],
                source_path=row["source_path"],
                source_type=row["source_type"],
                doc_title=row["doc_title"],
                section_path=json.loads(row["section_path_json"]),
                heading_path=json.loads(row["heading_path_json"]) if row["heading_path_json"] else json.loads(row["section_path_json"]),
                page_or_sheet=row["page_or_sheet"],
                page_title=row["page_title"] or row["doc_title"],
                space_key=row["space_key"],
                page_id=row["page_id"],
                ancestor_titles=json.loads(row["ancestor_titles_json"]) if row["ancestor_titles_json"] else [],
                labels=json.loads(row["labels_json"]) if row["labels_json"] else [],
                authors=json.loads(row["authors_json"]) if row["authors_json"] else [],
                comment_snippets=json.loads(row["comment_snippets_json"]) if row["comment_snippets_json"] else [],
                content=row["content"],
                raw_text=row["raw_text"] or row["content"],
                context_prefix=row["context_prefix"] or "",
                retrieval_text=row["retrieval_text"] or row["content"],
                exact_terms=json.loads(row["exact_terms_json"]) if row["exact_terms_json"] else [],
                tags=json.loads(row["tags_json"]),
                updated_at=row["updated_at"],
                metadata_json=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            )
            for row in rows
        ]

    def save_retrieval_run(self, result: RetrievalResult) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO retrieval_runs (question, query_type, plan_json, result_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    result.question,
                    result.query_type,
                    json.dumps(result.plan, ensure_ascii=False),
                    json.dumps(
                        {
                            "bm25": [item.chunk.chunk_id for item in result.bm25_candidates],
                            "dense": [item.chunk.chunk_id for item in result.dense_candidates],
                            "fused": [item.chunk.chunk_id for item in result.fused_candidates],
                            "reranked": [item.chunk.chunk_id for item in result.reranked_candidates],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            retrieval_run_id = int(cursor.lastrowid)
            for stage_name, candidates in (
                ("bm25", result.bm25_candidates),
                ("dense", result.dense_candidates),
                ("fused", result.fused_candidates),
                ("reranked", result.reranked_candidates),
            ):
                for rank, item in enumerate(candidates, start=1):
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO retrieval_candidates (
                            retrieval_run_id, stage, rank, chunk_id, source_type, score, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            retrieval_run_id,
                            stage_name,
                            rank,
                            item.chunk.chunk_id,
                            item.chunk.source_type,
                            item.final_score or item.rerank_score or item.fused_score or item.bm25_score or item.dense_score,
                            json.dumps(
                                {
                                    "source_path": item.chunk.source_path,
                                    "heading_path": item.chunk.heading_path,
                                    "page_title": item.chunk.page_title,
                                    "bm25_score": item.bm25_score,
                                    "dense_score": item.dense_score,
                                    "fused_score": item.fused_score,
                                    "rerank_score": item.rerank_score,
                                },
                                ensure_ascii=False,
                            ),
                        ),
                    )
            conn.commit()
            return retrieval_run_id

    def save_qa_feedback(
        self,
        question: str,
        selected_chunk_ids: list[str],
        *,
        issue_key: str | None = None,
        root_cause: str | None = None,
        accepted: bool = False,
        notes: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO qa_feedback (question, issue_key, selected_chunk_ids_json, root_cause, accepted, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    question,
                    issue_key,
                    json.dumps(selected_chunk_ids, ensure_ascii=False),
                    root_cause,
                    1 if accepted else 0,
                    notes,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def save_daily_analysis(self, analysis: DailyAIAnalysis) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ai_analysis_daily (report_date, data_json) VALUES (?, ?)",
                (analysis.report_date, json.dumps(analysis.to_dict(), ensure_ascii=False)),
            )
            conn.commit()

    def load_daily_analysis(self, report_date: str) -> DailyAIAnalysis | None:
        with self.connect() as conn:
            row = conn.execute("SELECT data_json FROM ai_analysis_daily WHERE report_date = ?", (report_date,)).fetchone()
        return DailyAIAnalysis(**json.loads(row["data_json"])) if row else None

    def save_issue_analyses(self, analyses: list[IssueAIAnalysis]) -> None:
        with self.connect() as conn:
            for analysis in analyses:
                conn.execute(
                    "INSERT OR REPLACE INTO ai_analysis_issue (report_date, issue_key, data_json) VALUES (?, ?, ?)",
                    (analysis.report_date, analysis.issue_key, json.dumps(analysis.to_dict(), ensure_ascii=False)),
                )
            conn.commit()

    def load_issue_analyses(self, report_date: str) -> list[IssueAIAnalysis]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT data_json FROM ai_analysis_issue WHERE report_date = ? ORDER BY issue_key",
                (report_date,),
            ).fetchall()
        return [IssueAIAnalysis(**json.loads(row["data_json"])) for row in rows]

    def list_snapshot_dates(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT DISTINCT snapshot_date FROM issues_daily_snapshot ORDER BY snapshot_date DESC").fetchall()
        return [row["snapshot_date"] for row in rows]

    def latest_snapshot_on_or_before(self, snapshot_date: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT DISTINCT snapshot_date FROM issues_daily_snapshot WHERE snapshot_date <= ? ORDER BY snapshot_date DESC LIMIT 1",
                (snapshot_date,),
            ).fetchone()
        return row["snapshot_date"] if row else None

    def latest_snapshot_date(self) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT DISTINCT snapshot_date FROM issues_daily_snapshot ORDER BY snapshot_date DESC LIMIT 1"
            ).fetchone()
        return row["snapshot_date"] if row else None

    def compute_stale_issue_keys(self, snapshot_date: str, stale_days: int) -> set[str]:
        stale_keys: set[str] = set()
        cutoff = datetime.fromisoformat(snapshot_date) - timedelta(days=stale_days)
        for issue in self.load_snapshot(snapshot_date):
            if not issue.updated_at:
                continue
            try:
                updated = datetime.fromisoformat(issue.updated_at.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                continue
            if updated < cutoff:
                stale_keys.add(issue.issue_key)
        return stale_keys

    def save_management_summary(self, run_id: int, request: ManagementSummaryRequest, result: ManagementSummaryResult) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ai_management_summary (run_id, request_json, data_json) VALUES (?, ?, ?)",
                (
                    run_id,
                    json.dumps(request.to_dict(), ensure_ascii=False),
                    json.dumps(result.to_dict(), ensure_ascii=False),
                ),
            )
            conn.commit()

    def load_management_summary(self, run_id: int) -> ManagementSummaryResult | None:
        with self.connect() as conn:
            row = conn.execute("SELECT data_json FROM ai_management_summary WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        payload = json.loads(row["data_json"])
        return ManagementSummaryResult(
            summary_id=payload["summary_id"],
            generated_at=payload["generated_at"],
            request=ManagementSummaryRequest(**payload["request"]),
            metrics=ManagementSummaryMetrics(**payload["metrics"]),
            latest_progress_overview=payload["latest_progress_overview"],
            key_recent_changes=payload["key_recent_changes"],
            current_risks_and_blockers=payload["current_risks_and_blockers"],
            root_cause_and_pattern_observations=payload["root_cause_and_pattern_observations"],
            recommended_management_actions=payload["recommended_management_actions"],
            data_gaps=payload["data_gaps"],
            referenced_issue_keys=payload["referenced_issue_keys"],
            referenced_metrics=payload["referenced_metrics"],
            raw_response=payload["raw_response"],
        )
