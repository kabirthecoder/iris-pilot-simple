# Example outputs

Produced by `make run` on the committed fixture, then copied here so they can be read without
running anything. They are regenerated in `out/` on every run.

| File | What it shows |
|---|---|
| `bess-DE-P008.md` / `.pdf` | A two-page BESS dossier. P008 passes, and is flagged **borderline**: 2,997 m to the substation against a 3,000 m limit, within ±7.5 m positional uncertainty |
| `peat-DE-P009.md` / `.pdf` | A two-page peatland dossier with the drained peat area and indicative eco-points |
| `last_run.json` | The manifest of a successful run: every stage with timestamps, duration and counts, the rejected rows with reasons, and the state of each output |
| `READ_ME_FIRST.txt` | The one-sentence verdict for non-technical readers after that run |
| `failed_run.json` | The manifest after a failed run (no accepted substations): the first stage failed, the rest were skipped, and all outputs are STALE |
| `READ_ME_FIRST-after-failed-run.txt` | The verdict after that failed run: "DO NOT USE …" |
