from app.models import infer_team_from_issue_key


def test_infer_team_from_issue_key():
    assert infer_team_from_issue_key("[SV]SSD-101") == "SV"
    assert infer_team_from_issue_key("[DV]SSD-102") == "DV"
    assert infer_team_from_issue_key("SSD-103") is None
