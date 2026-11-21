FROM ghcr.io/astral-sh/uv:0.9.7-python3.13-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy GRADIO_ANALYTICS_ENABLED=False
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --no-dev
COPY src ./src
RUN uv sync --locked --no-dev
RUN useradd --create-home web
USER web
EXPOSE 7860
CMD ["/app/.venv/bin/web"]
