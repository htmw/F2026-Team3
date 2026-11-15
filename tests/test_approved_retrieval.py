from datetime import date
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from knowledge.retrieval import search


class RetrievalTests(unittest.TestCase):
    def fixture(self,root):
        raw=b"# Test-only project instructions\n\nThe degree plan shows completed credits.\nIt also shows remaining requirements.\n\nContact the assigned advisor for questions.\n"
        (root/"demo.md").write_bytes(raw)
        return {"id":"fixture","title":"Test-only project guide","path":"demo.md","version":"test-v1","scope":"project_demo","approved":True,"approved_by":"test-fixture-only","approved_on":"2026-01-01","effective_from":"2026-01-01","effective_until":None,"audiences":["student"],"sha256":hashlib.sha256(raw).hexdigest()}
    def lookup(self,root,docs,**kw):
        return search(root,docs,"degree plan completed credits",audience="student",as_of=date(2026,11,14),scope="project_demo",**kw)
    def test_exact_excerpt_and_line_citation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);doc=self.fixture(root);out=self.lookup(root,[doc])
            self.assertEqual(out["status"],"supported_excerpts")
            hit=out["excerpts"][0]
            self.assertEqual((hit["start_line"],hit["end_line"]),(3,4))
            self.assertEqual(hit["quote"],"The degree plan shows completed credits.\nIt also shows remaining requirements.")
            self.assertEqual(hit["sha256"],doc["sha256"])
    def test_unapproved_and_no_match_abstain(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);doc=self.fixture(root)
            self.assertEqual(self.lookup(root,[dict(doc,approved=False,path="missing")])["excerpts"],[])
            self.assertEqual(search(root,[doc],"visa funding",audience="student",as_of=date(2026,11,14),scope="project_demo")["status"],"no_supported_excerpt")
    def test_audience_and_demo_scope_cannot_supply_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);doc=self.fixture(root)
            for role,scope in [("advisor","project_demo"),("student","academic_policy")]:
                self.assertEqual(search(root,[doc],"degree plan",audience=role,as_of=date(2026,11,14),scope=scope)["excerpts"],[])
    def test_future_and_expired_sources_are_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);doc=self.fixture(root)
            for patch in ({"effective_from":"2027-01-01"},{"approved_on":"2027-01-01"},{"effective_until":"2026-01-02"}):
                self.assertEqual(self.lookup(root,[dict(doc,**patch)])["excerpts"],[])
    def test_changed_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);doc=self.fixture(root);(root/"demo.md").write_text("changed")
            with self.assertRaisesRegex(ValueError,"checksum"):self.lookup(root,[doc])
    def test_path_escape_and_missing_approval_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);doc=self.fixture(root)
            with self.assertRaises(ValueError):self.lookup(root,[dict(doc,path="../outside.md")])
            with self.assertRaises(ValueError):self.lookup(root,[dict(doc,approved_by="")])
    def test_empty_manifest_and_underspecified_query_abstain(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.assertEqual(self.lookup(root,[])["status"],"no_supported_excerpt")
            self.assertEqual(search(root,[],"what is it",audience="student",as_of=date(2026,11,14),scope="project_demo")["excerpts"],[])


if __name__=="__main__":unittest.main()
