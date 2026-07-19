"""PSpice simulation profile + CLI run + result extraction.

Bypasses Capture's fragile ASP-client sim APIs by:
1. Writing a proper .sim file (for Capture UI)
2. Registering it cleanly in the .opj
3. Building a standalone .cir from SCHEMATIC1.net + analysis
4. Running psp_cmd.exe headless
5. Parsing .PRINT tables / CSDF and plotting PNG
"""

from __future__ import annotations

import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PSP_CMD = Path(r"C:\Cadence\OrCADX_25.1\tools\bin\psp_cmd.exe")
DEFAULT_PROJECT = Path(
    r"C:\Users\lance\AppData\Roaming\SPB_Data\cdssetup\workspace\projects\orcadcpmtest\1"
)
DEFAULT_OPJ = DEFAULT_PROJECT / "ORCadCPMTest.opj"
DEFAULT_PSPICE_DIR = DEFAULT_PROJECT / "ORCadCPMTest-PSpiceFiles" / "SCHEMATIC1"
DEFAULT_NET = DEFAULT_PSPICE_DIR / "SCHEMATIC1.net"

LIB_LINES = [
    '.lib "nom.lib"',
    '.lib "tex_inst.lib"',
    r'.lib "C:\Cadence\OrCADX_25.1\tools\capture\library\pspice\1N6263.lib"',
    r'.lib "C:\Cadence\OrCADX_25.1\tools\capture\library\pspice\2n7000.lib"',
]


@dataclass
class TranSettings:
    tstop: str = "50ms"
    tstep: str = "1u"
    tstart: str = "0"


@dataclass
class AcSettings:
    points_per_decade: int = 10
    fstart: str = "1"
    fstop: str = "100Meg"


@dataclass
class ParametricSettings:
    """Capture .sim @Analysis: 5 block (Parametric Sweep).

    Learned from Lab5_TRAN (user UI):
      @Analysis: 5 1
      +0 0                 # sweep kind 0 (global parameter style, same as sample Vin sweeps)
      +0 "RS"              # Global Parameter name (must match schematic VALUE/{param})
      +4 "100"  +5 "1"  +6 "10"
         # Lab 6.1 RS sweep encoding that yields 100 / 1k / 10k decade steps
         # For RL sweep (§6.2): name=\"RL\", keep RS=100 on schematic

    Enable with enabled=True. Disable leaves @Analysis: 5 0.
    """

    enabled: bool = False
    param: str = "RS"
    # Captured field order from working Lab5_TRAN.sim
    start: str = "100"
    mid: str = "1"
    end: str = "10"


def _parametric_block(p: ParametricSettings | None) -> str:
    if p is None or not p.enabled:
        return """@Analysis: 5 0
+0 0
+0 "" 
+1 "" 
+2 "" 
+3 "" 
+4 "" 
+5 "" 
+6 "" 
+7 "" 
@End Analysis"""
    return f"""@Analysis: 5 1
+0 0
+0 "{p.param}" 
+1 "" 
+2 "" 
+3 "" 
+4 "{p.start}" 
+5 "{p.mid}" 
+6 "{p.end}" 
+7 "" 
@End Analysis"""


def write_tran_sim(
    name: str,
    out_dir: Path = DEFAULT_PSPICE_DIR,
    settings: TranSettings | None = None,
    parametric: ParametricSettings | None = None,
    notes: str = "",
) -> Path:
    """Write a Capture-compatible .sim file for transient analysis."""
    s = settings or TranSettings()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.sim"
    notes = notes or f"Transient to {s.tstop}, max step {s.tstep}"
    param_block = _parametric_block(parametric)
    text = f"""@OrCAD Simulation Server Version: 1.0

@Settings: 2 1
@General:
ProfileName= "{name}" 
ProfileFile= "{name}.sim" 
Connectivity= "SCHEMATIC1.net" 
NetlistFile= "{name}.cir" 
DataFile= "{name}.dat" 
OutFile= "{name}.out" 
Notes=
@#$BEGINNOTES
{notes}
@#$ENDNOTES
@End General
@Analysis: 0 1
+0 0 0 0 
+0 "{s.tstop}" 
+1 "" 
+2 "{s.tstart}" 
+3 "{s.tstep}" 
+4 "" 
+5 "" 
+6 "" 
@End Analysis
@Analysis: 1 0
+2 0 0
+0 "10" 
+1 "1" 
+2 "100Meg" 
+3 "" 
+4 "" 
+5 "" 
@End Analysis
@Analysis: 2 0
+0 0
+0 "" 
+1 "" 
+2 "" 
+3 "" 
+4 "" 
+5 "" 
+6 "" 
+7 "" 
@End Analysis
@Analysis: 3 0
+0 0 0
+0 "" 
+1 "" 
+2 "" 
@End Analysis
@Analysis: 4 0
+0 0 1 0 0 0 2 0 0 0 1
+0 "" 
+1 "" 
+2 "" 
+3 "" 
+4 "" 
+5 "" 
+6 "" 
+7 "" 
LoadFile 0 "" 
SaveFile 0 "" 
@End Analysis
{param_block}
@Analysis: 6 0
+1 
+0 "" 
@End Analysis
@Analysis: 7 0
+0 0
+0 "" 
+1 "" 
+2 "" 
+3 "" 
+4 "" 
+5 "" 
@End Analysis
@Analysis: 8 0
+0 
+0 "" 
+1 "" 
+2 "" 
+3 "" 
+4 "" 
+5 "" 
@End Analysis
@Analysis: 9 0
+0 "" 
@End Analysis
@Analysis: 10 0
+0 0
+0 "" 
+1 "" 
+2 "" 
+3 "" 
+4 "" 
+5 "" 
+6 "" 
+7 "" 
@End Analysis
@Analysis: 11 1
+ 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 
+ 0 0 0 0 0 0 0 0 0
@End Analysis
@Analysis: 12 0
+2236960 0 1
@End Analysis
@Analysis: 13 1
+0 1 1 0
@End Analysis
@Analysis: 14 1
+1 1 1 "*" 
@End Analysis
@Analysis: 15 0
@End Analysis
@Analysis: 16 0
+0 "0" 
+1 "0" 
@End Analysis
@Analysis: 17 0
+0 "-1" 
+1 "-1" 
+2 "0" 
+3 "-1" 
+4 "1" 
@End Analysis
@Analysis: 18 0
+0 "" 
+1 "0.1" 
+2 "0.1" 
+3 "1" 
+4 "2" 
+5 "" 
+6 "false" 
+7 "5" 
@End Analysis
@Analysis: 19 0
+0 "2" 
+1 "21" 
+2 "5" 
+3 "50K" 
+4 "1" 
@End Analysis
"""
    path.write_text(text, encoding="utf-8")
    return path


def write_ac_sim(
    name: str,
    out_dir: Path = DEFAULT_PSPICE_DIR,
    settings: AcSettings | None = None,
    notes: str = "",
) -> Path:
    s = settings or AcSettings()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.sim"
    notes = notes or f"AC DEC {s.points_per_decade} {s.fstart} {s.fstop}"
    # Reuse Lab2_AC structure: Analysis 0 off, Analysis 1 on
    base = write_tran_sim(name, out_dir, TranSettings(), notes)
    text = base.read_text(encoding="utf-8")
    text = text.replace("@Analysis: 0 1", "@Analysis: 0 0", 1)
    text = text.replace("@Analysis: 1 0", "@Analysis: 1 1", 1)
    text = re.sub(
        r'@Analysis: 1 1\n\+2 0 0\n\+0 "10" \n\+1 "1" \n\+2 "100Meg" ',
        f'@Analysis: 1 1\n+2 0 0\n+0 "{s.points_per_decade}" \n+1 "{s.fstart}" \n+2 "{s.fstop}" ',
        text,
        count=1,
    )
    path.write_text(text, encoding="utf-8")
    return path


def register_profile_in_opj(
    profile_name: str,
    sim_path: Path,
    opj_path: Path = DEFAULT_OPJ,
    set_active: bool = True,
) -> str:
    """Insert/update a PSpice profile entry with a unique GUID and full path."""
    opj = opj_path.read_text(encoding="utf-8", errors="replace")
    sim_posix = sim_path.resolve().as_posix()
    display = f"SCHEMATIC1-{profile_name}"
    guid = "{" + str(uuid.uuid4()) + "}"

    # Remove prior entries for this profile name / path
    opj = re.sub(
        rf'\s*\(File\.PSpice\.\{{[^}}]+\}}\s*"[^"]*{re.escape(profile_name)}\.sim"[^\)]*\(DisplayName "[^"]*"\)\s*\(Type "PSpice Profile"\)\)',
        "",
        opj,
        flags=re.DOTALL,
    )
    # Also strip mangled relative ActiveProfile / duplicate stubs from orWriteSimProfileIntoPrjFiles
    opj = re.sub(r'\s*\(ActiveProfile "[^"]*"\)', "", opj)
    opj = re.sub(
        rf'\s*\(File\.PSpice\.\{{[^}}]+\}} "{re.escape(profile_name)}\.sim"[^\)]*\(DisplayName "[^"]*"\)\s*\(Type "PSpice Profile"\)\)',
        "",
        opj,
        flags=re.DOTALL,
    )

    entry = (
        f'      (File.PSpice.{guid}\n'
        f'         "{sim_posix}"\n'
        f'        (DisplayName "{display}")\n'
        f'        (Type "PSpice Profile"))'
    )
    active = f'      (ActiveProfile\n         "{sim_posix}")\n' if set_active else ""

    marker = '(Folder "Simulation Profiles"'
    idx = opj.find(marker)
    if idx < 0:
        return "ERROR: Simulation Profiles folder not found in .opj"

    # Insert after the folder line
    insert_at = opj.find("\n", idx) + 1
    block = active + entry + "\n"
    # Keep existing Lab2 etc. — just prepend our entry
    opj = opj[:insert_at] + block + opj[insert_at:]
    opj_path.write_text(opj, encoding="utf-8")
    return f"OK registered {display} -> {sim_posix}"


def _fix_netlist_body(net_text: str) -> str:
    """Fix known Capture netlist glitches (e.g. C_CL missing positive node)."""
    lines = []
    for line in net_text.splitlines():
        # C_CL         0  47u  -> C_CL VOUT 0 47u
        m = re.match(r"^(C_CL)\s+0\s+(47u)\s*$", line.strip(), re.I)
        if m:
            lines.append(f"C_CL         VOUT 0  {m.group(2)}")
            continue
        lines.append(line)
    return "\n".join(lines)


def _print_expr(node: str) -> str:
    """PSpice node voltage expression.

    Bare V(NAME) is treated as a *device* voltage. Net aliases need V([NAME]).
    Numeric nodes use V(3). Already-wrapped expressions are left alone.
    """
    n = node.strip()
    if n.upper().startswith("V("):
        return n
    if re.fullmatch(r"\d+", n):
        return f"V({n})"
    return f"V([{n}])"


def build_cir(
    profile_name: str,
    analysis_lines: Iterable[str],
    net_path: Path = DEFAULT_NET,
    out_dir: Path | None = None,
    print_nodes: list[str] | None = None,
    use_csdf: bool = True,
    analysis_kind: str = "TRAN",
) -> Path:
    """Build a runnable .cir from schematic net + analysis directives."""
    out_dir = out_dir or (DEFAULT_PSPICE_DIR / profile_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    cir_path = out_dir / f"{profile_name}.cir"

    net_body = _fix_netlist_body(net_path.read_text(encoding="utf-8", errors="replace"))
    raw_nodes = print_nodes or ["VOUT", "VIN"]
    exprs = [_print_expr(n) for n in raw_nodes]
    kind = analysis_kind.upper()
    print_line = f".PRINT {kind} " + " ".join(exprs)
    probe = ".PROBE/CSDF " + " ".join(exprs) if use_csdf else ".PROBE " + " ".join(exprs)

    # Prefer absolute library paths so psp_cmd works without Capture's LIBPATH.
    libs = "\n".join(
        [
            r'.lib "C:\Cadence\OrCADX_25.1\tools\pspice\library\nom.lib"',
            r'.lib "C:\Cadence\OrCADX_25.1\tools\pspice\library\tex_inst.lib"',
            r'.lib "C:\Cadence\OrCADX_25.1\tools\capture\library\pspice\1N6263.lib"',
            r'.lib "C:\Cadence\OrCADX_25.1\tools\capture\library\pspice\2n7000.lib"',
        ]
    )
    analysis = "\n".join(analysis_lines)
    cir = f"""* {profile_name} — generated by tcl-mcp-server sim_lib
{libs}

{net_body}

{analysis}
{print_line}
{probe}
.OPTIONS RELTOL=0.001
.END
"""
    cir_path.write_text(cir, encoding="utf-8")
    return cir_path


def run_psp_cmd(cir_path: Path, timeout_s: float = 120.0) -> dict:
    """Run headless PSpice; poll .out for completion (psp_cmd may hang after JOB CONCLUDED)."""
    if not PSP_CMD.is_file():
        return {"ok": False, "error": f"psp_cmd not found: {PSP_CMD}"}
    cir_path = cir_path.resolve()
    cwd = cir_path.parent
    stem = cir_path.stem
    out_file = cwd / f"{stem}.out"
    # Remove stale out so we detect fresh completion
    if out_file.is_file():
        try:
            out_file.unlink()
        except OSError:
            pass

    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["CDSROOT"] = r"C:\Cadence\OrCADX_25.1"

    proc = subprocess.Popen(
        [str(PSP_CMD), str(cir_path.name)],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.time() + timeout_s
    concluded = False
    while time.time() < deadline:
        if out_file.is_file():
            try:
                txt = out_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                txt = ""
            if "JOB CONCLUDED" in txt or "Job concluded" in txt:
                concluded = True
                break
            if "ERROR(" in txt and "CIRCUIT DESCRIPTION" in txt:
                # Hard error before/during run
                if "JOB STATISTICS" in txt or txt.count("ERROR(") > 0 and "INITIAL" not in txt:
                    # Keep waiting briefly for file flush unless only early errors
                    if "JOB CONCLUDED" in txt:
                        concluded = True
                        break
        if proc.poll() is not None:
            break
        time.sleep(0.4)

    if proc.poll() is None:
        # Simulation finished writing but process hung (often Probe spawn) — kill it.
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    stdout, stderr = "", ""
    try:
        stdout, stderr = proc.communicate(timeout=2)
    except Exception:
        pass

    dat_file = cwd / f"{stem}.dat"
    csdf_file = cwd / f"{stem}.csd"
    if not csdf_file.is_file():
        csdf_file = cwd / f"{stem}.csdf"
    candidates = list(cwd.glob(f"{stem}.*"))
    ok = concluded or (out_file.is_file() and "JOB CONCLUDED" in out_file.read_text(encoding="utf-8", errors="replace"))
    return {
        "ok": ok,
        "returncode": proc.returncode,
        "concluded": concluded,
        "stdout": (stdout or "")[-2000:],
        "stderr": (stderr or "")[-2000:],
        "out": str(out_file) if out_file.is_file() else "",
        "dat": str(dat_file) if dat_file.is_file() else "",
        "csdf": str(csdf_file) if csdf_file.is_file() else "",
        "files": [str(p.name) for p in candidates],
    }


def parse_print_tran(out_path: Path) -> dict[str, list[float]]:
    """Parse .PRINT TRAN table from a PSpice .out file."""
    text = out_path.read_text(encoding="utf-8", errors="replace")
    # Find a block that looks like: TIME V(VOUT) V(VIN) ... then numeric rows
    lines = text.splitlines()
    header_idx = None
    headers: list[str] = []
    for i, line in enumerate(lines):
        if re.search(r"\bTIME\b", line, re.I) and re.search(r"\bV\(", line, re.I):
            headers = re.findall(r"[A-Za-z0-9_().*/+-]+", line)
            # Keep TIME and V(...) columns
            headers = [h for h in headers if h.upper() == "TIME" or h.upper().startswith("V(")]
            if len(headers) >= 2:
                header_idx = i
                break
    if header_idx is None:
        return {}

    cols: dict[str, list[float]] = {h: [] for h in headers}
    for line in lines[header_idx + 1 :]:
        if not line.strip():
            if cols[headers[0]]:
                break
            continue
        if re.match(r"^\s*\*", line) or "ERROR" in line.upper():
            if cols[headers[0]]:
                break
            continue
        nums = re.findall(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?", line)
        if len(nums) < len(headers):
            continue
        try:
            for h, n in zip(headers, nums[: len(headers)]):
                cols[h].append(float(n))
        except ValueError:
            continue
    return cols


def parse_csdf(csdf_path: Path) -> dict[str, list[float]]:
    """Minimal CSDF parser for #N / #C style PSpice CSDF files."""
    text = csdf_path.read_text(encoding="utf-8", errors="replace")
    names: list[str] = []
    series: dict[str, list[float]] = {}
    # Names often appear as: #N name1 name2 ...
    for m in re.finditer(r"^#N\s+(.+)$", text, re.M):
        names = m.group(1).split()
        for n in names:
            series.setdefault(n, [])
    # Data rows: #C t; v1 v2 ...   or plain numbers after #C
    for m in re.finditer(r"^#C\s+([^;]+);\s*(.+)$", text, re.M):
        try:
            t = float(m.group(1).strip())
            vals = [float(x) for x in m.group(2).split()]
        except ValueError:
            continue
        if not names:
            continue
        # First name is often Time
        if names[0].upper() in ("TIME", "FREQ", "FREQUENCY"):
            series[names[0]].append(t)
            for n, v in zip(names[1:], vals):
                series[n].append(v)
        else:
            # time then values matching names
            if "TIME" not in series:
                series["TIME"] = []
            series["TIME"].append(t)
            for n, v in zip(names, vals):
                series[n].append(v)
    return series


def plot_traces(
    data: dict[str, list[float]],
    x_key: str,
    y_keys: list[str],
    out_png: Path,
    title: str = "",
    xlabel: str = "",
) -> str:
    """Plot selected traces to PNG using matplotlib."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "ERROR: matplotlib not installed"

    if x_key not in data or not data[x_key]:
        # fuzzy match
        for k in data:
            if k.upper() == x_key.upper():
                x_key = k
                break
    if x_key not in data:
        return f"ERROR: x-axis '{x_key}' not in data keys {list(data)}"

    x = data[x_key]
    fig, ax = plt.subplots(figsize=(10, 5))
    for yk in y_keys:
        key = yk
        if key not in data:
            for k in data:
                if k.upper() == yk.upper() or k.upper().replace(" ", "") == yk.upper():
                    key = k
                    break
        if key not in data:
            continue
        ax.plot(x, data[key], label=key)
    ax.set_title(title or "PSpice results")
    ax.set_xlabel(xlabel or x_key)
    ax.set_ylabel("Value")
    ax.grid(True, alpha=0.3)
    ax.legend()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)
    return str(out_png.resolve())


def summarize_last(data: dict[str, list[float]], node: str, last_n: int = 200) -> dict:
    """Simple steady-state stats on the last window of a trace."""
    key = node
    if key not in data:
        for k in data:
            if node.upper() in k.upper():
                key = k
                break
    if key not in data or not data[key]:
        return {"error": f"node {node} not found"}
    ys = data[key][-last_n:]
    return {
        "node": key,
        "n": len(ys),
        "mean": sum(ys) / len(ys),
        "min": min(ys),
        "max": max(ys),
        "pp": max(ys) - min(ys),
    }
