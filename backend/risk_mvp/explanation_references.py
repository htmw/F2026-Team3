"""Load provisioned numeric SHAP references. Never trains or reads evaluation data."""
import hashlib
import json
from pathlib import Path

RELATIVE = Path("ml/outputs/explanation-references-v1")
POLICY = "preceding_weekly_training_checkpoint_v1"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate(root, payload):
    config_bytes = (Path(root)/"ml/configs/FINAL_EXPERIMENT_V1.json").read_bytes()
    config = json.loads(config_bytes)
    if payload["schema_version"] != "1.0" or payload["policy"] != POLICY:
        raise ValueError("Unsupported reference package")
    if payload["config_sha256"] != digest(config_bytes) or payload["features"] != config["features"]:
        raise ValueError("Frozen configuration mismatch")
    if not payload["references"]:
        raise ValueError("Empty references")
    import math
    for key, record in payload["references"].items():
        day = int(key)
        meta, rows = record["metadata"], record["values"]
        if day < 7 or day % 7 or str(day) != key or meta["course_day"] != day:
            raise ValueError("Invalid reference day")
        if meta["seed"] != 42 or meta["requested_size"] != 128 or not 2 <= len(rows) <= 128 or meta["actual_size"] != len(rows):
            raise ValueError("Invalid reference sample")
        if meta["source"] != "verified_original_training_features_only":
            raise ValueError("Invalid source")
        if record["baseline_report_sha256"] != config["baseline_report_sha256"] or record["split_manifest_sha256"] != config["split_manifest_sha256"]:
            raise ValueError("Reference provenance mismatch")
        for row in rows:
            if len(row) != len(config["features"]) or row[0] != day or any(v is not None and (type(v) not in (int,float) or not math.isfinite(v)) for v in row):
                raise ValueError("Invalid numeric background")
    return payload


def load(root, day):
    root=Path(root)
    folder=root/RELATIVE
    receipt=json.loads((folder/"receipt.json").read_text(encoding="utf-8"))
    raw=(folder/"references.json").read_bytes()
    if digest(raw) != receipt["references_sha256"]:
        raise ValueError("Installed reference checksum mismatch")
    payload=validate(root,json.loads(raw))
    record=payload["references"].get(str(day))
    if record is None:
        raise ValueError("No verified reference for requested day")
    import numpy as np
    values=np.asarray([[np.nan if v is None else v for v in row] for row in record["values"]],dtype=float)
    values.setflags(write=False)
    return values,dict(record["metadata"])
