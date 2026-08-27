# Release gate

Este directorio no contiene artefactos ficticios. `tools/compliance_gate.py --mode distribution` debe fallar hasta que CI genere, verifique y firme:

- `evidence/sbom.cdx.json`
- `evidence/sbom.spdx.json`
- `evidence/image-sboms/`
- `evidence/THIRD_PARTY_NOTICES.md`
- `evidence/LICENSES/`
- `evidence/corresponding-source/`
- `evidence/component-lock.json`
- `evidence/attestation.json`

No cree archivos vacíos para superar el gate. La attestation debe estar ligada a los digests finales de todos los artefactos.

## Flujo seguro

Genere primero el inventario provisional, que siempre queda marcado como bloqueado y se escribe fuera de `evidence/`. Use `--fetch-wheels` para seleccionar y verificar los wheels exactos contra el lock de hashes:

```bash
python3 tools/generate_distribution_candidate.py --fetch-wheels --fetch-licenses --fetch-sources --fetch-model-metadata --scan-images --syft /ruta/a/syft
```

El resultado se guarda en `release/candidate/distribution/` e incluye SBOMs CycloneDX y SPDX globales y por imagen, wheelhouse verificado, textos de licencia extraídos, avisos, manifiesto de fuentes candidato, lock normalizado y la lista explícita de pendientes. `IMAGE_LICENSE_GAPS.json` deduplica los hallazgos sin licencia declarada entre imágenes, mientras que `LEGAL_REVIEW_QUEUE.json` reúne las declaraciones, sus textos y hashes para revisión humana. Ambos permanecen marcados como bloqueados y no constituyen aprobación legal ni autorización de distribución.

Para validar una entrega final es obligatorio proporcionar el artefacto exacto:

```bash
python3 tools/compliance_gate.py --mode distribution --artifact /ruta/al/artefacto-final
```

El gate comprueba contenido no vacío, componentes fijados, cobertura del SBOM y avisos, textos de licencia con sus hashes, el manifiesto de fuentes correspondientes, los hashes de toda la evidencia y las firmas criptográficas de Release, Security y Legal. Las claves públicas confiables se aprovisionan fuera del bundle en `release/trusted-signers/{release,security,legal}.pem`.

La firma cubre la representación JSON canónica y sin espacios de los campos `subject` y `artifacts` de `attestation.json`, con las claves ordenadas. Cada aprobación declara `role`, `signer`, `signed_at` y `signature_base64`; el gate verifica la firma con OpenSSL y no acepta indicadores booleanos de aprobación.

`tools/prepare_unsigned_distribution_evidence.py --artifact /ruta/al/artefacto-final` prepara un paquete sin firmas únicamente cuando el candidato declara cero bloqueos y la revisión legal ya está registrada. Genera `SIGNING_PAYLOAD.json` para que Release, Security y Legal lo firmen por canales independientes. La herramienta no genera claves, no atribuye identidades y no convierte licencias desconocidas en declaraciones genéricas.
