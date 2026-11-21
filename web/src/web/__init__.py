"""Web UI: upload a manuscript, watch the reviewer's log live, read the review."""
import os
import tempfile
from pathlib import Path

import gradio as gr
import httpx

REVIEWER_URL = os.environ.get("REVIEWER_URL", "http://reviewer:8000")
MAX_LOG_CHARS = 200_000  # keep the log box responsive on very long runs

# While a file uploads, Gradio shows "Uploading 1 file..." with a progress ring that
# stays still. Animate it: turn the ring into a spinner and sweep a bar under the label.
CSS = """
#manuscript .uploading { display: block; }
#manuscript .progress-bar {  /* Gradio draws the ring as a gradient; redraw it as a spinner */
  background: radial-gradient(closest-side, var(--block-background-fill) 64%, transparent 66%),
              conic-gradient(var(--color-accent) 0 25%, var(--color-accent-soft) 0) !important;
  animation: upload-spin 0.8s linear infinite;
}
#manuscript .uploading::after {
  content: "";
  display: block;
  width: min(220px, 60%);
  height: 3px;
  margin: 10px auto 0;
  border-radius: 2px;
  background: linear-gradient(90deg, transparent, var(--color-accent), transparent) 0 0 / 40% 100% no-repeat,
              var(--color-accent-soft);
  animation: upload-sweep 1.2s ease-in-out infinite;
}
@keyframes upload-spin { to { transform: rotate(360deg); } }
@keyframes upload-sweep { from { background-position: -40% 0, 0 0; } to { background-position: 140% 0, 0 0; } }
@media (prefers-reduced-motion: reduce) {
  #manuscript .progress-bar, #manuscript .uploading::after { animation: none !important; }
}
"""


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
        pdf = gr.File(label="Manuscript (PDF)", file_types=[".pdf"], type="filepath", elem_id="manuscript")
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
        server_name="0.0.0.0", server_port=int(os.environ.get("PORT", "7860")), css=CSS
    )
