"""Runtime configuration helpers with Docker-secret support."""
import os
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit


def text_secret(name: str) -> str:
    file_name = os.getenv(name + "_FILE")
    if file_name:
        return Path(file_name).read_text(encoding="utf-8").strip()
    return os.getenv(name, "").strip()


def postgres_dsn() -> str:
    direct = os.getenv("ATLANTIS_DATABASE_URL", "").strip()
    if direct:
        return _postgres_tls_dsn(direct)
    password = text_secret("ATLANTIS_DATABASE_PASSWORD")
    if not password:
        return ""
    user = quote(os.getenv("ATLANTIS_DATABASE_USER", "atlantis_runtime"), safe="")
    password = quote(password, safe="")
    host = os.getenv("ATLANTIS_DATABASE_HOST", "postgres")
    port = os.getenv("ATLANTIS_DATABASE_PORT", "5432")
    database = os.getenv("ATLANTIS_DATABASE_NAME", "atlantis")
    return _postgres_tls_dsn(f"postgresql://{user}:{password}@{host}:{port}/{database}")


def _postgres_tls_dsn(dsn: str) -> str:
    production = os.getenv("ATLANTIS_ENV", "development") != "development"
    configured_mode = os.getenv("ATLANTIS_DATABASE_SSLMODE", "").strip()
    parts = urlsplit(dsn)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    mode = configured_mode or query.get("sslmode") or ("verify-full" if production else "")
    if production and mode != "verify-full":
        raise RuntimeError("POSTGRES_SSLMODE_VERIFY_FULL_REQUIRED")
    if mode:
        query["sslmode"] = mode
    for env_name, query_name in (
        ("ATLANTIS_DATABASE_SSLROOTCERT", "sslrootcert"),
        ("ATLANTIS_DATABASE_SSLCERT", "sslcert"),
        ("ATLANTIS_DATABASE_SSLKEY", "sslkey"),
    ):
        value = os.getenv(env_name, "").strip()
        if value:
            query[query_name] = value
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
