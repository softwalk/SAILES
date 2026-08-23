ARG PYTHON_BASE_IMAGE
FROM ${PYTHON_BASE_IMAGE}
RUN useradd --system --uid 10001 atlantis
WORKDIR /app
COPY shared/atlantis_contracts /app/atlantis_contracts
COPY services/channel_adapters/app /app/app
USER 10001
ENV PYTHONPATH=/app
CMD ["python", "-m", "app.server"]
