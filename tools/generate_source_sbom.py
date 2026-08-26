#!/usr/bin/env python3
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release/candidate"
VERSION = "0.9.0-rc5"


def directory_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                       and not ("release" in p.parts and "candidate" in p.parts)):
        digest.update(file.relative_to(path).as_posix().encode() + b"\0")
        digest.update(file.read_bytes())
    return digest.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    components = []
    for path in sorted((ROOT / "services").iterdir()):
        if path.is_dir():
            components.append({"type":"application","name":path.name,"version":VERSION,
                               "hashes":[{"alg":"SHA-256","content":directory_hash(path)}],
                               "licenses":[{"license":{"id":"LicenseRef-Proprietary-Atlantis"}}]})
    shared = ROOT / "shared/atlantis_contracts"
    components.append({"type":"library","name":"atlantis-contracts","version":VERSION,
                       "hashes":[{"alg":"SHA-256","content":directory_hash(shared)}],
                       "licenses":[{"license":{"id":"LicenseRef-Proprietary-Atlantis"}}]})
    bom = {"bomFormat":"CycloneDX","specVersion":"1.6","serialNumber":"urn:uuid:"+str(uuid4()),"version":1,
           "metadata":{"timestamp":datetime.now(UTC).isoformat(),"component":{"type":"application","name":"atlantis-autonomous-sales","version":VERSION}},
           "components":components,
           "properties":[{"name":"atlantis:scope","value":"first-party-source-only"},
                         {"name":"atlantis:distribution-status","value":"blocked-pending-third-party-lock"}]}
    (OUT / "source-sbom.cdx.json").write_text(json.dumps(bom, indent=2)+"\n")
    manifest = {"version":VERSION,"source_tree_sha256":directory_hash(ROOT),
                "generated_at":datetime.now(UTC).isoformat(),"distribution_authorized":False,
                "reason":"Third-party component/model locks and legal evidence are incomplete"}
    (OUT / "source-manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(json.dumps({"components":len(components),"status":"SOURCE_SBOM_GENERATED","distribution":"BLOCKED"}))


if __name__ == "__main__": main()
