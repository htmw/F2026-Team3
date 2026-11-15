"""Project-help acceptance on disposable pytest data; no external provider calls."""
from datetime import date
from unittest.mock import patch
import pytest
from conftest import login
from test_ai import new_student
from knowledge import project_help


@pytest.fixture(autouse=True)
def project_help_on(monkeypatch):
    monkeypatch.setenv("ACADMATE_PROJECT_HELP_ENABLED","true")
    monkeypatch.setattr(project_help,"today",lambda:date(2026,11,14))


@pytest.mark.parametrize("question,document",[
    ("How do I submit my degree plan in AcadMate?","project-help-plan"),
    ("What does a course risk estimate mean?","project-help-assessment"),
    ("How do I message a student in AcadMate?","project-help-followup"),
])
def test_help_returns_exact_verified_quote(question,document):
    out=project_help.answer(question)
    citation=out["payload"]["citations"][0]
    assert citation["document_id"]==document
    entry=next(d for d in project_help.documents() if d["id"]==document)
    lines=(project_help.CORPUS/entry["path"]).read_text(encoding="utf-8").splitlines()
    assert out["text"]=="Project help\n\n"+"\n".join(lines[citation["start_line"]-1:citation["end_line"]])


def test_policy_abstains_and_personal_record_query_is_not_intercepted():
    out=project_help.answer("What is the minimum GPA required by university policy?")
    assert not out["payload"]["citations"] and "official catalog" in out["text"]
    assert project_help.answer("What is my GPA?") is None
    assert project_help.answer("Which electives should I take next term?") is None


def test_help_toggle_and_integrity_failure(monkeypatch):
    monkeypatch.setenv("ACADMATE_PROJECT_HELP_ENABLED","false")
    assert project_help.answer("How do I submit my degree plan?") is None
    monkeypatch.setenv("ACADMATE_PROJECT_HELP_ENABLED","true")
    entries=project_help.documents();entries[0]["sha256"]="0"*64
    monkeypatch.setattr(project_help,"documents",lambda:entries)
    out=project_help.answer("How do I submit my degree plan?")
    assert "temporarily unavailable" in out["text"] and out["payload"]["citations"]==[]


def test_persisted_chat_and_authenticated_source(client,new_student):
    assert client.get("/api/v1/help/documents/project-help-plan").status_code==401
    user=new_student();login(client,user.email)
    with patch("services.ai._engine_answer",side_effect=AssertionError("Help must not call an engine")):
        response=client.post("/api/v1/students/me/ai/threads",json={"text":"How do I submit my degree plan in AcadMate?"})
    assert response.status_code==201,response.text
    body=response.json();reply=body["messages"][1];citation=reply["citations"][0]
    assert citation["documentId"]=="project-help-plan" and "Send for approval" in reply["text"]
    saved=client.get(f"/api/v1/students/me/ai/threads/{body['thread']['id']}").json()
    assert saved["messages"][1]["citations"]==reply["citations"]
    source=client.get("/api/v1"+citation["path"])
    assert source.status_code==200 and "not university academic policy" in source.text
    assert "3: To submit a degree plan" in source.text
    assert client.get("/api/v1/help/documents/not-approved").status_code==404


def test_engines_cannot_forge_verified_citations(client,new_student):
    user=new_student();login(client,user.email)
    with patch("services.ai._engine_answer",return_value={"engine":"Rules","text":"Fixture answer","payload":{"citations":[{"documentId":"forged"}]}}):
        response=client.post("/api/v1/students/me/ai/threads",json={"text":"What is my GPA?"})
    assert response.status_code==201 and response.json()["messages"][1]["citations"]==[]


def test_existing_topic_guard_precedes_help(client,new_student):
    user=new_student();login(client,user.email)
    with patch("knowledge.project_help.answer",side_effect=AssertionError("Guard must run first")):
        response=client.post("/api/v1/students/me/ai/threads",json={"text":"How do I submit a grade appeal in AcadMate?"})
    assert response.status_code==201 and response.json()["messages"][1]["kind"]=="handoff"
