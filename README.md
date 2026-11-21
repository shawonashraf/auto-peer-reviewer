# auto-peer-reviewer

Upload a paper manuscript (PDF), watch the review run live, and get a detailed peer review in Markdown.

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
docker compose up -d --build
```

Open <http://localhost:7860>.

`LLM_API_FORMAT` says what your endpoint speaks:

- `auto` (default): at startup the proxy sends a 1-token request in each format and uses the first that works. Anthropic is tried first, since passing calls through beats translating them. If neither works, the proxy exits and prints both status codes (`docker compose logs llm-proxy`).
- `openai`: an OpenAI-compatible endpoint, e.g. `https://host/v1`. The proxy translates to `/chat/completions`.
- `anthropic`: an Anthropic-compatible endpoint. The proxy passes calls through.

The model must support tool calling.

## How a review runs

1. `web` sends the PDF to `reviewer` (`POST /jobs`).
2. `reviewer` copies a prepared Open ScholarPeer workspace to `/data/jobs/<id>/workspace`, puts the PDF in `.brain/input/`, and runs `claude -p` with [reviewer/prompt.md](reviewer/prompt.md). The prompt runs all seven phases without stopping and answers the questions the protocol would normally ask a person.
3. Claude Code's JSON event stream is turned into a readable log, which `web` streams (`GET /jobs/<id>/logs`).
4. When `.brain/review/final_review.md` exists, `web` shows it (`GET /jobs/<id>`).

All the intermediate artifacts (summary, literature, baselines, Q&A) stay in the `jobs` volume under each job's `.brain/`.

## Limits

- Claude Code's built-in WebSearch only works against Anthropic's own API, so it is turned off. Literature search uses Open ScholarPeer's paper databases (arXiv, Semantic Scholar, OpenAlex, Europe PMC, Zenodo). Google Scholar is left out because it usually blocks server IPs.
- A full review takes a while (tens of minutes). Jobs time out after `REVIEW_TIMEOUT_SECONDS` (default 2 h).
- Jobs that are running when `reviewer` restarts are marked failed.
