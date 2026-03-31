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
                    source_path TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    doc_title TEXT NOT NULL,
                    section_path_json TEXT NOT NULL,
                    page_or_sheet TEXT,
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
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
            conn.commit()

    def create_run(self, run_type: str, run_date: str, status: str, details: str = "") -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (run_type, run_date, status, details) VALUES (?, ?, ?, ?)",
                (run_type, run_date, status, details),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def update_run(self, run_id: int, status: str, details: str = "") -> None:
        with self.connect() as conn:
            conn.execute("UPDATE runs SET status = ?, details = ? WHERE id = ?", (status, details, run_id))
            conn.commit()

    def list_runs(self, limit: int = 50) -> list[dict[str, str | int | None]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, run_type, run_date, status, details, created_at
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
                SELECT id, run_type, run_date, status, details, created_at
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
                        chunk_id, source_path, source_type, doc_title, section_path_json,
                        page_or_sheet, content, tags_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.source_path,
                        chunk.source_type,
                        chunk.doc_title,
                        json.dumps(chunk.section_path, ensure_ascii=False),
                        chunk.page_or_sheet,
                        chunk.content,
                        json.dumps(chunk.tags, ensure_ascii=False),
                        chunk.updated_at,
                    ),
                )
            conn.commit()

    def load_doc_chunks(self) -> list[DocChunk]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM doc_chunks ORDER BY doc_title, chunk_id").fetchall()
        return [
            DocChunk(
                chunk_id=row["chunk_id"],
                source_path=row["source_path"],
                source_type=row["source_type"],
                doc_title=row["doc_title"],
                section_path=json.loads(row["section_path_json"]),
                page_or_sheet=row["page_or_sheet"],
                content=row["content"],
                tags=json.loads(row["tags_json"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

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
