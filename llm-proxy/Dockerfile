# LiteLLM proxy: the only service holding the LLM API key.
# Exposes the Anthropic /v1/messages API that Claude Code speaks and forwards it to the
# custom endpoint. It detects at startup whether that endpoint speaks OpenAI or Anthropic.
FROM python:3.13-slim
RUN pip install --no-cache-dir "litellm[proxy]==1.108.1"
COPY openai.yaml anthropic.yaml /app/
COPY entrypoint.sh detect_format.py /app/
EXPOSE 4000
CMD ["sh", "/app/entrypoint.sh"]
