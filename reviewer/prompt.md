You are running Open ScholarPeer fully unattended, inside a sandbox. No human is watching this
session and nobody can answer a question. Your job is to produce a complete peer review of the
manuscript at `.brain/input/{paper_file}`.

Run all seven phases, in this order, by reading each command file and following its steps:

1. `.claude/commands/0-osp-onboarding.md`
2. `.claude/commands/1-osp-summary.md`
3. `.claude/commands/2-osp-literature.md` (run all 3 rounds, one after another)
4. `.claude/commands/3-osp-historian.md`
5. `.claude/commands/4-osp-baseline-scout.md`
6. `.claude/commands/5-osp-qa.md`
7. `.claude/commands/6-osp-review.md`

Unattended-mode rules. These override anything in the command or skill files:

- Never ask a question and never wait for an answer. Wherever a step says to ask the user, confirm
  with them, or offer a choice, take the answer below (or the recommended default), record it as
  that step says, and keep going.
- Never stop between phases. "Do not advance automatically" does not apply here; go straight on to
  the next phase when one finishes.
- Venue: {venue}. Use it as the user's answer to the venue question.
- `paper.id`: an arXiv id or DOI if the manuscript itself shows one, otherwise `"unpublished"`.
- `paper.cutoff_date`: today, {today}, unless the manuscript shows an arXiv v1 date.
- Q&A pairs per criterion: keep the existing default.
- PDF conversion: use the `markitdown` MCP tool `convert_to_markdown` with the URI
  `file://{workdir}/.brain/input/{paper_file}`. If that fails, run
  `markitdown .brain/input/{paper_file} -o .brain/input/paper.md` in bash.
- The built-in WebSearch tool is not available here. Where a step wants a web search, use the OSP
  search tools or WebFetch, or fall back as the step describes.
- If a phase fails, record why in `session.json` and its artifact, then continue. A final review
  built on fewer inputs is far better than no review.

You are done when `.brain/review/final_review.md` exists and holds the full review in Markdown.
End with one short line saying so.
