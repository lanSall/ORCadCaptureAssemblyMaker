"""MCP server: MATLAB Engine bridge for PSpice result processing.

Loads CSV/trace data produced by extract_sim_results (or any path) into a
persistent MATLAB session and runs analysis code there.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

import sim_lib

mcp = FastMCP("matlab-mcp-server")

_lock = threading.Lock()
_eng: Any = None


def _ensure_engine():
    """Start a shared MATLAB Engine session if needed."""
    global _eng
    if _eng is not None:
        return _eng
    import matlab.engine

    _eng = matlab.engine.start_matlab()
    return _eng


def _quit_engine() -> None:
    global _eng
    if _eng is not None:
        try:
            _eng.quit()
        except Exception:
            pass
        _eng = None


def _matlab_str(path: Path | str) -> str:
    """Escape a filesystem path for use inside a MATLAB single-quoted string."""
    return str(Path(path).resolve()).replace("'", "''")


def _safe_varname(name: str) -> str:
    """Turn a PSpice column like V(VOUT) into a legal MATLAB identifier."""
    s = re.sub(r"[^0-9A-Za-z_]", "_", name.strip())
    if not s:
        s = "var"
    if s[0].isdigit():
        s = "v_" + s
    return s


def _resolve_pspice_csv(name_or_path: str) -> Path:
    """Accept an absolute CSV path or a PSpice profile name (Lab5_TRAN)."""
    p = Path(name_or_path)
    if p.is_file():
        return p.resolve()
    # Profile name → <run_dir>/<name>_traces.csv
    run_dir = sim_lib.DEFAULT_PSPICE_DIR / name_or_path
    csv_path = run_dir / f"{name_or_path}_traces.csv"
    if csv_path.is_file():
        return csv_path.resolve()
    # Any *_traces.csv in that folder
    if run_dir.is_dir():
        matches = sorted(run_dir.glob("*_traces.csv"))
        if matches:
            return matches[0].resolve()
    raise FileNotFoundError(
        f"No PSpice CSV for '{name_or_path}'. "
        f"Expected file or {csv_path}"
    )


def _eval_capture(eng, code: str) -> str:
    """Run MATLAB code and capture textual output (diary-style via evalc)."""
    # evalc returns the printed output as a char array
    out = eng.evalc(code, nargout=1)
    if out is None:
        return ""
    return str(out)


@mcp.tool()
def matlab_ping() -> str:
    """Start MATLAB Engine if needed and return version / ready status."""
    with _lock:
        try:
            eng = _ensure_engine()
            ver = eng.eval("version", nargout=1)
            return json.dumps({"ok": True, "version": str(ver)}, indent=2)
        except Exception as exc:
            _quit_engine()
            return json.dumps({"ok": False, "error": str(exc)}, indent=2)


@mcp.tool()
def matlab_eval(expression: str) -> str:
    """Evaluate a MATLAB expression and return its string form (disp).

    Prefer matlab_run for multi-statement scripts with no return value.
    """
    expr = expression.strip()
    if not expr:
        return json.dumps({"ok": False, "error": "empty expression"})
    with _lock:
        try:
            eng = _ensure_engine()
            text = _eval_capture(eng, f"disp({expr})")
            return json.dumps({"ok": True, "output": text.rstrip()}, indent=2)
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, indent=2)


@mcp.tool()
def matlab_run(code: str) -> str:
    """Execute one or more MATLAB statements in the shared session.

    Captures printed output via evalc. Workspace state persists across calls.
    """
    code = code.strip()
    if not code:
        return json.dumps({"ok": False, "error": "empty code"})
    with _lock:
        try:
            eng = _ensure_engine()
            text = _eval_capture(eng, code)
            return json.dumps({"ok": True, "output": text.rstrip()}, indent=2)
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, indent=2)


@mcp.tool()
def load_pspice_csv(
    name_or_path: str,
    workspace_var: str = "pspice",
) -> str:
    """Load a PSpice traces CSV into the MATLAB workspace as a table + vectors.

    name_or_path: absolute path to *_traces.csv, or a profile name like Lab5_TRAN
      (resolves under ORCadCPMTest-PSpiceFiles/SCHEMATIC1/<name>/).

    Creates:
      <workspace_var>          — table from readtable
      <workspace_var>_TIME/... — numeric column vectors with safe names
    """
    var = _safe_varname(workspace_var)
    try:
        csv_path = _resolve_pspice_csv(name_or_path)
    except FileNotFoundError as exc:
        return json.dumps({"ok": False, "error": str(exc)}, indent=2)

    # Peek headers so we can report / create vectors
    header = csv_path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    cols = [c.strip() for c in header.split(",") if c.strip()]
    safe_cols = [_safe_varname(c) for c in cols]
    vn_list = ", ".join("'" + c.replace("'", "''") + "'" for c in safe_cols)
    # Table columns are forced to safe names; also export plain vectors.
    assign_vecs = "\n".join(f"{var}_{sc} = {var}.{sc};" for sc in safe_cols)
    matlab_code = f"""
csvPath = '{_matlab_str(csv_path)}';
opts = detectImportOptions(csvPath);
opts.VariableNames = {{{vn_list}}};
{var} = readtable(csvPath, opts);
{assign_vecs}
fprintf('loaded %d rows, %d cols from %s\\n', height({var}), width({var}), csvPath);
"""

    with _lock:
        try:
            eng = _ensure_engine()
            text = _eval_capture(eng, matlab_code)
            return json.dumps(
                {
                    "ok": True,
                    "csv": str(csv_path),
                    "table": var,
                    "columns_original": cols,
                    "columns_safe": safe_cols,
                    "vectors": [f"{var}_{sc}" for sc in safe_cols],
                    "output": text.rstrip(),
                },
                indent=2,
            )
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, indent=2)


@mcp.tool()
def process_pspice_in_matlab(
    name_or_path: str,
    analysis_code: str,
    workspace_var: str = "pspice",
) -> str:
    """Load a PSpice CSV into MATLAB, then run analysis_code in that session.

    Convenience wrapper: load_pspice_csv → matlab_run(analysis_code).
    Column vectors are named <workspace_var>_<SAFE_COL> (e.g. pspice_TIME,
    pspice_V_VOUT_). The table itself is <workspace_var>.
    """
    load_result = json.loads(load_pspice_csv(name_or_path, workspace_var))
    if not load_result.get("ok"):
        return json.dumps(load_result, indent=2)

    run_result = json.loads(matlab_run(analysis_code))
    return json.dumps(
        {
            "ok": bool(run_result.get("ok")),
            "load": load_result,
            "analysis_output": run_result.get("output", ""),
            "error": run_result.get("error"),
        },
        indent=2,
    )


@mcp.tool()
def matlab_workspace() -> str:
    """List variables currently in the MATLAB base workspace (whos)."""
    with _lock:
        try:
            eng = _ensure_engine()
            text = _eval_capture(eng, "whos")
            return json.dumps({"ok": True, "output": text.rstrip()}, indent=2)
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, indent=2)


@mcp.tool()
def matlab_quit_engine() -> str:
    """Shut down the shared MATLAB Engine session."""
    with _lock:
        _quit_engine()
    return json.dumps({"ok": True, "message": "MATLAB Engine quit"}, indent=2)


if __name__ == "__main__":
    mcp.run()
