import json

from app.repository import Repository


def test_repository_claims_oldest_queued_run_and_preserves_payload(tmp_path):
    repo = Repository(str(tmp_path / "test.db"))
    first_id = repo.create_run("analyze", "2026-04-01", "queued", payload={"report_date": "2026-04-01"})
    second_id = repo.create_run("report", "2026-04-01", "queued", payload={"report_date": "2026-04-01"})

    claimed = repo.claim_next_queued_run()

    assert claimed is not None
    assert claimed["id"] == first_id
    assert json.loads(claimed["payload_json"]) == {"report_date": "2026-04-01"}
    assert claimed["attempt_count"] == 1
    latest_first = repo.load_run(first_id)
    latest_second = repo.load_run(second_id)
    assert latest_first is not None and latest_first["status"] == "running"
    assert latest_first["attempt_count"] == 1
    assert latest_second is not None and latest_second["status"] == "queued"


def test_repository_recovers_running_tasks_after_restart(tmp_path):
    repo = Repository(str(tmp_path / "test.db"))
    run_id = repo.create_run("build-docs", "2026-04-01", "running")

    recovered = repo.requeue_running_runs("Recovered interrupted in-process task after service restart")

    run = repo.load_run(run_id)
    assert recovered == 1
    assert run is not None
    assert run["status"] == "queued"
    assert run["attempt_count"] == 1
    assert run["details"] == "Recovered interrupted in-process task after service restart"


def test_repository_retries_before_marking_failed(tmp_path):
    repo = Repository(str(tmp_path / "test.db"))
    run_id = repo.create_run("report", "2026-04-01", "queued", payload={"report_date": "2026-04-01"})
    repo.claim_next_queued_run()

    should_retry = repo.schedule_retry(run_id, "temporary failure", max_attempts=3)
    queued = repo.load_run(run_id)

    assert should_retry is True
    assert queued is not None
    assert queued["status"] == "queued"
    assert queued["attempt_count"] == 1
    assert queued["last_error"] == "temporary failure"

    repo.claim_next_queued_run()
    repo.schedule_retry(run_id, "still failing", max_attempts=2)
    failed = repo.load_run(run_id)

    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["attempt_count"] == 2
    assert failed["last_error"] == "still failing"


def test_repository_cancels_queued_run(tmp_path):
    repo = Repository(str(tmp_path / "test.db"))
    run_id = repo.create_run("report", "2026-04-01", "queued", payload={"report_date": "2026-04-01"})

    state = repo.cancel_run(run_id)
    run = repo.load_run(run_id)

    assert state == "cancelled"
    assert run is not None
    assert run["status"] == "cancelled"
    assert run["details"] == "Cancelled before execution"


def test_repository_marks_running_run_as_cancelling(tmp_path):
    repo = Repository(str(tmp_path / "test.db"))
    run_id = repo.create_run("build-docs", "2026-04-01", "running")

    state = repo.cancel_run(run_id)
    run = repo.load_run(run_id)

    assert state == "cancelling"
    assert run is not None
    assert run["status"] == "running"
    assert run["details"] == "Cancellation requested"
