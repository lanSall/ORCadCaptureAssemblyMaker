"""MCP server: Capture Tcl bridge + PSpice profile/run/extract tools."""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

import sim_lib

HOST = "localhost"
PORT = 9020
RECV_BUFSIZE = 65536
TIMEOUT_SECONDS = 30.0

mcp = FastMCP("tcl-mcp-server")

_lock = threading.Lock()
_sock: socket.socket | None = None


def _ensure_newline(command: str) -> str:
    return command if command.endswith("\n") else command + "\n"


def _close_sock() -> None:
    global _sock
    if _sock is not None:
        try:
            _sock.close()
        except OSError:
            pass
        _sock = None


def _connect() -> socket.socket:
    global _sock
    _close_sock()
    sock = socket.create_connection((HOST, PORT), timeout=TIMEOUT_SECONDS)
    sock.settimeout(TIMEOUT_SECONDS)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    _sock = sock
    return sock


def _recv_all(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    sock.settimeout(TIMEOUT_SECONDS)
    try:
        first = sock.recv(RECV_BUFSIZE)
    except socket.timeout:
        sock.settimeout(TIMEOUT_SECONDS)
        return b""
    if not first:
        return b""
    chunks.append(first)
    sock.settimeout(0.15)
    while True:
        try:
            data = sock.recv(RECV_BUFSIZE)
        except socket.timeout:
            break
        if not data:
            break
        chunks.append(data)
    sock.settimeout(TIMEOUT_SECONDS)
    return b"".join(chunks)


def _send_one(command: str) -> str:
    payload = _ensure_newline(command).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            sock = _sock if _sock is not None else _connect()
            sock.sendall(payload)
            response = _recv_all(sock)
            return response.decode("utf-8", errors="replace")
        except OSError as exc:
            last_err = exc
            _close_sock()
            if attempt == 0:
                continue
    return f"ERROR: Capture socket failed: {last_err}"


# --- Capture Tcl tools -------------------------------------------------


@mcp.tool()
def execute_tcl(command: str) -> str:
    """Send a single TCL command to localhost:9020 and return the response."""
    with _lock:
        return _send_one(command)


@mcp.tool()
def execute_tcl_batch(commands: list[str], delay_ms: float = 50.0) -> str:
    """Run several small TCL commands in order on one persistent connection."""
    if not commands:
        return "ERROR: empty command list"
    delay_s = max(0.0, float(delay_ms) / 1000.0)
    results: list[str] = []
    with _lock:
        for i, cmd in enumerate(commands):
            text = cmd.strip()
            if not text:
                continue
            out = _send_one(text)
            results.append(f"[{i}] {out.rstrip()}")
            if delay_s and i < len(commands) - 1:
                time.sleep(delay_s)
    return "\n".join(results)


@mcp.tool()
def capture_ping() -> str:
    """Health-check Capture on port 9020."""
    with _lock:
        return _send_one("expr 1")


# --- PSpice profile / run / extract ------------------------------------


@mcp.tool()
def create_sim_profile(
    name: str,
    analysis: str = "tran",
    tstop: str = "50ms",
    tstep: str = "1u",
    fstart: str = "1",
    fstop: str = "100Meg",
    points_per_decade: int = 10,
    register: bool = True,
    notes: str = "",
) -> str:
    """Create a Capture .sim profile and optionally register it in the .opj.

    analysis: "tran" or "ac"
    After this, reopen/refresh the project in Capture if the profile list is stale.
    """
    analysis = analysis.lower().strip()
    if analysis == "tran":
        path = sim_lib.write_tran_sim(
            name,
            settings=sim_lib.TranSettings(tstop=tstop, tstep=tstep),
            notes=notes,
        )
    elif analysis == "ac":
        path = sim_lib.write_ac_sim(
            name,
            settings=sim_lib.AcSettings(
                points_per_decade=points_per_decade,
                fstart=fstart,
                fstop=fstop,
            ),
            notes=notes,
        )
    else:
        return f"ERROR: unsupported analysis '{analysis}' (use tran|ac)"

    msg = f"wrote {path}"
    if register:
        msg += "\n" + sim_lib.register_profile_in_opj(name, path, set_active=True)
    return msg


@mcp.tool()
def run_sim(
    name: str,
    analysis: str = "tran",
    tstop: str = "50ms",
    tstep: str = "1u",
    fstart: str = "1",
    fstop: str = "100Meg",
    points_per_decade: int = 10,
    print_nodes: list[str] | None = None,
    timeout_s: float = 300.0,
) -> str:
    """Build .cir from SCHEMATIC1.net, run psp_cmd.exe headless, return result paths.

    Does not require Capture's ASP client. Uses current netlist on disk — save the
    design in Capture first so SCHEMATIC1.net is up to date.
    """
    analysis = analysis.lower().strip()
    print_nodes = print_nodes or ["VOUT", "VIN"]
    if analysis == "tran":
        analysis_lines = [f".TRAN {tstep} {tstop} 0 {tstep}"]
        kind = "TRAN"
    elif analysis == "ac":
        analysis_lines = [f".AC DEC {points_per_decade} {fstart} {fstop}"]
        kind = "AC"
    else:
        return f"ERROR: unsupported analysis '{analysis}'"

    # Ensure .sim exists for Capture UI parity
    if analysis == "tran":
        sim_lib.write_tran_sim(name, settings=sim_lib.TranSettings(tstop=tstop, tstep=tstep))
    else:
        sim_lib.write_ac_sim(
            name,
            settings=sim_lib.AcSettings(
                points_per_decade=points_per_decade, fstart=fstart, fstop=fstop
            ),
        )

    if not sim_lib.DEFAULT_NET.is_file():
        return f"ERROR: netlist missing: {sim_lib.DEFAULT_NET} (PSpice → Create Netlist / save design)"

    cir = sim_lib.build_cir(
        name,
        analysis_lines=analysis_lines,
        print_nodes=print_nodes,
        use_csdf=True,
        analysis_kind=kind,
    )

    result = sim_lib.run_psp_cmd(cir, timeout_s=timeout_s)
    result["cir"] = str(cir)
    result["name"] = name
    return json.dumps(result, indent=2)


@mcp.tool()
def extract_sim_results(
    name: str,
    y_nodes: list[str] | None = None,
    title: str = "",
) -> str:
    """Parse PSpice .out/.csdf for a profile run and write a PNG plot + stats JSON.

    Looks under ORCadCPMTest-PSpiceFiles/SCHEMATIC1/<name>/.
    """
    y_nodes = y_nodes or ["V(VOUT)", "V(VIN)"]
    run_dir = sim_lib.DEFAULT_PSPICE_DIR / name
    out_path = run_dir / f"{name}.out"
    csdf_path = run_dir / f"{name}.csdf"
    # Also accept .csd
    if not csdf_path.is_file():
        alt = run_dir / f"{name}.csd"
        if alt.is_file():
            csdf_path = alt

    data: dict = {}
    source = ""
    if out_path.is_file():
        data = sim_lib.parse_print_tran(out_path)
        source = str(out_path)
    if (not data) and csdf_path.is_file():
        data = sim_lib.parse_csdf(csdf_path)
        source = str(csdf_path)
    if not data:
        # Try any .out in folder
        outs = list(run_dir.glob("*.out"))
        for p in outs:
            data = sim_lib.parse_print_tran(p)
            if data:
                source = str(p)
                break
    if not data:
        files = [str(p.name) for p in run_dir.glob("*")] if run_dir.is_dir() else []
        return json.dumps(
            {"ok": False, "error": "no parseable results", "dir": str(run_dir), "files": files},
            indent=2,
        )

    # Resolve x axis
    x_key = "TIME"
    for k in data:
        if k.upper() in ("TIME", "FREQ", "FREQUENCY"):
            x_key = k
            break

    png = run_dir / f"{name}_plot.png"
    plot_msg = sim_lib.plot_traces(
        data,
        x_key=x_key,
        y_keys=y_nodes,
        out_png=png,
        title=title or f"{name} — {x_key}",
        xlabel=x_key,
    )
    stats = {n: sim_lib.summarize_last(data, n) for n in y_nodes}
    # CSV dump
    csv_path = run_dir / f"{name}_traces.csv"
    keys = [x_key] + [k for k in data if k != x_key]
    n = min(len(data[k]) for k in keys if k in data and data[k])
    with csv_path.open("w", encoding="utf-8") as f:
        f.write(",".join(keys) + "\n")
        for i in range(n):
            f.write(",".join(str(data[k][i]) for k in keys) + "\n")

    return json.dumps(
        {
            "ok": True,
            "source": source,
            "plot": plot_msg,
            "csv": str(csv_path.resolve()),
            "keys": list(data.keys()),
            "points": n,
            "stats": stats,
        },
        indent=2,
    )


if __name__ == "__main__":
    mcp.run()
