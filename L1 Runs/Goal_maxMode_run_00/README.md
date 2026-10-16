# Goal_maxMode_run_00 — compact run record

This folder retains the run documentation, reported best CAD, and compact supporting evidence. Results are model-reported findings, not independently validated conclusions.

## Best saved design

[Iteration 2 STEP](iteration_2/geometry_2/bracket_v3.step) is the authoritative saved geometry. The run reports 184.06 g and first mode 107.48 Hz (medium mesh), 107.23 Hz (fine mesh). Python files beside the STEP are historical source snapshots and analysis scripts; exact source-to-STEP generation provenance is unresolved. `build_v3.py` contains parameter notes rather than an executable reconstruction.

## Retained evidence

- [Final report](FINAL_REPORT.md) and [machine-readable results](results_final.json): original reported findings.
- [Run log](RUN_LOG.md), [prompt](prompt.txt), [operator instructions](operator-instructions.txt), [requirements snapshot](A15.json), and [run manifest](run-manifest.json): run context and provenance.
- [Iteration 2 FEA](iteration_2/FEA_2/): compact JSON summaries, solver logs, and `.dat` results. These are insufficient to independently recheck full stress fields without the archived raw outputs.
- [Iteration 1 DfM report](iteration_1/DfM_1/report.txt) and [violations](iteration_1/DfM_1/violations.csv): failed screening evidence.
- [Diagnostics](diagnostics/): artifact mappings, counters, preflight evidence, and recorded runtime failure.

## Status and limitations

The final report names iteration 2 as best, while iteration 2 DfM remains pending. The run log records Docker runtime failure and unverified completion. Neither the file name “FINAL_REPORT” nor reported numerical passes establishes an accepted design. Keep-out, fastener access, material assumptions, and other unresolved requirements remain as documented in the original report. No new FEA, DfM, or engineering validation was performed during cleanup. The monitoring automation was paused when inspected; its ACTIVE value in the historical manifest is stale.

## External archive

Removed files retain their original relative paths under:

`/Users/samkweskin/Desktop/Internship/Text-to-MfG Archives/Goal_maxMode_run_00/`

This includes other iterations, STL exports, raw solver inputs/results, meshes, diagnostic experiments, copied tools, container inspection dumps, transcripts, and the artifact collector. References in the original reports or source files to absent files, `/workspace/`, or discarded iteration folders refer to these historical artifacts in the archive; they are not live repository links. Original reports and source snapshots are preserved without rewriting their claims.

`ARCHIVE_MANIFEST.json` in the archive records every original file's size, SHA-256, and keep/archive disposition. Each archived copy was verified before its repository copy was removed. The archive is local and outside Git; it still consumes disk space and needs a separate backup if long-term retention is required.

The run-local `.gitignore` allows only the retained record and blocks regenerated bulk files. Cleanup did not stage, commit, push, or rewrite history.
