"""Place Lab 2 §6 non-inverting + inverting TL074 circuits on Capture PAGE1.

Requires Capture with CaptureMCPPortConnection listening on :9020.

Usage:
  python scripts/lab2_place.py            # place both amps
  python scripts/lab2_place.py --dry-run  # print Tcl only
"""
from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from placement_lib import (  # noqa: E402
    ground_at_hotspot,
    lib_path,
    mcp_delay_ms,
    orthowire,
    pin_tip,
    place_alias,
    place_part,
    place_wire,
    save_cmd,
    set_props_at_xy,
    split_place_wire_prop,
)

HOST, PORT = "127.0.0.1", 9020
TEX = lib_path("pspice/tex_inst.olb")
ANALOG = lib_path("pspice/analog.olb")
SOURCE = lib_path("pspice/source.olb")
TL074_NAME = "TL074/301/TI"
TL074_DEV = "A"


def tcl(cmd: str, timeout: float = 30.0) -> str:
    if not cmd.endswith("\n"):
        cmd += "\n"
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sock.settimeout(timeout)
        sock.sendall(cmd.encode("utf-8"))
        chunks: list[bytes] = []
        while True:
            try:
                data = sock.recv(65536)
            except socket.timeout:
                break
            if not data:
                break
            chunks.append(data)
            if b"\n" in data:
                break
        return b"".join(chunks).decode("utf-8", errors="replace").strip()


def count_parts() -> str:
    return tcl(
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set n 0; set lIter [$lPage NewPartInstsIter $lStatus]; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { incr n; set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; return $n"
    )


def send_all(cmds: list[str]) -> None:
    """Crash-safe sender: place one at a time, save after each, verify counts.

    2026-07-20 session: 4 rapid PlaceParts (150 ms apart, no save) crashed
    Capture and rolled back everything since last save.
    """
    buckets = split_place_wire_prop(cmds)
    for c in buckets["place"]:
        before = count_parts()
        print("PLACE", c[:80])
        print(" ", tcl(c, timeout=15))
        time.sleep(0.6)
        after = count_parts()
        print(f"  parts {before} -> {after}")
        tcl(save_cmd(), timeout=20)
        time.sleep(0.4)
    for c in buckets["ground"]:
        print("GND", c[:80])
        print(" ", tcl(c, timeout=15))
        time.sleep(0.5)
    tcl(save_cmd(), timeout=20)
    for i, c in enumerate(buckets["wire"]):
        print("WIRE", c)
        print(" ", tcl(c, timeout=15))
        time.sleep(0.25)
        if i % 6 == 5:
            tcl(save_cmd(), timeout=20)
    tcl(save_cmd(), timeout=20)
    for c in buckets["other"]:
        print("OTHER", c[:90])
        print(" ", tcl(c, timeout=15))
        time.sleep(0.25)
    tcl(save_cmd(), timeout=20)


def place_tl074(x: float, y: float) -> str:
    return place_part(x, y, TEX, TL074_NAME, TL074_DEV)


def tip_u(u: tuple[float, float], pin: str) -> tuple[float, float]:
    return pin_tip(u, "pspice/tex_inst.olb", "TL074", pin)


def tip_r(r: tuple[float, float], pin: str) -> tuple[float, float]:
    return pin_tip(r, "pspice/analog.olb", "R", pin)


def tip_vdc(v: tuple[float, float], pin: str) -> tuple[float, float]:
    return pin_tip(v, "pspice/source.olb", "VDC", pin)


def tip_vac(v: tuple[float, float], pin: str) -> tuple[float, float]:
    return pin_tip(v, "pspice/source.olb", "VAC", pin)


def delete_at(x: float, y: float, tol: float = 0.08) -> str:
    return (
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set lIter [$lPage NewPartInstsIter $lStatus]; set victim NULL; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { "
        "set loc [$lInst GetLocation $lStatus]; "
        "set ox [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
        "set oy [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
        f"if {{abs($ox-{x})<{tol} && abs($oy-{y})<{tol}}} {{ set victim $lInst }}; "
        "set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; "
        "if {$victim != $lNullObj} { $lPage DeletePartInst $victim; return deleted } "
        "else { return none }"
    )


def build_noninv(origin: tuple[float, float] = (1.0, 1.2)) -> list[str]:
    """Fig 6 / Fig 8a: non-inverting, Av=10, RL=1Meg, ±15V."""
    ox, oy = origin
    u = (ox + 1.6, oy + 0.4)       # TL074
    vac = (ox + 0.0, oy + 0.5)     # VIN AC
    r1 = (ox + 0.7, oy + 1.5)      # 1k to ground from -
    r2 = (ox + 1.7, oy - 0.2)      # 9k feedback (above)
    rl = (ox + 2.9, oy + 0.5)      # 1Meg load
    vdd = (ox + 2.0, oy - 0.5)     # +15V
    vss = (ox + 2.0, oy + 1.6)     # -15V (polarity flipped via wiring)

    cmds: list[str] = [
        place_tl074(*u),
        place_part(*vac, SOURCE, "VAC"),
        place_part(*r1, ANALOG, "R"),
        place_part(*r2, ANALOG, "R"),
        place_part(*rl, ANALOG, "R"),
        place_part(*vdd, SOURCE, "VDC"),
        place_part(*vss, SOURCE, "VDC"),
    ]

    up, um = tip_u(u, "+"), tip_u(u, "-")
    uvp, uvm, uout = tip_u(u, "V+"), tip_u(u, "V-"), tip_u(u, "OUT")
    vac_p, vac_m = tip_vac(vac, "+"), tip_vac(vac, "-")
    r1_1, r1_2 = tip_r(r1, "1"), tip_r(r1, "2")
    r2_1, r2_2 = tip_r(r2, "1"), tip_r(r2, "2")
    rl_1, rl_2 = tip_r(rl, "1"), tip_r(rl, "2")
    vdd_p, vdd_m = tip_vdc(vdd, "+"), tip_vdc(vdd, "-")
    vss_p, vss_m = tip_vdc(vss, "+"), tip_vdc(vss, "-")

    # VIN → +
    cmds += orthowire(vac_p, up)
    # Feedback R2 between OUT and -
    cmds += orthowire(uout, r2_2)
    cmds += orthowire(r2_1, um)
    # R1 from - side toward ground (use r1_1 near -, r1_2 to gnd)
    cmds += orthowire(um, r1_1)
    # RL from OUT
    cmds += orthowire(uout, rl_1)
    # Supplies
    cmds += orthowire(vdd_p, uvp)
    cmds += orthowire(vss_m, uvm)  # VSS - terminal → opamp V-

    # Grounds: VAC-, R1 free end, RL free end, VDD-, VSS+
    for pin in (vac_m, r1_2, rl_2, vdd_m, vss_p):
        hy = pin[1] + 0.6
        cmds.append(ground_at_hotspot(pin[0], hy))
        cmds.append(place_wire(pin[0], pin[1], pin[0], hy))

    cmds += [
        place_alias(vac_p[0] - 0.15, vac_p[1] - 0.15, "VIN"),
        place_alias(uout[0] + 0.15, uout[1] - 0.15, "VOUT"),
        set_props_at_xy(*r1, {"VALUE": "1k", "Reference": "R1"}),
        set_props_at_xy(*r2, {"VALUE": "9k", "Reference": "R2"}),
        set_props_at_xy(*rl, {"VALUE": "1Meg", "Reference": "RL"}),
        set_props_at_xy(*vac, {"ACMAG": "1", "DC": "0", "Reference": "VIN"}),
        set_props_at_xy(*vdd, {"VALUE": "15V", "Reference": "VDD"}),
        set_props_at_xy(*vss, {"VALUE": "15V", "Reference": "VSS"}),
        set_props_at_xy(*u, {"Reference": "U1"}),
        f'PlaceText {ox:.2f} {oy - 0.9:.2f} {ox + 3.5:.2f} {oy - 0.6:.2f} "Lab2 Non-Inv Av=10"',
    ]
    return cmds


def build_inv(origin: tuple[float, float] = (5.5, 1.2)) -> list[str]:
    """Fig 8b: inverting, Av=-20, RL=1Meg, ±15V, + grounded."""
    ox, oy = origin
    u = (ox + 1.8, oy + 0.4)
    vac = (ox + 0.0, oy + 0.9)
    r3 = (ox + 0.7, oy + 0.9)      # 1k input series to -
    r4 = (ox + 1.9, oy - 0.2)      # 20k feedback
    rl = (ox + 3.1, oy + 0.5)
    vdd = (ox + 2.2, oy - 0.5)
    vss = (ox + 2.2, oy + 1.6)

    cmds: list[str] = [
        place_tl074(*u),
        place_part(*vac, SOURCE, "VAC"),
        place_part(*r3, ANALOG, "R"),
        place_part(*r4, ANALOG, "R"),
        place_part(*rl, ANALOG, "R"),
        place_part(*vdd, SOURCE, "VDC"),
        place_part(*vss, SOURCE, "VDC"),
    ]

    up, um = tip_u(u, "+"), tip_u(u, "-")
    uvp, uvm, uout = tip_u(u, "V+"), tip_u(u, "V-"), tip_u(u, "OUT")
    vac_p, vac_m = tip_vac(vac, "+"), tip_vac(vac, "-")
    r3_1, r3_2 = tip_r(r3, "1"), tip_r(r3, "2")
    r4_1, r4_2 = tip_r(r4, "1"), tip_r(r4, "2")
    rl_1, rl_2 = tip_r(rl, "1"), tip_r(rl, "2")
    vdd_p, vdd_m = tip_vdc(vdd, "+"), tip_vdc(vdd, "-")
    vss_p, vss_m = tip_vdc(vss, "+"), tip_vdc(vss, "-")

    # VIN → R3 → -
    cmds += orthowire(vac_p, r3_1)
    cmds += orthowire(r3_2, um)
    # Feedback R4 OUT ↔ -
    cmds += orthowire(uout, r4_2)
    cmds += orthowire(r4_1, um)
    # RL
    cmds += orthowire(uout, rl_1)
    # Supplies
    cmds += orthowire(vdd_p, uvp)
    cmds += orthowire(vss_m, uvm)

    # Grounds: VAC-, +, RL, VDD-, VSS+
    for pin in (vac_m, up, rl_2, vdd_m, vss_p):
        hy = pin[1] + 0.6
        cmds.append(ground_at_hotspot(pin[0], hy))
        cmds.append(place_wire(pin[0], pin[1], pin[0], hy))

    cmds += [
        place_alias(vac_p[0] - 0.15, vac_p[1] - 0.15, "VIN2"),
        place_alias(uout[0] + 0.15, uout[1] - 0.15, "VOUT2"),
        set_props_at_xy(*r3, {"VALUE": "1k", "Reference": "R3"}),
        set_props_at_xy(*r4, {"VALUE": "20k", "Reference": "R4"}),
        set_props_at_xy(*rl, {"VALUE": "1Meg", "Reference": "RL2"}),
        set_props_at_xy(*vac, {"ACMAG": "1", "DC": "0", "Reference": "VIN2"}),
        set_props_at_xy(*vdd, {"VALUE": "15V", "Reference": "VDD2"}),
        set_props_at_xy(*vss, {"VALUE": "15V", "Reference": "VSS2"}),
        set_props_at_xy(*u, {"Reference": "U2"}),
        f'PlaceText {ox:.2f} {oy - 0.9:.2f} {ox + 3.5:.2f} {oy - 0.6:.2f} "Lab2 Inv Av=-20"',
    ]
    return cmds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--noninv-only", action="store_true")
    ap.add_argument("--inv-only", action="store_true")
    args = ap.parse_args()

    cmds: list[str] = []
    if not args.inv_only:
        cmds += build_noninv((1.0, 1.2))
    if not args.noninv_only:
        cmds += build_inv((5.5, 1.2))
    cmds.append(save_cmd())

    if args.dry_run:
        print(delete_at(5.0, 1.0))
        for c in cmds:
            print(c)
        return 0

    # Remove probe TL074 at (5.0, 1.0) first (must precede PlacePart batches)
    print("DELETE probe", tcl(delete_at(5.0, 1.0)))
    time.sleep(0.2)

    print(f"Sending {len(cmds)} Tcl commands…")
    send_all(cmds)
    print("Done. In Capture: PSpice -> Create Netlist, then run Lab2_AC.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
