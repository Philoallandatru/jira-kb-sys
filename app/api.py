from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.cli import _bootstrap
from app.management import build_management_summary, write_management_summary_files
from app.models import ManagementSummaryRequest


app = FastAPI(title="Jira Summary API", version="0.2.0")


class ManagementSummaryTaskRequest(BaseModel):
    date_from: str
    date_to: str
    team: str | None = None
    jira_status: list[str] = Field(default_factory=list)
    config_path: str | None = None


def _run_management_summary(run_id: int, request: ManagementSummaryTaskRequest) -> None:
    config, repo = _bootstrap(request.config_path)
    try:
        summary_request = ManagementSummaryRequest(
            date_from=request.date_from,
            date_to=request.date_to,
            team=request.team,
            jira_status=request.jira_status,
        )
        result = build_management_summary(config, repo, summary_request, run_id=run_id)
        repo.save_management_summary(run_id, summary_request, result)
        paths = write_management_summary_files(config, result)
        repo.update_run(run_id, "success", str(paths))
    except Exception as exc:
        repo.update_run(run_id, "failed", str(exc))


@app.post("/tasks/reports/management-summary")
def create_management_summary_task(payload: ManagementSummaryTaskRequest, background_tasks: BackgroundTasks) -> dict[str, int | str]:
    config, repo = _bootstrap(payload.config_path)
    run_id = repo.create_run("management-summary", payload.date_to, "queued")
    background_tasks.add_task(_run_management_summary, run_id, payload)
    return {"id": run_id, "status": "queued"}


@app.get("/reports/management-summary/{run_id}")
def get_management_summary(run_id: int, config_path: str | None = None) -> dict:
    _, repo = _bootstrap(config_path)
    result = repo.load_management_summary(run_id)
    if not result:
        with repo.connect() as conn:
            row = conn.execute("SELECT status, details FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="summary not found")
        return {"id": run_id, "status": row["status"], "details": row["details"]}
    return {"id": run_id, "status": "success", "result": result.to_dict()}
