# Pin image versions for repeatable builds. Pin these tags to immutable digests
# in the release pipeline as well.
FROM python:3.14.3-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.9.20 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache --no-dev
COPY . .

RUN groupadd --system app && useradd --system --gid app --home-dir /app app \
    && chmod +x entrypoint.sh \
    && chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

USER app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]
