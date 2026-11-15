"""Cross-role approval lifecycle; use only the dedicated pytest database."""
import pytest
from conftest import login
from test_plan import restore_plan, unsent_plan, AMARA, PLAN, SPRING_2027
from test_messages import restore_messages

@pytest.mark.parametrize("action,comment,status,plan_status", [
    ("approve", "Ready to proceed.", "Approved", "Approved"),
    ("request-changes", "Please revise the elective.", "Changes requested", "Changes requested"),
])
def test_student_advisor_round_trip(client,unsent_plan,restore_messages,action,comment,status,plan_status):
    login(client,AMARA)
    response=client.post(PLAN+"/submit",json={"termId":SPRING_2027})
    assert response.status_code==200
    request_id=response.json()["requestId"]
    login(client,"daniel.kim@pac.edu")
    assert client.post(f"/api/v1/advisor/approvals/{request_id}/{action}",json={"comment":comment}).status_code==404
    login(client,"sarah.smith@pac.edu")
    before=client.get("/api/v1/users/me/badges").json()["badges"]["approvals"]
    decision=client.post(f"/api/v1/advisor/approvals/{request_id}/{action}",json={"comment":comment})
    assert decision.status_code==200 and decision.json()["status"]==status
    assert client.get("/api/v1/users/me/badges").json()["badges"]["approvals"]==before-1
    assert client.post(f"/api/v1/advisor/approvals/{request_id}/approve").status_code==409
    login(client,AMARA)
    assert client.post(f"/api/v1/advisor/approvals/{request_id}/approve").status_code==403
    spring=next(t for t in client.get(PLAN).json()["terms"] if t["name"]=="Spring 2027")
    assert {c["planStatus"] for c in spring["courses"]}=={plan_status}
    assert spring["advisorFeedback"]==(comment if status=="Changes requested" else None)
    audit=client.get("/api/v1/students/me/degree-audit").json()
    assert (audit["graduation"]["status"]=="Plan changes requested")== (status=="Changes requested")
    assert audit["graduation"]["label"]=="May 2027"
    login(client,"sarah.smith@pac.edu")
    reopened=client.post(f"/api/v1/advisor/approvals/{request_id}/reopen")
    assert reopened.status_code==200 and reopened.json()["status"]=="Pending"
    assert client.get("/api/v1/users/me/badges").json()["badges"]["approvals"]==before
    login(client,AMARA)
    spring=next(t for t in client.get(PLAN).json()["terms"] if t["name"]=="Spring 2027")
    assert {c["planStatus"] for c in spring["courses"]}=={"Pending approval"}
    assert spring["advisorFeedback"] is None

@pytest.mark.parametrize("comment", ["", "   ", "x"*1001])
def test_change_request_requires_meaningful_bounded_comment(client,comment):
    login(client,"sarah.smith@pac.edu")
    response=client.post("/api/v1/advisor/approvals/1709/request-changes",json={"comment":comment})
    assert response.status_code==422
    assert client.get("/api/v1/advisor/approvals/1709").json()["status"]=="Pending"


def test_nonblocking_warnings_reach_advisor(client):
    from database import SessionLocal
    from models import ApprovalRequest
    login(client,"sarah.smith@pac.edu")
    response=client.get("/api/v1/advisor/approvals/1709")
    assert response.status_code==200
    with SessionLocal() as db:
        checks=db.get(ApprovalRequest,1709).precheck["checks"]
        expected=[c["text"] for c in checks if not c.get("ok") and not c.get("blocking")]
    assert expected
    assert response.json()["warnings"]==expected
