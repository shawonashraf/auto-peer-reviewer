# auto-peer-reviewer

A sandboxed (containerised) manuscript peer reviewer which uses claude code with a custom LLM endpoint so that you can get an LLM driven peer review of your manuscript without exposing the contents.

The review is done by [Open ScholarPeer](https://github.com/amirkiarafiei/open-scholar-peer) running
inside Claude Code, which talks to your own LLM endpoint. Everything runs in Docker.

## Services

| Service     | What it does                                                                                     | Published port |
|-------------|--------------------------------------------------------------------------------------------------|----------------|
| `web`       | Gradio UI: upload a PDF, stream the log, show and download the review.                           | `7860`         |
| `reviewer`  | Claude Code + Open ScholarPeer behind a small job API. Each job runs in its own folder, as a non-root user. | none |
| `llm-proxy` | LiteLLM. Takes the Anthropic API calls Claude Code makes and forwards them to your endpoint. The only service that holds the API key. | none |

## Run

```bash
cp .env.example .env   # fill in LLM_API_KEY, LLM_BASE_URL, MODEL_NAME
# for the first run
docker compose up -d --build
# for subsequent runs
docker compose up
```

> [!NOTE]
> If running inside WSL, please use `docker.exe` instead of `docker` in the commands stated above.

Open <http://localhost:7860>.

> [!TIP]
> LLM inference endpoints can be Anthropic or OpenAI compatible. We've a proxy for that in this project, which will dynamically route the requests based on their compatibility, so that, you don't have to worry about any issues with claude code.



## How a review runs

1. `web` sends the PDF to `reviewer` (`POST /jobs`).
2. `reviewer` copies a prepared Open ScholarPeer workspace to `/data/jobs/<id>/workspace`, puts the PDF in `.brain/input/`, and runs `claude -p` with [reviewer/prompt.md](reviewer/prompt.md). The prompt runs all seven phases without stopping and answers the questions the protocol would normally ask a person.
3. Claude Code's JSON event stream is turned into a readable log, which `web` streams (`GET /jobs/<id>/logs`).
4. When `.brain/review/final_review.md` exists, `web` shows it (`GET /jobs/<id>`).

> [!IMPORTANT] 
> All the intermediate artifacts (summary, literature, baselines, Q&A) stay in the `jobs` volume under each job's `.brain/` inside the container.

## Limits

- Claude Code's built-in WebSearch only works against Anthropic's own API, so it is turned off. Literature search uses Open ScholarPeer's paper databases (arXiv, Semantic Scholar, OpenAlex, Europe PMC, Zenodo). Google Scholar is left out because it usually blocks server IPs.
- A full review takes a while (tens of minutes). Jobs time out after `REVIEW_TIMEOUT_SECONDS` (default 2 h).
- Jobs that are running when `reviewer` restarts are marked failed.
