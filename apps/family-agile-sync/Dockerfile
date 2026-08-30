# Build context: repository root (mirrors apps/forge-site/Dockerfile).
FROM python:3.12-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

RUN addgroup --system --gid 1001 app && \
    adduser --system --uid 1001 --ingroup app app

COPY apps/family-agile-sync/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/family-agile-sync/src ./src

USER app
ENTRYPOINT ["python", "-m", "family_agile_sync"]
CMD ["pull-completions"]
