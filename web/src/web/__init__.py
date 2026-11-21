"""Web UI: upload a manuscript, watch the reviewer's log live, read the review."""
import os
import tempfile
from pathlib import Path

import gradio as gr
import httpx

REVIEWER_URL = os.environ.get("REVIEWER_URL", "http://reviewer:8000")
MAX_LOG_CHARS = 200_000  # keep the log box responsive on very long runs


def review(pdf_path, venue):
    """Start a review job and stream (log, review markdown, review file) to the UI."""
    if not pdf_path:
        raise gr.Error("Please upload a PDF first.")

    with open(pdf_path, "rb") as f:
        r = httpx.post(
            f"{REVIEWER_URL}/jobs",
            files={"file": (Path(pdf_path).name, f, "application/pdf")},
            data={"venue": venue.strip() or "unspecified"},
            timeout=120,
        )
    if r.status_code != 200:
        raise gr.Error(f"Reviewer rejected the upload: {r.text}")
    job_id = r.json()["job_id"]

    log = ""
    yield log, "*Review in progress…*", None
    with httpx.stream("GET", f"{REVIEWER_URL}/jobs/{job_id}/logs", timeout=httpx.Timeout(30, read=None)) as s:
        for line in s.iter_lines():
            log = (log + line + "\n")[-MAX_LOG_CHARS:]
            yield log, "*Review in progress…*", None

    job = httpx.get(f"{REVIEWER_URL}/jobs/{job_id}", timeout=30).json()
    if job["status"] != "done":
        yield log, f"**Review failed:** {job.get('error') or 'unknown error'}", None
        return

    out = Path(tempfile.mkdtemp()) / "final_review.md"
    out.write_text(job["review"])
    yield log, job["review"], str(out)


with gr.Blocks(title="Automated Peer Reviewer") as demo:
    gr.Markdown("# Automated Peer Reviewer\nUpload a manuscript (PDF). The review runs end to end and can take a while.")
    with gr.Row():
        pdf = gr.File(label="Manuscript (PDF)", file_types=[".pdf"], type="filepath")
        with gr.Column():
            venue = gr.Textbox(label="Venue (optional)", placeholder="e.g. NeurIPS 2026 — leave empty for generic criteria")
            start = gr.Button("Start review", variant="primary")
    logs = gr.Textbox(label="Live log", lines=20, max_lines=20, autoscroll=True, interactive=False)
    gr.Markdown("## Review")
    result = gr.Markdown()
    download = gr.File(label="Download review (.md)")

    start.click(review, inputs=[pdf, venue], outputs=[logs, result, download])


def main() -> None:
    demo.queue(default_concurrency_limit=4).launch(
        server_name="0.0.0.0", server_port=int(os.environ.get("PORT", "7860"))
    )
