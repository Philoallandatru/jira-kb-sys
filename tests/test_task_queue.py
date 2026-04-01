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
    latest_first = repo.load_run(first_id)
    latest_second = repo.load_run(second_id)
    assert latest_first is not None and latest_first["status"] == "running"
    assert latest_second is not None and latest_second["status"] == "queued"
