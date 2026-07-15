FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CANOPY_MCP_HOST=0.0.0.0 \
    CANOPY_MCP_PORT=8000 \
    CANOPY_GRAPHHOPPER_URL=http://graphhopper:8989
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install . \
    && useradd --system --uid 10001 --home-dir /nonexistent canopy
USER canopy
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
  CMD python -c 'import socket; socket.create_connection(("127.0.0.1", 8000), 2).close()'
ENTRYPOINT ["canopy-mcp"]
