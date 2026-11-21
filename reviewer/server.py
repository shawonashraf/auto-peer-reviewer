"""Job API around Claude Code + Open ScholarPeer.

POST /jobs              upload a PDF, start a review, get a job id
GET  /jobs/{id}/logs    stream the human-readable log until the job ends
GET  /jobs/{id}         job status, plus the final review once it exists

Each job lives in its own directory under JOBS_DIR:
    workspace/   copy of the OSP template; Claude Code runs here
    log.txt      readable log, streamed to the web UI
    status.json  {"status": queued|running|done|failed, "error": ...}
"""
import asyncio
import datetime as dt
import json
import os
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

JOBS_DIR = Path(os.environ.get("JOBS_DIR", "/data/jobs"))
TEMPLATE = Path("/opt/workspace-template")
PROMPT = Path(__file__).with_name("prompt.md").read_text()
MAX_PDF_BYTES = int(os.environ.get("MAX_PDF_MB", "50")) * 1024 * 1024
TIMEOUT = int(os.environ.get("REVIEW_TIMEOUT_SECONDS", "7200"))
SLOTS = asyncio.Semaphore(int(os.environ.get("MAX_CONCURRENT_JOBS", "2")))

app = FastAPI()
RUNNING: set[asyncio.Task] = set()  # keep references so tasks are not garbage-collected


@app.on_event("startup")
def fail_interrupted_jobs() -> None:
    """A job still queued/running at startup was cut off by a restart; say so."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    for d in JOBS_DIR.iterdir():
        if (d / "status.json").is_file() and read_status(d)["status"] in ("queued", "running"):
            log(d, "[job] interrupted by a reviewer restart")
            write_status(d, "failed", "interrupted by a reviewer restart")


# ---------- LLM wiring ----------

def claude_env() -> dict:
    """Environment for the claude process: every model slot goes to the llm-proxy service."""
    model = os.environ["MODEL_NAME"]
    env = dict(os.environ)
    env.update(
        ANTHROPIC_BASE_URL=os.environ.get("LLM_PROXY_URL", "http://llm-proxy:4000"),
        ANTHROPIC_AUTH_TOKEN="proxy",  # the real key lives only in llm-proxy
        ANTHROPIC_MODEL=model,
        ANTHROPIC_DEFAULT_OPUS_MODEL=model,
        ANTHROPIC_DEFAULT_SONNET_MODEL=model,
        ANTHROPIC_DEFAULT_HAIKU_MODEL=model,
        CLAUDE_CODE_SUBAGENT_MODEL=model,
    )
    return env


# ---------- job files ----------

def job_dir(job_id: str) -> Path:
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(404, "unknown job")
    d = JOBS_DIR / job_id
    if not d.is_dir():
        raise HTTPException(404, "unknown job")
    return d


def read_status(d: Path) -> dict:
    return json.loads((d / "status.json").read_text())


def write_status(d: Path, status: str, error: str | None = None) -> None:
    (d / "status.json").write_text(json.dumps({"status": status, "error": error}))


def log(d: Path, line: str) -> None:
    with open(d / "log.txt", "a") as f:
        f.write(line.rstrip("\n") + "\n")


def make_workspace(d: Path, pdf: bytes, filename: str) -> Path:
    ws = d / "workspace"
    # Copy everything except the MCP venv, which is large and read-only; link to it instead.
    shutil.copytree(TEMPLATE, ws, ignore=shutil.ignore_patterns(".open-scholar-peer"))
    (ws / ".open-scholar-peer").symlink_to(TEMPLATE / ".open-scholar-peer")
    (ws / ".brain" / "input").mkdir(parents=True, exist_ok=True)
    (ws / ".brain" / "input" / filename).write_bytes(pdf)
    return ws


# ---------- turning stream-json into a readable log ----------

def short(value, n: int = 200) -> str:
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def describe_tool(name: str, inp: dict) -> str:
    for key in ("file_path", "command", "pattern", "url", "query", "description", "skill"):
        if key in inp:
            return f"{name}: {short(inp[key], 160)}"
    return f"{name}: {short(inp, 160)}"


def render_event(ev: dict) -> list[str]:
    kind = ev.get("type")
    if kind == "system" and ev.get("subtype") == "init":
        servers = ", ".join(f"{s['name']}={s['status']}" for s in ev.get("mcp_servers", []))
        return [f"[init] model={ev.get('model')} tools={len(ev.get('tools', []))} mcp: {servers}"]
    if kind == "assistant":
        out = []
        for block in ev.get("message", {}).get("content", []):
            if block.get("type") == "text" and block.get("text", "").strip():
                out.append(f"[claude] {block['text'].strip()}")
            elif block.get("type") == "tool_use":
                out.append(f"[tool] {describe_tool(block['name'], block.get('input', {}))}")
        return out
    if kind == "user":
        out = []
        for block in ev.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_result":
                content = block.get("content")
                if isinstance(content, list):
                    content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                tag = "[error]" if block.get("is_error") else "  ->"
                out.append(f"{tag} {short(content or '')}")
        return out
    if kind == "result":
        return [
            f"[result] {ev.get('subtype')} after {ev.get('num_turns')} turns, "
            f"{round((ev.get('duration_ms') or 0) / 60000, 1)} min"
        ]
    return []


# ---------- running a job ----------

async def run_job(d: Path, ws: Path, paper_file: str, venue: str) -> None:
    async with SLOTS:
        write_status(d, "running")
        log(d, f"[job] started {dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M:%S} UTC")
        prompt = PROMPT.format(
            paper_file=paper_file,
            venue=venue,
            today=dt.date.today().isoformat(),
            workdir=ws,
        )
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "stream-json", "--verbose",
            "--permission-mode", "bypassPermissions",
            "--mcp-config", str(ws / ".mcp.json"), "--strict-mcp-config",
            "--disallowedTools", "WebSearch",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=ws, env=claude_env(),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                limit=16 * 1024 * 1024,
            )
            async with asyncio.timeout(TIMEOUT):
                async for raw in proc.stdout:
                    line = raw.decode(errors="replace").strip()
                    if not line:
                        continue
                    try:
                        for out in render_event(json.loads(line)):
                            log(d, out)
                    except json.JSONDecodeError:
                        log(d, f"[stderr] {short(line, 500)}")
                code = await proc.wait()
        except TimeoutError:
            proc.kill()
            log(d, f"[job] timed out after {TIMEOUT}s")
            write_status(d, "failed", f"timed out after {TIMEOUT}s")
            return
        except Exception as e:  # report anything else to the user instead of hanging
            log(d, f"[job] crashed: {e}")
            write_status(d, "failed", str(e))
            return

        if (ws / ".brain/review/final_review.md").is_file():
            log(d, "[job] final review written")
            write_status(d, "done")
        else:
            log(d, f"[job] claude exited with code {code} and no final review")
            write_status(d, "failed", f"no final review (claude exit code {code})")


# ---------- HTTP ----------

@app.post("/jobs")
async def create_job(file: UploadFile, venue: str = Form("unspecified")):
    pdf = await file.read(MAX_PDF_BYTES + 1)
    if len(pdf) > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF too large")
    if not pdf.startswith(b"%PDF"):
        raise HTTPException(400, "file is not a PDF")
    job_id = str(uuid.uuid4())
    d = JOBS_DIR / job_id
    d.mkdir(parents=True)
    (d / "log.txt").touch()
    write_status(d, "queued")
    ws = make_workspace(d, pdf, "paper.pdf")
    venue = " ".join(venue.split())[:200] or "unspecified"
    log(d, f"[job] {job_id} queued, venue: {venue}")
    task = asyncio.create_task(run_job(d, ws, "paper.pdf", venue))
    RUNNING.add(task)
    task.add_done_callback(RUNNING.discard)
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    d = job_dir(job_id)
    status = read_status(d)
    review = d / "workspace/.brain/review/final_review.md"
    status["review"] = review.read_text() if review.is_file() else None
    return status


@app.get("/jobs/{job_id}/logs")
async def stream_logs(job_id: str):
    d = job_dir(job_id)

    async def follow():
        with open(d / "log.txt") as f:
            while True:
                line = f.readline()
                if line:
                    yield line
                    continue
                if read_status(d)["status"] in ("done", "failed"):
                    yield f.read()
                    return
                await asyncio.sleep(0.5)

    return StreamingResponse(follow(), media_type="text/plain")


@app.get("/health")
def health():
    return {"ok": True}
