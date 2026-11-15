"""Both student surfaces share projection assumptions without losing plan-review status."""
def test_degree_audit_shares_dashboard_estimate_explanation(client,as_user):
    as_user("student")
    dashboard=client.get("/api/v1/students/me/dashboard")
    audit=client.get("/api/v1/students/me/degree-audit")
    assert dashboard.status_code==audit.status_code==200
    graduation=next(stat for stat in dashboard.json()["stats"] if stat["key"]=="graduation")
    actual=audit.json()["graduation"]
    assert actual["label"]==graduation["value"]
    assert actual["estimateNote"]==graduation["note"]
    assert "9 credits" in actual["estimateNote"]
    # Approval state stays separate from pace assumptions.
    assert actual["status"]==next(stat for stat in audit.json()["stats"] if stat["label"]=="Expected graduation")["note"]
