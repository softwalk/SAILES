ARG PYTHON_BASE_IMAGE
FROM ${PYTHON_BASE_IMAGE}
RUN useradd --system --uid 10001 atlantis
WORKDIR /app
COPY shared/atlantis_contracts /app/atlantis_contracts
COPY services/model_gateway/app /app/app
USER 10001
ENV PYTHONPATH=/app PORT=8084
EXPOSE 8084
CMD ["python", "-m", "app.server"]
