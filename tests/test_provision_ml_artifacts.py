import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC=importlib.util.spec_from_file_location('provision',Path(__file__).resolve().parents[1]/'tools/provision_ml_artifacts.py')
PROVISION=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(PROVISION)

class ProvisioningTests(unittest.TestCase):
    def fixture(self,base):
        source=base/'source';target=base/'target'
        payloads={name:('test-only-'+name).encode() for name in PROVISION.FILES}
        config={'primary':'logistic_regression_with_existing_sigmoid','source_sha256':{'features.py':PROVISION.digest(b'# frozen test fixture\n')}}
        for name,key in PROVISION.FILES.items():config[key]=PROVISION.digest(payloads[name])
        for repo in [source,target]:
            (repo/'ml/configs').mkdir(parents=True);(repo/'ml/src/acadmate_ml').mkdir(parents=True)
            (repo/'ml/configs/FINAL_EXPERIMENT_V1.json').write_text(json.dumps(config))
            (repo/'ml/src/acadmate_ml/features.py').write_bytes(b'# frozen test fixture\n')
        for name,data in payloads.items():
            path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        bundle=base/'artifacts.zip';checksum=PROVISION.pack(source,bundle)
        return source,target,bundle,checksum,payloads

    def test_minimal_package_install_verify_and_idempotence_without_joblib(self):
        with tempfile.TemporaryDirectory() as temp:
            source,target,bundle,checksum,payloads=self.fixture(Path(temp))
            with zipfile.ZipFile(bundle) as archive:self.assertEqual(set(archive.namelist()),set(PROVISION.FILES)|{PROVISION.MANIFEST})
            with patch.dict(sys.modules,{'joblib':None}):
                PROVISION.install(target,bundle,checksum);PROVISION.install(target,bundle,checksum)
                result=PROVISION.verify(target)
            self.assertIsNone(result['smoke'])
            for name,data in payloads.items():self.assertEqual((target/name).read_bytes(),data)
            with self.assertRaises(ValueError):PROVISION.pack(source,bundle)

    def test_wrong_zip_checksum_leaves_checkout_unmodified(self):
        with tempfile.TemporaryDirectory() as temp:
            _,target,bundle,_,_=self.fixture(Path(temp))
            with self.assertRaisesRegex(ValueError,'ZIP checksum'):PROVISION.install(target,bundle,'0'*64)
            self.assertFalse((target/'ml/outputs').exists())

    def test_changed_source_rejected_before_install(self):
        with tempfile.TemporaryDirectory() as temp:
            _,target,bundle,checksum,_=self.fixture(Path(temp))
            (target/'ml/src/acadmate_ml/features.py').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'source mismatch'):PROVISION.install(target,bundle,checksum)
            self.assertFalse((target/'ml/outputs').exists())

    def test_existing_mismatch_preserved_and_other_artifact_not_installed(self):
        with tempfile.TemporaryDirectory() as temp:
            _,target,bundle,checksum,_=self.fixture(Path(temp))
            first=target/next(iter(PROVISION.FILES));first.parent.mkdir(parents=True);first.write_bytes(b'preserve me')
            with self.assertRaisesRegex(ValueError,'overwrite'):PROVISION.install(target,bundle,checksum)
            self.assertEqual(first.read_bytes(),b'preserve me')
            second=target/list(PROVISION.FILES)[1];self.assertFalse(second.exists())

    def test_unexpected_zip_entry_rejected_without_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            _,target,bundle,_,_=self.fixture(Path(temp))
            with zipfile.ZipFile(bundle,'a') as archive:archive.writestr('../escape.txt','bad')
            checksum=PROVISION.digest(bundle.read_bytes())
            with self.assertRaisesRegex(ValueError,'entries'):PROVISION.install(target,bundle,checksum)
            self.assertFalse((target/'ml/outputs').exists())
            self.assertFalse((Path(temp)/'escape.txt').exists())

    def test_tampered_artifact_rejected_even_with_matching_zip_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            _,target,bundle,_,_=self.fixture(Path(temp))
            with zipfile.ZipFile(bundle) as archive:entries={n:archive.read(n) for n in archive.namelist()}
            entries[next(iter(PROVISION.FILES))]=b'tampered'
            with zipfile.ZipFile(bundle,'w') as archive:
                for n,data in entries.items():archive.writestr(n,data)
            with self.assertRaisesRegex(ValueError,'checksum/manifest'):PROVISION.install(target,bundle,PROVISION.digest(bundle.read_bytes()))
            self.assertFalse((target/'ml/outputs').exists())

if __name__=='__main__':unittest.main()
