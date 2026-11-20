FROM python:3.15-slim
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG APT_MIRROR=https://deb.debian.org
RUN sed -i "s|http://deb.debian.org|$APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends chromium fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 worker
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.7.6 && uv export --frozen --no-dev --no-emit-project --extra worker -o /tmp/requirements.txt && pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt
COPY src/loop_sandbox/__init__.py ./src/loop_sandbox/__init__.py
COPY src/loop_sandbox/contracts ./src/loop_sandbox/contracts
COPY src/loop_sandbox/worker ./src/loop_sandbox/worker
ENV PYTHONPATH=/app/src HOME=/tmp CHROMIUM_EXECUTABLE=/usr/bin/chromium
USER worker
CMD ["uvicorn", "loop_sandbox.worker.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
