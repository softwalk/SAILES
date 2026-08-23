# Imagen base propietaria Atlantis — Python 3.12 + dependencias runtime pinadas.
#
# Propósito (FR-041 / component-lock): fijar por digest las dependencias que la
# imagen upstream python:3.12-slim-bookworm NO incluye (psycopg, pika, langgraph),
# de modo que los 7 servicios hereden una base inmutable y reproducible.
#
# Build:
#   docker build \
#     --build-arg PYTHON_BASE_IMAGE=python:3.12-slim-bookworm@sha256:a116514e... \
#     -t atlantis-python-base:0.9.0 \
#     -f deploy/proxmox/base/Dockerfile .
#
# Tras el build, fijar el digest resultante en .env como ATLANTIS_PYTHON_BASE_IMAGE.

ARG PYTHON_BASE_IMAGE
FROM ${PYTHON_BASE_IMAGE}

# Dependencias runtime y transitivas pinadas con hashes (FR-041).
# - psycopg v3:      repositorios PostgreSQL (crm, ledger, outbox, token, webhook).
# - pika:            broker RabbitMQ (outbox/inbox, channel consumer).
# - langgraph:       runtime del orquestador durable (langgraph_adapter).
COPY deploy/proxmox/base/requirements-runtime.lock /tmp/requirements-runtime.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements-runtime.lock \
    && rm /tmp/requirements-runtime.lock

# Verificación de importación en build (falla el build si falta algo).
RUN python -c "import psycopg, pika, langgraph; print('atlantis-python-base deps ok')"

LABEL org.opencontainers.image.title="atlantis-python-base" \
      org.opencontainers.image.version="0.9.0-rc4" \
      org.opencontainers.image.description="Python 3.12 + psycopg/pika/langgraph con hashes para Atlantis RC 0.9.0-rc4"
