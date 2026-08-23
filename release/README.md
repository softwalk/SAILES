# Release gate

Este directorio no contiene artefactos ficticios. `tools/compliance_gate.py --mode distribution` debe fallar hasta que CI genere, verifique y firme:

- `evidence/sbom.cdx.json`
- `evidence/THIRD_PARTY_NOTICES.md`
- `evidence/LICENSES/`
- `evidence/corresponding-source/`
- `evidence/component-lock.json`
- `evidence/attestation.json`

No cree archivos vacíos para superar el gate. La attestation debe estar ligada a los digests finales de todos los artefactos.
