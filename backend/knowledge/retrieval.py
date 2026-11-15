"""Small approved-corpus excerpt search. No generated advice, network or database access."""
from datetime import date
import hashlib
from pathlib import Path
import re

STOP = set("a an and are as at be can do does for from how i in is it me my of on or that the this to we what when where which with you your".split())


def tokens(text):
    return set(re.findall(r"[a-z0-9]+",text.lower())) - STOP


def search(root, documents, query, *, audience, as_of, scope, limit=3):
    """The server supplies the reviewed manifest, audience, date and scope, never the model.

    `approved` is workflow metadata, not cryptographic approval. Manifest writes must
    remain restricted to reviewed source changes. Retrieved text is untrusted evidence,
    never executable instructions. A match is an excerpt, not an institutional answer.
    """
    if audience not in {"student","advisor","admin"} or scope not in {"project_demo","academic_policy"}:
        raise ValueError("Explicit supported audience and scope required")
    if type(as_of) is not date or type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError("Explicit date and limit 1..5 required")
    query_tokens=tokens(query)
    if len(query_tokens)<2:
        return {"status":"no_supported_excerpt","excerpts":[]}
    root=Path(root).resolve();matches=[];seen=set()
    for doc in documents:
        if doc.get("approved") is not True or doc.get("scope")!=scope or audience not in doc.get("audiences",[]):
            continue
        if not doc.get("approved_by") or not doc.get("version") or not doc.get("title"):
            raise ValueError("Incomplete approval provenance")
        if date.fromisoformat(doc["approved_on"])>as_of or date.fromisoformat(doc["effective_from"])>as_of:
            continue
        if doc.get("effective_until") and as_of>date.fromisoformat(doc["effective_until"]):
            continue
        if doc["id"] in seen:raise ValueError("Duplicate approved document ID")
        seen.add(doc["id"])
        relative=Path(doc["path"])
        target=(root/relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(root) or target.suffix.lower() not in {".md",".txt"}:
            raise ValueError("Document must be reviewed UTF-8 text inside corpus root")
        raw=target.read_bytes()
        if len(raw)>1024*1024:raise ValueError("Document exceeds MVP size limit")
        checksum=hashlib.sha256(raw).hexdigest()
        if checksum!=doc["sha256"]:raise ValueError("Approved document checksum mismatch")
        lines=raw.decode("utf-8-sig").splitlines()
        # Paragraph boundaries preserve exact line references and quotations.
        start=0
        for end in range(len(lines)+1):
            if end<len(lines) and lines[end].strip():continue
            if end>start:
                excerpt="\n".join(lines[start:end])
                overlap=len(tokens(excerpt)&query_tokens)
                if overlap>=2:
                    matches.append((overlap,{"document_id":doc["id"],"title":doc["title"],"version":doc["version"],"scope":scope,
                        "sha256":checksum,"start_line":start+1,"end_line":end,"quote":excerpt}))
            start=end+1
    matches.sort(key=lambda x:(-x[0],x[1]["document_id"],x[1]["start_line"]))
    excerpts=[row[1] for row in matches[:limit]]
    return {"status":"supported_excerpts" if excerpts else "no_supported_excerpt","excerpts":excerpts}
