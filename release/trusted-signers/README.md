# Trusted distribution signers

CI or the release environment must provision these public keys from the organization's trusted identity system:

- `release.pem`
- `security.pem`
- `legal.pem`

Do not generate release trust keys inside the evidence bundle and do not commit private keys. The distribution gate uses these public keys to verify the three independent signatures over the canonical attestation payload.
