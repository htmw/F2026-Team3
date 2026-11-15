import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tools"),str(ROOT/"backend")]
import provision_explanation_references as setup
from risk_mvp.explanation_references import load, RELATIVE, POLICY, digest


class ReferenceSetupTests(unittest.TestCase):
    def fixture(self,root):
        repo=root/"checkout"
        config={"primary":"logistic_regression_with_existing_sigmoid","source_sha256":{},"features":["course_day","x"],"baseline_report_sha256":"a"*64,"split_manifest_sha256":"b"*64}
        path=repo/"ml/configs/FINAL_EXPERIMENT_V1.json";path.parent.mkdir(parents=True);path.write_text(json.dumps(config))
        meta={"course_day":28,"seed":42,"requested_size":128,"actual_size":2,"source":"verified_original_training_features_only"}
        data={"schema_version":"1.0","policy":POLICY,"config_sha256":digest(path.read_bytes()),"features":config["features"],"references":{"28":{"metadata":meta,"values":[[28,None],[28,2]],"baseline_report_sha256":"a"*64,"split_manifest_sha256":"b"*64}}}
        return repo,data

    def package(self,root,data,extra=None):
        raw=json.dumps(data).encode();manifest={"schema_version":"1.0","references_sha256":digest(raw),"bytes":len(raw)}
        bundle=root/"refs.zip"
        with zipfile.ZipFile(bundle,"w") as archive:
            archive.writestr("references.json",raw);archive.writestr("manifest.json",json.dumps(manifest))
            if extra:archive.writestr(extra,b"bad")
        return bundle,digest(bundle.read_bytes())

    def test_install_idempotent_load_and_missing_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo,data=self.fixture(root);bundle,sha=self.package(root,data)
            self.assertTrue(setup.install(repo,bundle,sha)["passed"])
            setup.install(repo,bundle,sha)
            values,meta=load(repo,28)
            self.assertFalse(values.flags.writeable);self.assertEqual(values.shape,(2,2))
            with self.assertRaisesRegex(ValueError,"requested day"):load(repo,35)

    def test_wrong_zip_hash_no_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo,data=self.fixture(root);bundle,sha=self.package(root,data)
            with self.assertRaisesRegex(ValueError,"ZIP checksum"):setup.install(repo,bundle,"0"*64)
            self.assertFalse((repo/RELATIVE).exists())

    def test_extra_entry_no_extract(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo,data=self.fixture(root);bundle,sha=self.package(root,data,"../escape")
            with self.assertRaisesRegex(ValueError,"entries"):setup.install(repo,bundle,sha)
            self.assertFalse((repo/RELATIVE).exists())

    def test_invalid_matrix_and_config_rejected_before_write(self):
        for change in ("future_day","infinity","config","provenance"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temp:
                root=Path(temp);repo,data=self.fixture(root)
                if change=="future_day":data["references"]["28"]["values"][0][0]=35
                elif change=="infinity":data["references"]["28"]["values"][0][1]=float("inf")
                elif change=="config":data["config_sha256"]="0"*64
                else:data["references"]["28"]["split_manifest_sha256"]="0"*64
                bundle,sha=self.package(root,data)
                with self.assertRaises(ValueError):setup.install(repo,bundle,sha)
                self.assertFalse((repo/RELATIVE).exists())

    def test_tamper_and_overwrite_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo,data=self.fixture(root);bundle,sha=self.package(root,data)
            setup.install(repo,bundle,sha)
            (repo/RELATIVE/"references.json").write_text("{}")
            with self.assertRaisesRegex(ValueError,"checksum"):load(repo,28)
            with self.assertRaisesRegex(ValueError,"mismatched"):setup.install(repo,bundle,sha)


    def test_invalid_installed_package_does_not_fall_back_to_training(self):
        from risk_mvp.main_explanations import training_background
        with tempfile.TemporaryDirectory() as temp:
            repo=Path(temp)
            (repo/RELATIVE).mkdir(parents=True)
            training_background.cache_clear()
            with patch("acadmate_ml.explain.background",side_effect=AssertionError("No fallback")):
                with self.assertRaises(FileNotFoundError):training_background(str(repo),28)
            training_background.cache_clear()

    def test_verify_rejects_empty_reference_document(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo,data=self.fixture(root);bundle,sha=self.package(root,data)
            setup.install(repo,bundle,sha)
            data["references"]={}
            (repo/RELATIVE/"references.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"Empty"):setup.verify(repo)


if __name__=="__main__":unittest.main()
