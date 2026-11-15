"""Opt-in project help overlay for the isolated team candidate; no DB operations."""
from pathlib import Path
import argparse
from apply_main_admin_display import replace_once
ROOT=Path(__file__).resolve().parents[1]


def apply(snapshot):
    snapshot=Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT/"ml/outputs/main-integration"):raise ValueError("Isolated export required")
    path=snapshot/"backend/services/ai/__init__.py"
    old='    else:\n        result = _engine_answer(db, student, label, text, ctx, history)\n    return {**result, "payload": _clean_payload(db, result.get("payload"))}'
    new='    else:\n        from knowledge.project_help import answer as project_help_answer\n        help_result = project_help_answer(text, audience="student")\n        result = help_result if help_result is not None else _engine_answer(db, student, label, text, ctx, history)\n    payload = _clean_payload(db, result.get("payload"))\n    # Only server-retrieved evidence may create a verified citation; engines cannot supply one.\n    payload.pop("citations", None)\n    if help_result is not None:\n        payload["citations"] = help_result["payload"].get("citations", [])\n    return {**result, "payload": payload}'
    replace_once(path,old,new)
    replace_once(path,'    result = guard.check(text, ctx["settings"]["blockedTopics"])','    help_result = None\n    result = guard.check(text, ctx["settings"]["blockedTopics"])')
    path=snapshot/"backend/services/ai/threads.py"
    replace_once(path,'        "sources": payload.get("sources") or [],','        "sources": payload.get("sources") or [],\n        "citations": payload.get("citations") or [],')
    path=snapshot/"backend/schemas/ai.py"
    replace_once(path,'class MessageOut(ApiModel):','class ProjectHelpCitation(ApiModel):\n    document_id: str\n    title: str\n    version: str\n    start_line: int\n    end_line: int\n    path: str\n\n\nclass MessageOut(ApiModel):')
    replace_once(path,'    sources: list[str]\n    rating: int | None','    sources: list[str]\n    citations: list[ProjectHelpCitation] = Field(default_factory=list)\n    rating: int | None')
    path=snapshot/"backend/main.py"
    text=path.read_text(encoding="utf-8")
    addition="\n# Authenticated, read-only source view for opt-in project-help citations.\nfrom knowledge.router import router as project_help_router\napp.include_router(project_help_router)\n"
    if addition not in text:path.write_text(text+addition,encoding="utf-8")
    path=snapshot/"frontend/src/components/ai/AiMessage.jsx"
    # Remove the earlier citation presentation when updating an existing export.
    # New exports retain the original plain-text message component.
    text=path.read_text(encoding="utf-8")
    text=text.replace("import { apiUrl } from '../../lib/api.js'\n", "")
    start=text.find("        {message.citations?.filter(")
    if start != -1:
        end=text.index("        {message.follow && <div",start)
        text=text[:start]+text[end:]
    path.write_text(text,encoding="utf-8")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--snapshot",required=True);apply(p.parse_args().snapshot)
