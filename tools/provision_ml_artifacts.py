"""Provision trusted frozen artifacts without training or extracting arbitrary ZIP paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

FILES = {
    'ml/outputs/baselines-v1/logistic_regression.joblib': 'model_sha256',
    'ml/outputs/calibration-v1/calibration_maps.joblib': 'maps_sha256',
}
MANIFEST = 'artifact-manifest.json'
MAX_ENTRY_BYTES = 10 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def configuration(repo):
    repo = Path(repo).resolve()
    config = json.loads((repo / 'ml/configs/FINAL_EXPERIMENT_V1.json').read_text(encoding='utf-8-sig'))
    if config['primary'] != 'logistic_regression_with_existing_sigmoid':
        raise ValueError('Unsupported frozen experiment')
    for name, expected in config['source_sha256'].items():
        if Path(name).name != name:
            raise ValueError('Invalid frozen source path')
        if digest((repo / 'ml/src/acadmate_ml' / name).read_bytes()) != expected:
            raise ValueError('Frozen source mismatch: ' + name)
    return config


def checked_artifacts(repo):
    repo = Path(repo).resolve()
    config = configuration(repo)
    artifacts = {}
    for relative, key in FILES.items():
        data = (repo / relative).read_bytes()
        if digest(data) != config[key]:
            raise ValueError('Frozen artifact mismatch: ' + relative)
        artifacts[relative] = data
    return config, artifacts


def pack(repo, bundle):
    config, artifacts = checked_artifacts(repo)
    manifest = {'schema_version': '1.0', 'primary': config['primary'], 'artifacts': {
        relative: {'sha256': digest(data), 'bytes': len(data)} for relative, data in artifacts.items()
    }}
    bundle = Path(bundle)
    if bundle.exists():
        raise ValueError('Package exists; refusing to overwrite')
    bundle.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, data in artifacts.items():
            archive.writestr(relative, data)
        archive.writestr(MANIFEST, json.dumps(manifest, indent=2) + '\n')
    checksum = digest(bundle.read_bytes())
    sidecar = bundle.with_suffix(bundle.suffix + '.sha256')
    with sidecar.open('x', encoding='utf-8') as stream:
        stream.write(checksum + '  ' + bundle.name + '\n')
    return checksum


def install(repo, bundle, expected_zip_sha256):
    repo = Path(repo).resolve()
    config = configuration(repo)
    package = Path(bundle).read_bytes()
    if digest(package) != expected_zip_sha256.lower():
        raise ValueError('ZIP checksum mismatch')
    import io
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        names = archive.namelist()
        if len(names) != 3 or set(names) != set(FILES) | {MANIFEST}:
            raise ValueError('Unexpected/duplicate package entries')
        if any(entry.file_size > MAX_ENTRY_BYTES for entry in archive.infolist()):
            raise ValueError('Artifact package entry exceeds size limit')
        manifest = json.loads(archive.read(MANIFEST))
        if manifest['schema_version'] != '1.0' or manifest['primary'] != config['primary'] or set(manifest['artifacts']) != set(FILES):
            raise ValueError('Package manifest does not match experiment')
        payloads = {}
        for relative, key in FILES.items():
            data = archive.read(relative)
            record = manifest['artifacts'][relative]
            if digest(data) != config[key] or record['sha256'] != config[key] or record['bytes'] != len(data):
                raise ValueError('Artifact checksum/manifest mismatch: ' + relative)
            target = repo / relative
            if not target.resolve().is_relative_to(repo):
                raise ValueError('Artifact target escapes checkout')
            if target.exists() and digest(target.read_bytes()) != config[key]:
                raise ValueError('Refusing to overwrite a mismatched artifact: ' + relative)
            payloads[relative] = data
    # All package, source, target and integrity checks precede any installation.
    for relative, data in payloads.items():
        target = repo / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
    return verify(repo)


def verify(repo, smoke=False):
    repo = Path(repo).resolve()
    config, artifacts = checked_artifacts(repo)
    result = {'artifacts': {relative: digest(data) for relative, data in artifacts.items()}, 'smoke': None}
    if smoke:
        # Only the opt-in smoke step deserializes local files, after hash checks.
        sys.path[:0] = [str(repo / 'backend'), str(repo / 'ml/src')]
        from services.research_predictions import PredictionService
        previous = os.environ.get('ACADMATE_RESEARCH_DEMO_ENABLED')
        try:
            os.environ['ACADMATE_RESEARCH_DEMO_ENABLED'] = 'true'
            service = PredictionService(repo)
            scored = service.get(20014)
            unavailable = service.get(20044)
        finally:
            if previous is None:
                os.environ.pop('ACADMATE_RESEARCH_DEMO_ENABLED', None)
            else:
                os.environ['ACADMATE_RESEARCH_DEMO_ENABLED'] = previous
        if scored['status'] != 'scored_research_demo' or abs(scored['research_risk_probability'] - 0.3783828964249184) > 1e-12:
            raise ValueError('Frozen inference smoke regression')
        if unavailable['status'] != 'unavailable' or unavailable['research_risk_probability'] is not None:
            raise ValueError('Unavailable-data smoke regression')
        result['smoke'] = {'scored_enrollment': 20014, 'probability': scored['research_risk_probability'], 'unavailable_enrollment': 20044, 'passed': True}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['pack', 'install', 'verify'])
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--sha256', help='ZIP digest received through the trusted handoff')
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.smoke and args.action != 'verify':
        parser.error('--smoke applies only to verify')
    if args.action in {'pack', 'install'} and args.bundle is None:
        parser.error('--bundle is required')
    if args.action == 'install' and not args.sha256:
        parser.error('--sha256 is required for install')
    try:
        if args.action == 'pack':
            result = {'zip_sha256': pack(args.repo, args.bundle), 'bundle': str(args.bundle.resolve())}
        elif args.action == 'install':
            result = install(args.repo, args.bundle, args.sha256)
        else:
            result = verify(args.repo, args.smoke)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(1, 'Provisioning failed: ' + str(exc) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
