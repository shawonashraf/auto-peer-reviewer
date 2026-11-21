# LiteLLM proxy: the only service holding the LLM API key.
# Exposes the Anthropic /v1/messages API that Claude Code speaks and forwards it to the
# custom endpoint, translating to OpenAI format when LLM_API_FORMAT=openai.
FROM python:3.13-slim
RUN pip install --no-cache-dir "litellm[proxy]==1.108.1"
COPY openai.yaml anthropic.yaml /app/
COPY entrypoint.sh /app/
EXPOSE 4000
CMD ["sh", "/app/entrypoint.sh"]
