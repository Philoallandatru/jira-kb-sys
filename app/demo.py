from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.models import DocChunk, IssueRecord


def build_demo_issues() -> dict[str, list[IssueRecord]]:
    today = datetime.today().date()
    yesterday = today - timedelta(days=1)
    return {
        yesterday.isoformat(): [
            IssueRecord(
                issue_key="SSD-101",
                summary="Admin queue timeout under heavy mixed workload",
                status="In Progress",
                assignee="alice",
                priority="High",
                project="SSD",
                labels=["timeout", "nvme"],
                components=["fw", "admin-queue"],
                description="Timeout happens during admin queue command bursts after reset recovery.",
                updated_at=f"{yesterday.isoformat()}T10:00:00",
            ),
            IssueRecord(
                issue_key="SSD-102",
                summary="Background GC causes latency spikes in PCIe stress",
                status="Open",
                assignee="bob",
                priority="Medium",
                project="SSD",
                labels=["latency", "pcie"],
                components=["gc", "scheduler"],
                description="Latency spike aligns with GC kick-off and PCIe retry count increase.",
                updated_at=f"{yesterday.isoformat()}T12:00:00",
            ),
            IssueRecord(
                issue_key="SSD-103",
                summary="Telemetry mismatch in SMART log page",
                status="Done",
                assignee="carol",
                priority="Low",
                project="SSD",
                labels=["telemetry"],
                components=["smart-log"],
                description="SMART log counter rollover fixed in prior patch.",
                updated_at=f"{yesterday.isoformat()}T15:00:00",
            ),
        ],
        today.isoformat(): [
            IssueRecord(
                issue_key="SSD-101",
                summary="Admin queue timeout under heavy mixed workload",
                status="Blocked",
                assignee="alice",
                priority="High",
                project="SSD",
                labels=["timeout", "nvme", "blocker"],
                components=["fw", "admin-queue"],
                description="Issue escalated after repeated timeout and controller reset loop.",
                updated_at=f"{today.isoformat()}T09:30:00",
            ),
            IssueRecord(
                issue_key="SSD-102",
                summary="Background GC causes latency spikes in PCIe stress",
                status="In Progress",
                assignee="bob",
                priority="Medium",
                project="SSD",
                labels=["latency", "pcie"],
                components=["gc", "scheduler"],
                description="Need to correlate GC throttle policy with retry bursts.",
                updated_at=f"{today.isoformat()}T11:00:00",
            ),
            IssueRecord(
                issue_key="SSD-104",
                summary="Namespace attach command fails after surprise power loss",
                status="Open",
                assignee="dave",
                priority="Critical",
                project="SSD",
                labels=["power-loss", "namespace"],
                components=["recovery", "namespace-mgr"],
                description="Attach fails after metadata replay leaves namespace state inconsistent.",
                updated_at=f"{today.isoformat()}T13:15:00",
            ),
        ],
    }


def build_demo_chunks(base_dir: str) -> list[DocChunk]:
    base = Path(base_dir).resolve()
    return [
        DocChunk(
            chunk_id="demo-nvme-admin-timeout",
            source_path=str(base / "nvme_admin_timeout.md"),
            source_type="md",
            doc_title="NVMe Admin Queue Recovery Notes",
            section_path=["Admin Queue", "Timeout Recovery"],
            page_or_sheet="Admin Queue",
            content=(
                "Admin queue timeout during heavy command bursts is often caused by outstanding "
                "completion entries not being reclaimed before controller reset. Recommended action "
                "is to inspect CQ head/tail synchronization, timeout thresholds, and reset recovery ordering."
            ),
            tags=["nvme", "timeout", "admin-queue", "recovery"],
            updated_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        ),
        DocChunk(
            chunk_id="demo-gc-latency",
            source_path=str(base / "gc_latency_policy.md"),
            source_type="md",
            doc_title="GC Scheduler Tuning",
            section_path=["GC", "Latency Control"],
            page_or_sheet="GC",
            content=(
                "Latency spikes under PCIe stress commonly align with aggressive foreground GC. "
                "Action should focus on throttle thresholds, queue depth aware scheduling, and "
                "correlating retry counts with GC kick windows."
            ),
            tags=["gc", "latency", "pcie", "scheduler"],
            updated_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        ),
        DocChunk(
            chunk_id="demo-namespace-recovery",
            source_path=str(base / "namespace_recovery.md"),
            source_type="md",
            doc_title="Namespace Recovery Design",
            section_path=["Recovery", "Namespace State Replay"],
            page_or_sheet="Recovery",
            content=(
                "Namespace attach failures after power loss can indicate incomplete metadata replay "
                "or stale namespace state cached before replay finalization. Validate replay checkpoints, "
                "state transition guards, and attach command precondition checks."
            ),
            tags=["namespace", "recovery", "power-loss"],
            updated_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        ),
    ]
