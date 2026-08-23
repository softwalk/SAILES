# Distribution compliance gate

This gate is mandatory for every client-facing appliance, VM, Proxmox template, snapshot, ISO, container bundle or offline installer.

## Required output

1. `component-lock.yaml` with no `TBD`, `UNKNOWN`, mutable tag or missing digest.
2. CycloneDX and SPDX SBOMs for application, operating system, containers and models.
3. `THIRD_PARTY_NOTICES` and complete license texts.
4. Corresponding-source package or valid written offer where applicable, including modifications and build/install scripts.
5. Reproducible build evidence, signatures, provenance and SHA-256 hashes.
6. `distribution-compliance-attestation.json` signed by Release, Security and Legal and bound to the final artifact digest.

## Deny conditions

- OpenOutreach imported into proprietary code or distributed modified without GPLv3 source.
- n8n found in dependency, container, SBOM, flow or deployment manifests.
- Atlantis proprietary services combined or linked into a copyleft process.
- Any component or model lacking exact repository/source, revision, digest or approved license.
- Any required notice, license, source package, build script or signature missing.
