# OrCAD Capture Assembly Maker / tcl-mcp-server

MCP servers and helpers for OrCAD Capture Tcl automation, PSpice simulation, and MATLAB post-processing.

## Layout

```
server.py              # OrCAD Capture MCP (execute_tcl, run_sim, …)
matlab_mcp.py          # MATLAB Engine MCP (load PSpice CSV, plot/analyze)
sim_lib.py             # PSpice .sim / .cir / psp_cmd helpers
placement_lib.py       # Capture place/wire helpers + recipe builders
parts_catalog.json     # Lookup: OLB paths, props, recipes, page bounds, crash rules
pin_offsets.json       # Cached pin hotspot offsets (inches)
CaptureMCPPortConnection  # Capture-side Tcl socket server (port 9020)

scripts/               # Lab renderers, Lab3 runner, Tcl examples
labs/
  lab2_pages/ …        # Lab PDF page / schematic references
  lab3_pages/
  lab3_results/        # Lab3 deliverables (figures, CSV, Word report, netlists)
  lab5_pages/
  lab8_pages/
  lab9_pages/
  lab9_results/
  examples/            # Small smoke-test artifacts
```

## Parts catalog (efficiency)

Before placing in Capture, look up the part:

```bash
python -c "from placement_lib import describe_part; print(describe_part('Q2N3904'))"
python -c "from placement_lib import catalog; print(list(catalog()['parts']))"
```

Build Lab9 CE amp Tcl lists locally (then send via MCP in small batches):

```bash
python -c "from placement_lib import build_ce_amp_fig5, chunked, mcp_delay_ms; print(len(build_ce_amp_fig5())); print(mcp_delay_ms('place'))"
```

Keep part origins inside `parts_catalog.json` → `page.safe_xy_inches` or they land off-page.

## Cursor MCP

Point Cursor MCP config at:

- OrCAD Capture: `python -u …/server.py`
- MATLAB Engine: Python 3.12 with `matlabengine` → `python -u …/matlab_mcp.py`

Capture must run `CaptureMCPPortConnection` (listens on `localhost:9020`).

## Lab 3 results

Word report: `labs/lab3_results/ECEN3314_Lab3_Simulation_Results.docx`

Regenerate plots/CSV:

```bash
python scripts/lab3_run_sims.py
python scripts/build_lab3_docx.py
```
