# OrCAD Capture Assembly Maker / tcl-mcp-server

MCP servers and helpers for OrCAD Capture Tcl automation, PSpice simulation, and MATLAB post-processing.

## Layout

```
server.py              # OrCAD Capture MCP (execute_tcl, run_sim, …)
matlab_mcp.py          # MATLAB Engine MCP (load PSpice CSV, plot/analyze)
sim_lib.py             # PSpice .sim / .cir / psp_cmd helpers
placement_lib.py       # Capture place/wire helpers
pin_offsets.json       # Cached pin hotspot offsets (inches)
CaptureMCPPortConnection  # Capture-side Tcl socket server (port 9020)

scripts/               # Lab renderers, Lab3 runner, Tcl examples
labs/
  lab2_pages/ …        # Lab PDF page / schematic references
  lab3_pages/
  lab3_results/        # Lab3 deliverables (figures, CSV, Word report, netlists)
  lab5_pages/
  lab8_pages/
  examples/            # Small smoke-test artifacts
```

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
