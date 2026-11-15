"""Opt-in project help from the user-authorized corpus; no LLM or student data."""
from datetime import datetime, timezone, date
import hashlib
import json
import logging
import os
from pathlib import Path
import re
from .retrieval import search
ROOT=Path(__file__).resolve().parents[2]
CORPUS=ROOT/"data/knowledge/project_help"
LOG=logging.getLogger(__name__)
POLICY=re.compile(r"\b(?:repeat(?:ing)? a course|repeat[- ]course|grade replacement|academic probation|minimum gpa|university policy|institutional policy)\b",re.I)
HELP=re.compile(r"\b(?:how|where|explain|what does|what is|why is)\b",re.I)
TOPICS=re.compile(r"\b(?:submit|approval|approved|pending|request(?:ed)? changes|risk estimate|course assessment|assessment unavailable|explanation|refresh assessment|message|schedule (?:a )?follow[- ]up|book (?:a |an )?(?:advising )?meeting)\b",re.I)


def today():
    # Document approvals use the actual calendar, not the simulated academic date.
    return datetime.now(timezone.utc).date()


def documents():
    return json.loads((CORPUS/"manifest.json").read_text(encoding="utf-8"))


def answer(text, audience="student"):
    if os.environ.get("ACADMATE_PROJECT_HELP_ENABLED")!="true":return None
    if POLICY.search(text):
        return {"kind":"answer","engine":"Rules","text":"Project help explains how to use AcadMate. I do not have an approved academic-policy document for that question. Ask your advisor and consult the applicable official catalog.","payload":{"sources":[],"citations":[]}}
    if not HELP.search(text) or not TOPICS.search(text):return None
    try:
        out=search(CORPUS,documents(),text,audience=audience,as_of=today(),scope="project_demo",limit=1)
        if not out["excerpts"]:
            return {"kind":"answer","engine":"Rules","text":"I could not find a verified project-help passage for that question. Try asking about submitting a plan, a course assessment, messages or meetings.","payload":{"sources":[],"citations":[]}}
        hit=out["excerpts"][0]
        citation={"document_id":hit["document_id"],"title":hit["title"],"version":hit["version"],"start_line":hit["start_line"],"end_line":hit["end_line"],"path":"/help/documents/"+hit["document_id"]}
        return {"kind":"answer","engine":"Rules","text":"Project help\n\n"+hit["quote"],"payload":{"sources":[],"citations":[citation]}}
    except (OSError,ValueError,KeyError,TypeError):
        LOG.exception("Verified project help unavailable")
        return {"kind":"answer","engine":"Rules","text":"Verified project help is temporarily unavailable. Your academic records and existing advising tools are unchanged.","payload":{"sources":[],"citations":[]}}


def document(document_id,audience):
    if os.environ.get("ACADMATE_PROJECT_HELP_ENABLED")!="true":raise LookupError("Project help unavailable")
    entry=next((d for d in documents() if d["id"]==document_id),None)
    if entry is None:raise LookupError("Project document not found")
    now=today()
    if entry.get("approved") is not True or entry.get("scope")!="project_demo" or audience not in entry.get("audiences",[]) or not entry.get("approved_by") or date.fromisoformat(entry["approved_on"])>now or date.fromisoformat(entry["effective_from"])>now or (entry.get("effective_until") and now>date.fromisoformat(entry["effective_until"])):
        raise LookupError("Project document not found")
    relative=Path(entry["path"]);path=(CORPUS/relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(CORPUS.resolve()) or path.suffix not in (".txt",".md"):raise ValueError("Invalid corpus path")
    raw=path.read_bytes()
    if len(raw)>1024*1024 or hashlib.sha256(raw).hexdigest()!=entry["sha256"]:raise ValueError("Project document checksum mismatch")
    lines=raw.decode("utf-8-sig").splitlines()
    return entry,"Project help only; not university academic policy.\nVersion "+entry["version"]+"\n\n"+"\n".join(f"{i}: {line}" for i,line in enumerate(lines,1))
