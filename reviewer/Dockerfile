# Reviewer: Claude Code + Open ScholarPeer, wrapped in a small job API.
FROM node:22-bookworm-slim

ARG CLAUDE_CODE_VERSION=2.1.318
ARG OSP_REPO=https://github.com/amirkiarafiei/open-scholar-peer
ARG OSP_COMMIT=fa71703d004f21e63d79a81b06c36e9ffb2afa0a
# google_scholar is left out: it scrapes, and is usually blocked from server IPs.
ARG OSP_SOURCES=arxiv,semantic_scholar,openalex,europepmc,zenodo

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-venv git ca-certificates ripgrep jq \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} && npm cache clean --force

# Open ScholarPeer, installed for Claude Code into a template workspace.
# Each review job gets a copy of this template.
RUN git clone ${OSP_REPO} /opt/osp && git -C /opt/osp checkout ${OSP_COMMIT}
RUN mkdir -p /opt/workspace-template \
 && cd /opt/workspace-template \
 && bash /opt/osp/install.sh --dir /opt/workspace-template --tool claude --sources ${OSP_SOURCES} \
 && chmod -R a+rX /opt/workspace-template  # its .env is 600; it holds only OSP_SOURCES, no secrets

# markitdown for PDF -> markdown. Own venv: markitdown-mcp needs mcp>=2, OSP pins mcp<2.
RUN python3 -m venv /opt/markitdown \
 && /opt/markitdown/bin/pip install --no-cache-dir "markitdown[pdf]==0.1.9" "markitdown-mcp==0.0.1a8"

# Job API.
COPY requirements.txt /opt/app/requirements.txt
RUN python3 -m venv /opt/app/.venv \
 && /opt/app/.venv/bin/pip install --no-cache-dir -r /opt/app/requirements.txt

# Register markitdown next to OSP's own MCP servers.
COPY add_markitdown_mcp.py /opt/app/
RUN python3 /opt/app/add_markitdown_mcp.py /opt/workspace-template/.mcp.json

COPY server.py prompt.md /opt/app/

# Claude Code refuses to skip permission prompts as root, so run as a normal user.
RUN useradd --create-home --shell /bin/bash reviewer \
 && mkdir -p /data/jobs && chown -R reviewer:reviewer /data
USER reviewer
ENV PATH="/opt/markitdown/bin:${PATH}" \
    JOBS_DIR=/data/jobs \
    DISABLE_AUTOUPDATER=1 \
    DISABLE_TELEMETRY=1 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

WORKDIR /opt/app
EXPOSE 8000
CMD ["/opt/app/.venv/bin/uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
