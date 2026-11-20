FROM python:3.12-slim
ARG PIP_INDEX_URL=https://pypi.org/simple
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.7.6 && uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt && pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt
COPY src/loop_sandbox/__init__.py ./src/loop_sandbox/__init__.py
COPY src/loop_sandbox/contracts ./src/loop_sandbox/contracts
COPY src/loop_sandbox/server ./src/loop_sandbox/server
COPY src/loop_sandbox/runtime ./src/loop_sandbox/runtime
COPY src/loop_sandbox/integrations ./src/loop_sandbox/integrations
ENV PYTHONPATH=/app/src
LABEL org.opencontainers.image.source="https://github.com/JimmyDi/loop-sandbox" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.title="Loop Sandbox API"
CMD ["uvicorn", "loop_sandbox.server.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
