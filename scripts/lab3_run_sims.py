"""Run ECEN3314 Lab 3 Section 6 simulations via psp_cmd and export CSVs."""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import sim_lib

ROOT = REPO / "labs" / "lab3_results"
NET = ROOT / "netlists"
DATA = ROOT / "data"
MODELS = ROOT / "models"
PSP = sim_lib.PSP_CMD
LIB4148 = MODELS / "1N4148.lib"
LIB4007 = MODELS / "1N4007.lib"
LIB5231 = MODELS / "1N5231_model.lib"


def run_cir(cir: Path, timeout_s: float = 120.0) -> dict:
    cir = cir.resolve()
    out = cir.with_suffix(".out")
    if out.is_file():
        try:
            out.unlink()
        except OSError:
            pass
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["CDSROOT"] = r"C:\Cadence\OrCADX_25.1"
    proc = subprocess.Popen(
        [str(PSP), cir.name],
        cwd=str(cir.parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.time() + timeout_s
    concluded = False
    while time.time() < deadline:
        if out.is_file():
            txt = out.read_text(encoding="utf-8", errors="replace")
            if "JOB CONCLUDED" in txt or "Job concluded" in txt:
                concluded = True
                break
        if proc.poll() is not None:
            break
        time.sleep(0.3)
    if proc.poll() is None:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    try:
        stdout, stderr = proc.communicate(timeout=2)
    except Exception:
        stdout, stderr = "", ""
    return {
        "ok": concluded,
        "out": str(out),
        "stdout": stdout[-500:] if stdout else "",
        "stderr": stderr[-300:] if stderr else "",
    }


def parse_print_table(out_text: str, xname: str, ynames: list[str]) -> dict[str, list[float]]:
    """Parse a .PRINT DC/TRAN numeric table after a header containing xname/ynames."""
    lines = out_text.splitlines()
    header_idx = None
    headers: list[str] = []
    want = {xname.upper(), *[y.upper() for y in ynames]}
    for i, line in enumerate(lines):
        toks = re.findall(r"[A-Za-z0-9_().*/+-]+", line)
        up = [t.upper() for t in toks]
        if xname.upper() in up and any(y.upper() in up for y in ynames):
            # keep only matching columns in order of appearance
            headers = []
            for t in toks:
                tu = t.upper()
                if tu == xname.upper() or tu in {y.upper() for y in ynames} or tu.startswith("V(") or tu.startswith("I("):
                    headers.append(t)
            if len(headers) >= 2:
                header_idx = i
                break
    if header_idx is None:
        return {}
    cols: dict[str, list[float]] = {h: [] for h in headers}
    for line in lines[header_idx + 1 :]:
        if not line.strip():
            if cols[headers[0]]:
                # allow blank mid-page; stop after sustained blank with data
                continue
            continue
        if re.match(r"^\s*\*", line) or "ERROR" in line.upper() or "JOB" in line.upper():
            if cols[headers[0]]:
                break
            continue
        if re.match(r"^\s*[A-Za-z]", line) and not re.match(r"^\s*[-+]?\d", line):
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


def write_csv(path: Path, data: dict[str, list[float]], keys: list[str]) -> None:
    n = min(len(data[k]) for k in keys)
    with path.open("w", encoding="utf-8") as f:
        f.write(",".join(keys) + "\n")
        for i in range(n):
            f.write(",".join(str(data[k][i]) for k in keys) + "\n")


def write_and_run(name: str, body: str) -> Path:
    NET.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    cir = NET / f"{name}.cir"
    cir.write_text(body, encoding="ascii", errors="replace")
    print(f"== {name} ==")
    res = run_cir(cir)
    print(res)
    return cir.with_suffix(".out")


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    NET.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)

    # --- 6.1 Diode I-V (Fig 9) DC sweep ---
    out = write_and_run(
        "Lab3_S2_diode_IV",
        f"""* Lab3 6.1 Fig9 diode I-V 1N4148 + 1k
.lib "{LIB4148.as_posix()}"
VIN VIN 0 DC 0
D1 VIN NVO 1N4148
R1 NVO 0 1k
.DC VIN 0 5 0.01
.PRINT DC V(VIN) V(NVO) I(D1)
.PROBE/CSDF V(VIN) V(NVO) I(D1)
.END
""",
    )
    text = out.read_text(encoding="utf-8", errors="replace")
    data = parse_print_table(text, "V(VIN)", ["V(NVO)", "I(D1)"])
    if data:
        # derive VD, ID (ID already I(D1))
        vin = data[[k for k in data if "VIN" in k.upper()][0]]
        vo = data[[k for k in data if "NVO" in k.upper() or k.upper() == "V(NVO)"][0]]
        idiode = data[[k for k in data if "I(D1)" in k.upper()][0]]
        vd = [a - b for a, b in zip(vin, vo)]
        export = {"VIN": vin, "VO": vo, "VD": vd, "ID": idiode}
        write_csv(DATA / "Lab3_S2_diode_IV.csv", export, ["VIN", "VO", "VD", "ID"])
        print("CSV diode IV", len(vin), "pts")
    else:
        print("WARN: failed to parse diode IV; out head:\n", text[:1500])

    # --- 6.2 Zener I-V (Fig 10) DC sweep ---
    out = write_and_run(
        "Lab3_S4_zener_IV",
        f"""* Lab3 6.2 Fig10 Zener 1N5231 reverse + 2k
.lib "{LIB5231.as_posix()}"
VIN VIN 0 DC 0
R1 VIN NCATH 2k
DZ 0 NCATH D1N5231
.DC VIN 0 15 0.05
.PRINT DC V(VIN) V(NCATH) I(R1)
.PROBE/CSDF V(VIN) V(NCATH) I(R1)
.END
""",
    )
    text = out.read_text(encoding="utf-8", errors="replace")
    data = parse_print_table(text, "V(VIN)", ["V(NCATH)", "I(R1)"])
    if data:
        vin = data[[k for k in data if "VIN" in k.upper()][0]]
        vc = data[[k for k in data if "NCATH" in k.upper()][0]]
        ir = data[[k for k in data if "I(R1)" in k.upper()][0]]
        # Fig10: cathode at NCATH, anode at 0 => reverse voltage magnitude ~= V(NCATH)
        # VD with diode polarity (anode-cathode) is -V(NCATH); lab wants reverse curve
        vr = [a - b for a, b in zip(vin, vc)]
        vd_rev = vc[:]  # cathode-to-anode magnitude when reverse
        export = {"VIN": vin, "VR": vr, "VD": vd_rev, "ID": ir}
        write_csv(DATA / "Lab3_S4_zener_IV.csv", export, ["VIN", "VR", "VD", "ID"])
        print("CSV zener IV", len(vin), "pts")
    else:
        print("WARN: failed to parse zener; out head:\n", text[:1500])

    # --- 6.3 Peak rectifier (Fig 11) at 50/150/500 Hz ---
    for freq in (50, 150, 500):
        tstop = 2.0 / freq  # two full waves
        tstep = min(1e-5, tstop / 2000)
        name = f"Lab3_S6_peak_{freq}Hz"
        out = write_and_run(
            name,
            f"""* Lab3 6.3 Fig11 peak rectifier 1N4007 150ohm 47uF @ {freq}Hz
.lib "{LIB4007.as_posix()}"
VIN VIN 0 SIN(0 3 {freq} 0 0 0)
D1 VIN VO 1N4007
C1 VO 0 47u IC=0
R1 VO 0 150
.TRAN {tstep} {tstop} 0 {tstep} UIC
.PRINT TRAN V(VIN) V(VO)
.PROBE/CSDF V(VIN) V(VO)
.END
""",
        )
        text = out.read_text(encoding="utf-8", errors="replace")
        data = parse_print_table(text, "TIME", ["V(VIN)", "V(VO)"])
        if not data:
            # try CSDF
            csd = out.with_suffix(".csd")
            if csd.is_file():
                data = sim_lib.parse_csdf(csd)
        if data:
            # normalize keys
            keys = list(data.keys())
            xk = next(k for k in keys if k.upper() in ("TIME", "FREQ"))
            yvin = next(k for k in keys if "VIN" in k.upper())
            yvout = next(k for k in keys if re.search(r"\bVO\b", k, re.I) or "V(VO)" in k.upper())
            export = {"TIME": data[xk], "VIN": data[yvin], "VOUT": data[yvout]}
            write_csv(DATA / f"{name}.csv", export, ["TIME", "VIN", "VOUT"])
            print(f"CSV peak {freq}Hz", len(export["TIME"]), "pts")
        else:
            print(f"WARN: parse fail {name}\n", text[:1200])

    # --- 6.4 Full-wave bridge (Fig 8) 50 Hz ---
    out = write_and_run(
        "Lab3_S8_fullwave_50Hz",
        f"""* Lab3 6.4 Fig8 full-wave bridge 1N4007 RL=10k 3V 50Hz
.lib "{LIB4007.as_posix()}"
VIN N1 N2 SIN(0 3 50 0 0 0)
D1 N1 A 1N4007
D2 B N1 1N4007
D3 N2 A 1N4007
D4 B N2 1N4007
RL A B 10k
RB B 0 1m
.TRAN 20u 40m 0 20u
.PRINT TRAN V(N1) V(N2) V(A) V(B)
.PROBE/CSDF V(N1) V(N2) V(A) V(B)
.END
""",
    )
    text = out.read_text(encoding="utf-8", errors="replace")
    data = parse_print_table(text, "TIME", ["V(A)"])
    if not data:
        csd = out.with_suffix(".csd")
        if csd.is_file():
            data = sim_lib.parse_csdf(csd)
    if data:
        keys = list(data.keys())
        xk = next(k for k in keys if k.upper() == "TIME")
        va = next(k for k in keys if re.search(r"V\(A\)", k, re.I) or k.upper() == "V(A)")
        vb = next((k for k in keys if re.search(r"V\(B\)", k, re.I)), None)
        n1 = next((k for k in keys if "N1" in k.upper()), None)
        n2 = next((k for k in keys if "N2" in k.upper()), None)
        vout = data[va]
        if vb:
            vout = [a - b for a, b in zip(data[va], data[vb])]
        export: dict[str, list[float]] = {"TIME": data[xk], "VOUT": vout}
        cols = ["TIME", "VOUT"]
        if n1 and n2:
            export["VIN"] = [a - b for a, b in zip(data[n1], data[n2])]
            cols = ["TIME", "VIN", "VOUT"]
        write_csv(DATA / "Lab3_S8_fullwave_50Hz.csv", export, cols)
        print("CSV fullwave", len(export["TIME"]), "pts")
    else:
        print("WARN: fullwave parse fail\n", text[:1500])

    print("DONE ->", ROOT)


if __name__ == "__main__":
    main()
