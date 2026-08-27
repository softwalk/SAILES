#!/usr/bin/env bash
# Technical OIDC validation for SHADOW only. This does not authorize a pilot or
# replace a hardened HA IdP with TLS, MFA, backup and independent administration.
set -euo pipefail
umask 077
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
assert_safe_root
[[ "$EUID" -eq 0 ]] || die "shadow OIDC setup must run as root"
for command in docker curl python3 sha256sum psql; do require_command "$command"; done
python3 -c 'import cryptography' >/dev/null 2>&1 || die "Python cryptography package is required for OIDC verification"
require_file "$ATLANTIS_ENV_FILE"
grep -Eq '^ATLANTIS_SHADOW_MODE=(true|"true")$' "$ATLANTIS_ENV_FILE" || \
  die "shadow OIDC setup requires ATLANTIS_SHADOW_MODE=true"

# The tag is pulled only to discover its content-addressed local image ID. Every
# container below runs by that immutable ID, which is recorded in evidence.
readonly image_tag="quay.io/keycloak/keycloak:26.7.2"
readonly image_digest="sha256:831330513f55695572286e521f94fcd3c7e285250ed5b848090265a33192f669"
readonly image_ref="$image_tag@$image_digest"
readonly container_name="atlantis-keycloak-shadow"
readonly volume_name="atlantis_keycloak_shadow_data"
readonly keycloak_base="http://127.0.0.1:8180"
readonly issuer="$keycloak_base/realms/atlantis"
readonly audience="atlantis-human-api"
readonly state_dir="$ATLANTIS_ROOT/infrastructure/oidc-shadow"
readonly public_dir="$ATLANTIS_ROOT/infrastructure/oidc"
readonly runtime_dir="/run/atlantis"
readonly evidence_dir="$ATLANTIS_EVIDENCE_ROOT/oidc-shadow-$(date -u +'%Y%m%dT%H%M%SZ')"
readonly credentials="$state_dir/users.json"
readonly realm_file="$state_dir/realm.json"

install -d -o root -g root -m 0700 "$state_dir" "$runtime_dir" "$evidence_dir"
install -d -o root -g root -m 0755 "$public_dir"

tenant_id="$(database_psql -Atqc "SELECT c.tenant_id FROM contact c JOIN campaign_version cv ON cv.tenant_id=c.tenant_id WHERE cv.status='APPROVED' ORDER BY cv.created_at DESC LIMIT 1")"
[[ "$tenant_id" =~ ^[a-f0-9-]{36}$ ]] || die "approved campaign tenant required"

volume_preexisting=false
docker volume inspect "$volume_name" >/dev/null 2>&1 && volume_preexisting=true
if [[ ! -f "$credentials" && "$volume_preexisting" == true ]]; then
  die "shadow IdP volume exists without its root-only credential state; manual reconciliation required"
fi

# Always materialize an import file from the root-only state. It is used only
# when the persistent volume needs initialization, then securely removed.
python3 - "$credentials" "$realm_file" "$tenant_id" <<'PY'
import json
import os
import secrets
import sys
import uuid

credentials_path, realm_path, tenant = sys.argv[1:]
if os.path.exists(credentials_path):
    data = json.load(open(credentials_path, encoding="utf-8"))
    if data.get("tenant_id") != tenant:
        raise SystemExit("existing shadow IdP belongs to another tenant; manual reset required")
else:
    data = {
        "campaign_id": str(uuid.uuid4()),
        "campaign_user": "atlantis-campaign-approver",
        "campaign_password": secrets.token_urlsafe(32),
        "reviewer_id": str(uuid.uuid4()),
        "reviewer_user": "atlantis-human-reviewer",
        "reviewer_password": secrets.token_urlsafe(32),
        "admin_password": secrets.token_urlsafe(40),
        "tenant_id": tenant,
    }
    temporary = credentials_path + ".tmp"
    open(temporary, "w", encoding="utf-8").write(json.dumps(data, separators=(",", ":")))
    os.chmod(temporary, 0o400)
    os.replace(temporary, credentials_path)

required = {
    "campaign_id", "campaign_user", "campaign_password", "reviewer_id",
    "reviewer_user", "reviewer_password", "admin_password", "tenant_id",
}
if not required.issubset(data) or any(not isinstance(data[key], str) or not data[key] for key in required):
    raise SystemExit("shadow IdP credential state is invalid")
mapper_common = {
    "access.token.claim": "true",
    "id.token.claim": "false",
    "userinfo.token.claim": "false",
}
realm = {
    "realm": "atlantis",
    "enabled": True,
    "sslRequired": "none",
    "accessTokenLifespan": 300,
    "verifyEmail": False,
    "requiredCredentials": ["password"],
    "roles": {"realm": [{"name": "CAMPAIGN_APPROVER"}, {"name": "HUMAN_REVIEWER"}]},
    "clientScopes": [
        {
            "name": "campaign:approve",
            "protocol": "openid-connect",
            "attributes": {"include.in.token.scope": "true", "display.on.consent.screen": "false"},
        },
        {
            "name": "human-action:decide",
            "protocol": "openid-connect",
            "attributes": {"include.in.token.scope": "true", "display.on.consent.screen": "false"},
        },
    ],
    "clients": [{
        "clientId": "atlantis-human-api",
        "enabled": True,
        "publicClient": True,
        "standardFlowEnabled": False,
        "directAccessGrantsEnabled": True,
        "fullScopeAllowed": True,
        "protocol": "openid-connect",
        "defaultClientScopes": ["profile", "roles", "campaign:approve", "human-action:decide"],
        "protocolMappers": [
            {
                "name": "sub",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-property-mapper",
                "config": {
                    **mapper_common,
                    "user.attribute": "id",
                    "claim.name": "sub",
                    "jsonType.label": "String",
                },
            },
            {
                "name": "sub-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-sub-mapper",
                "config": mapper_common,
            },
            {
                "name": "tenant_id",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "config": {
                    **mapper_common,
                    "user.attribute": "tenant_id",
                    "claim.name": "tenant_id",
                    "jsonType.label": "String",
                    "multivalued": "false",
                },
            },
            {
                "name": "roles",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-realm-role-mapper",
                "config": {
                    **mapper_common,
                    "claim.name": "roles",
                    "jsonType.label": "String",
                    "multivalued": "true",
                    "usermodel.realmRoleMapping.rolePrefix": "",
                },
            },
            {
                "name": "audience",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-audience-mapper",
                "config": {**mapper_common, "included.client.audience": "atlantis-human-api"},
            },
        ],
    }],
    "users": [
        {
            "id": data["campaign_id"],
            "username": data["campaign_user"],
            "enabled": True,
            "emailVerified": True,
            "email": "campaign-approver@atlantis.local",
            "firstName": "Campaign",
            "lastName": "Approver",
            "requiredActions": [],
            "attributes": {"tenant_id": [tenant]},
            "realmRoles": ["CAMPAIGN_APPROVER"],
            "credentials": [{"type": "password", "value": data["campaign_password"], "temporary": False}],
        },
        {
            "id": data["reviewer_id"],
            "username": data["reviewer_user"],
            "enabled": True,
            "emailVerified": True,
            "email": "human-reviewer@atlantis.local",
            "firstName": "Human",
            "lastName": "Reviewer",
            "requiredActions": [],
            "attributes": {"tenant_id": [tenant]},
            "realmRoles": ["HUMAN_REVIEWER"],
            "credentials": [{"type": "password", "value": data["reviewer_password"], "temporary": False}],
        },
    ],
}
temporary = realm_path + ".tmp"
open(temporary, "w", encoding="utf-8").write(json.dumps(realm, separators=(",", ":")))
os.chmod(temporary, 0o644)
os.replace(temporary, realm_path)
PY

docker pull "$image_ref" >/dev/null
image_id="$(docker image inspect --format '{{.Id}}' "$image_ref")"
repo_digests="$(docker image inspect --format '{{join .RepoDigests ","}}' "$image_ref")"
[[ "$image_id" =~ ^sha256:[a-f0-9]{64}$ ]] || die "Keycloak immutable local image ID missing"
[[ "$repo_digests" == *"@$image_digest"* ]] || die "Keycloak registry digest mismatch after pull"
printf 'component=keycloak\ntag=%s\nrequested_digest=%s\nimage_id=%s\nrepo_digests=%s\nlicense=Apache-2.0\nsource_commit=289376b142480b4d600aca7acb1e4651862ed2a1\n' \
  "$image_tag" "$image_digest" "$image_id" "$repo_digests" > "$evidence_dir/keycloak-image-lock.txt"

docker volume inspect "$volume_name" >/dev/null 2>&1 || docker volume create "$volume_name" >/dev/null
docker rm -f "$container_name" >/dev/null 2>&1 || true

run_keycloak() {
  local admin_password
  admin_password="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['admin_password'])" "$credentials")"
  docker run -d --name "$container_name" --restart unless-stopped \
    --tmpfs /tmp:rw,noexec,nosuid,size=128m --cap-drop ALL \
    --security-opt no-new-privileges:true --pids-limit 256 --memory 768m \
    -p 127.0.0.1:8180:8080 -v "$volume_name:/opt/keycloak/data" \
    -v "$realm_file:/opt/keycloak/data/import/realm.json:ro" \
    -e KC_BOOTSTRAP_ADMIN_USERNAME=atlantis-bootstrap \
    -e "KC_BOOTSTRAP_ADMIN_PASSWORD=$admin_password" \
    -e "KC_HOSTNAME=$keycloak_base" -e KC_HTTP_ENABLED=true \
    "$image_id" start-dev --import-realm >/dev/null
}

wait_for_realm() {
  local ready=false
  for _ in {1..90}; do
    if curl --fail --silent --max-time 3 "$issuer/.well-known/openid-configuration" >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 2
  done
  [[ "$ready" == true ]] || die "Keycloak realm did not become ready"
}

run_keycloak
wait_for_realm
curl --fail --silent --max-time 5 "$issuer/.well-known/openid-configuration" \
  > "$evidence_dir/openid-configuration.json"

campaign_token="$runtime_dir/campaign_approver.token"
reviewer_token="$runtime_dir/human_reviewer.token"
token_response="$runtime_dir/oidc-token-response.json"
trap 'rm -f "$campaign_token" "$reviewer_token" "$token_response" "$runtime_dir/jwks.json"' EXIT

issue_token() {
  local user_key="$1" password_key="$2" output="$3"
  local username password
  username="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$credentials" "$user_key")"
  password="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$credentials" "$password_key")"
  curl --fail --silent --show-error --max-time 15 -X POST \
    "$issuer/protocol/openid-connect/token" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode grant_type=password --data-urlencode client_id="$audience" \
    --data-urlencode username="$username" --data-urlencode password="$password" > "$token_response"
  python3 - "$token_response" "$output" <<'PY'
import json
import os
import sys

source, target = sys.argv[1:]
token = json.load(open(source, encoding="utf-8")).get("access_token", "")
if token.count(".") != 2:
    raise SystemExit("OIDC access token missing")
open(target, "w", encoding="utf-8").write(token)
os.chmod(target, 0o400)
PY
  rm -f "$token_response"
}

issue_token campaign_user campaign_password "$campaign_token"
issue_token reviewer_user reviewer_password "$reviewer_token"

curl --fail --silent --max-time 10 "$issuer/protocol/openid-connect/certs" > "$runtime_dir/jwks.json"
python3 - "$runtime_dir/jwks.json" "$public_dir/public_keys.json" <<'PY'
import base64
import json
import os
import sys
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

source, target = sys.argv[1:]
jwks = json.load(open(source, encoding="utf-8"))
result = {}
def number(value):
    return int.from_bytes(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)), "big")
for key in jwks.get("keys", []):
    if key.get("kty") == "RSA" and key.get("use") == "sig" and key.get("alg") == "RS256":
        public = RSAPublicNumbers(number(key["e"]), number(key["n"])).public_key()
        result[key["kid"]] = public.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
if not result:
    raise SystemExit("RS256 signing key missing")
temporary = target + ".tmp"
open(temporary, "w", encoding="utf-8").write(json.dumps(result, separators=(",", ":")))
os.chmod(temporary, 0o644)
os.replace(temporary, target)
PY
rm -f "$runtime_dir/jwks.json"

python3 - "$ATLANTIS_ENV_FILE" "$issuer" "$audience" <<'PY'
import os
import sys

path, issuer, audience = sys.argv[1:]
updates = {
    "ATLANTIS_REQUIRE_HUMAN_OIDC": "true",
    "ATLANTIS_OIDC_ISSUER": issuer,
    "ATLANTIS_OIDC_AUDIENCE": audience,
    "ATLANTIS_OIDC_PUBLIC_KEYS_FILE": "/etc/atlantis/oidc/public_keys.json",
    "ATLANTIS_OIDC_CAMPAIGN_APPROVER_ROLE": "CAMPAIGN_APPROVER",
    "ATLANTIS_OIDC_HUMAN_REVIEWER_ROLE": "HUMAN_REVIEWER",
}
lines = open(path, encoding="utf-8").read().splitlines()
seen, output = set(), []
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
    if key in updates:
        if key not in seen:
            output.append(key + "=" + updates[key])
            seen.add(key)
    else:
        output.append(line)
for key, value in updates.items():
    if key not in seen:
        output.append(key + "=" + value)
temporary = path + ".oidc.tmp"
open(temporary, "w", encoding="utf-8").write("\n".join(output) + "\n")
os.chmod(temporary, 0o644)
os.replace(temporary, path)
PY

compose up -d --force-recreate crm_api orchestrator >/dev/null
for port in 8082 8083; do
  ready=false
  for _ in {1..30}; do
    if curl --fail --silent --max-time 2 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 2
  done
  [[ "$ready" == true ]] || die "Atlantis service on port $port did not become ready"
done

"$OPS_DIR/80_validate_pilot_controls.sh" --execute
docker inspect --format 'name={{.Name}} image={{.Image}} restart={{.HostConfig.RestartPolicy.Name}} readonly={{.HostConfig.ReadonlyRootfs}}' \
  "$container_name" > "$evidence_dir/keycloak-runtime.txt"
find "$evidence_dir" -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
  > "$evidence_dir/SHA256SUMS"
chmod 600 "$evidence_dir"/*
log "PASS Keycloak shadow OIDC and pilot control probe; evidence=$evidence_dir"
