"""Place ECEN 4013 Wk2 simulation homework: N=5 Bessel LPF, fc=3 kHz.

PDF: ECEN 4013 Wk 2_2 AgileScrumADconversion.pdf (Simulation Homework).
Topology: unity-gain Sallen-Key 2nd-order + 3rd-order VCVS, TL081 (listed op-amp).

Usage:
  python scripts/hw_bessel_lpf.py --inspect
  python scripts/hw_bessel_lpf.py --dry-run
  python scripts/hw_bessel_lpf.py --rebuild   # clear page, place PDF-like layout
  python scripts/hw_bessel_lpf.py --place
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
TL081_NAME = "TL081/301/TI"


def tcl(cmd: str, timeout: float = 30.0) -> str:
    if not cmd.endswith("\n"):
        cmd += "\n"
    last: Exception | None = None
    for attempt in range(3):
        try:
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
        except OSError as exc:
            last = exc
            time.sleep(0.8)
    return f"ERROR: {last}"


def count_parts() -> str:
    return tcl(
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set n 0; set lIter [$lPage NewPartInstsIter $lStatus]; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { incr n; set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; return $n"
    )


def list_parts() -> str:
    return tcl(
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set out {}; set lIter [$lPage NewPartInstsIter $lStatus]; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { "
        "set ref [DboTclHelper_sMakeCString]; $lInst GetReference $ref; "
        "set loc [$lInst GetLocation $lStatus]; "
        "set ox [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
        "set oy [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
        "lappend out \"[DboTclHelper_sGetConstCharPtr $ref]@$ox,$oy\"; "
        "set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; return [join $out { | }]"
    )


def send_all(cmds: list[str]) -> None:
    """Crash-safe: one PlacePart + save, then grounds, then wires."""
    buckets = split_place_wire_prop(cmds)
    for c in buckets["place"]:
        before = count_parts()
        print("PLACE", c[:90])
        print(" ", tcl(c, timeout=20))
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
        print("OTHER", c[:100])
        print(" ", tcl(c, timeout=15))
        time.sleep(0.25)
    tcl(save_cmd(), timeout=20)


def place_tl081(x: float, y: float) -> str:
    return place_part(x, y, TEX, TL081_NAME, "")


def tip_u(u: tuple[float, float], pin: str) -> tuple[float, float]:
    # TL081 single-amp symbol matches TL074 section-A pin geometry.
    return pin_tip(u, "pspice/tex_inst.olb", "TL081", pin)


def tip_r(r: tuple[float, float], pin: str) -> tuple[float, float]:
    return pin_tip(r, "pspice/analog.olb", "R", pin)


def tip_c(c: tuple[float, float], pin: str) -> tuple[float, float]:
    return pin_tip(c, "pspice/analog.olb", "C", pin)


def tip_vdc(v: tuple[float, float], pin: str) -> tuple[float, float]:
    return pin_tip(v, "pspice/source.olb", "VDC", pin)


def tip_vac(v: tuple[float, float], pin: str) -> tuple[float, float]:
    return pin_tip(v, "pspice/source.olb", "VAC", pin)


def path(*pts: tuple[float, float]) -> list[str]:
    cmds: list[str] = []
    cleaned: list[tuple[float, float]] = []
    for p in pts:
        if not cleaned or abs(cleaned[-1][0] - p[0]) > 1e-6 or abs(cleaned[-1][1] - p[1]) > 1e-6:
            cleaned.append(p)
    for a, b in zip(cleaned, cleaned[1:]):
        cmds.append(place_wire(a[0], a[1], b[0], b[1]))
    return cmds


def gnd_down(pin: tuple[float, float], dy: float = 0.55) -> list[str]:
    hx, hy = pin[0], pin[1] + dy
    return [ground_at_hotspot(hx, hy), place_wire(pin[0], pin[1], hx, hy)]


def gnd_offset(pin: tuple[float, float], dx: float, dy: float = 0.55) -> list[str]:
    """Ground a pin without a vertical that would pass through another pin on the same X."""
    mid = (pin[0] + dx, pin[1])
    hs = (pin[0] + dx, pin[1] + dy)
    return [
        ground_at_hotspot(hs[0], hs[1]),
        place_wire(pin[0], pin[1], *mid),
        place_wire(*mid, *hs),
    ]


DEL_WIRE = (
    "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
    "set wIter [$lPage NewWiresIter $lStatus]; set w [$wIter NextWire $lStatus]; "
    "delete_DboPageWiresIter $wIter; if {$w != $lNullObj} { $lPage DeleteWire $w; return dw } else { return none }"
)


DEL_PART = (
    "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
    "set lIter [$lPage NewPartInstsIter $lStatus]; set victim NULL; "
    "set lInst [$lIter NextPartInst $lStatus]; "
    "while {$lInst != $lNullObj} { set victim $lInst; set lInst [$lIter NextPartInst $lStatus]}; "
    "delete_DboPagePartInstsIter $lIter; "
    "if {$victim != $lNullObj} { $lPage DeletePartInst $victim; return deleted } else { return none }"
)
DEL_GLOBAL = (
    "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
    "set gIter [$lPage NewGlobalsIter $lStatus]; set g [$gIter NextGlobal $lStatus]; "
    "delete_DboPageGlobalsIter $gIter; "
    "if {$g != $lNullObj} { $lPage DeleteGlobal $g; return dg } else { return none }"
)


def clear_wires(max_n: int = 120) -> int:
    """One DeleteWire at a time. Do not save mid-loop — that crashed Capture."""
    n = 0
    for _ in range(max_n):
        r = tcl(DEL_WIRE)
        if "none" in r.lower() or r.startswith("ERROR"):
            break
        n += 1
        time.sleep(0.22)
    time.sleep(0.5)
    tcl(save_cmd(), timeout=20)
    return n


def clear_parts(max_n: int = 40) -> int:
    n = 0
    for _ in range(max_n):
        r = tcl(DEL_PART)
        if "none" in r.lower():
            break
        n += 1
        time.sleep(0.45)
        tcl(save_cmd(), timeout=20)
        time.sleep(0.25)
    return n


def clear_globals(max_n: int = 16) -> int:
    """One ground/global at a time — never loop DeleteGlobal without a pause."""
    n = 0
    for _ in range(max_n):
        r = tcl(DEL_GLOBAL)
        if "none" in r.lower() or r.startswith("ERROR"):
            break
        n += 1
        time.sleep(0.8)
        tcl(save_cmd(), timeout=20)
        time.sleep(0.4)
    return n


def r_from_pin1(px: float, py: float) -> tuple[float, float]:
    return (px + 0.1, py - 0.1)


def c_from_pin1(px: float, py: float) -> tuple[float, float]:
    return (px + 0.1, py - 0.1)


def u_from_plus(px: float, py: float) -> tuple[float, float]:
    return (px + 0.1, py - 0.1)


def vac_from_plus(px: float, py: float) -> tuple[float, float]:
    return (px - 0.1, py + 0.1)


def vdc_from_plus(px: float, py: float) -> tuple[float, float]:
    return (px - 0.1, py)


def orthowire_hv(a: tuple[float, float], b: tuple[float, float]) -> list[str]:
    """Manhattan path a→b, horizontal first (avoids TL081 N1/N2 on the OUT column)."""
    ax, ay = a
    bx, by = b
    if abs(ax - bx) < 1e-6 or abs(ay - by) < 1e-6:
        return [place_wire(ax, ay, bx, by)]
    mid = (bx, ay)
    return [place_wire(ax, ay, *mid), place_wire(*mid, bx, by)]


def follower_fb(out_tip: tuple[float, float], minus_tip: tuple[float, float]) -> list[str]:
    """OUT → IN- without riding the right-edge pin stack (N1 / OUT / N2)."""
    return orthowire_hv(out_tip, minus_tip)


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


def build_lpf(origin: tuple[float, float] = (0.50, 1.20)) -> list[str]:
    """PDF-like N=5 Bessel LPF — one signal rail, feedback above, shunts below.

    Left → right like the homework figure:

        VIN -- R1 -- nA -- R2 -- U1+     U1out -- R3 -- nC -- R4 -- nD -- R5 -- U2+
                  |                   |                |            |
                 C1 (2.2n) above     C2A||C2B         C3A||C3B     C4 (2.2n) above
                  └──── to U1out      to GND           to GND       └──── to U2out
                                                                C5 at U2+ to GND

    Pin-safe routing:
      • never travel vertically on the TL081 OUT x-column (N1 / OUT / N2)
      • never travel vertically through the other VDC terminal
      • parallel caps: two independent drops; do not bus along the cap pin row
      • shunt drops stay left of the op-amp +/− column
    """
    ox, oy = origin
    sy = oy + 2.10          # signal rail
    fb_y = oy + 0.48        # feedback capacitor pin row (above)
    sh_y = oy + 3.45        # shunt capacitor pin row (below)

    # --- pin targets on the signal rail (generous gaps, PDF left-to-right) ---
    vin_x = ox + 0.35
    r1a, r1b = ox + 0.90, ox + 1.30          # R1 24.9k
    r2a, r2b = ox + 1.90, ox + 2.30          # R2 24.9k
    u1p_x = ox + 3.40                         # 1.1" gap for C2 pair
    r3a, r3b = ox + 4.80, ox + 5.20          # R3 24.3k
    r4a, r4b = ox + 6.20, ox + 6.60          # R4 24.3k  (gap for C3 pair)
    r5a, r5b = ox + 7.20, ox + 7.60          # R5 24.3k
    u2p_x = ox + 8.30

    vac = vac_from_plus(vin_x, sy)
    r1 = r_from_pin1(r1a, sy)
    r2 = r_from_pin1(r2a, sy)
    u1 = u_from_plus(u1p_x, sy)
    r3 = r_from_pin1(r3a, sy)
    r4 = r_from_pin1(r4a, sy)
    r5 = r_from_pin1(r5a, sy)
    u2 = u_from_plus(u2p_x, sy)

    c1 = c_from_pin1(r1b, fb_y)              # C1 hangs on nA column
    c4 = c_from_pin1(r4b, fb_y)              # C4 hangs on nD column
    c2a = c_from_pin1(u1p_x - 0.70, sh_y)
    c2b = c_from_pin1(u1p_x - 0.30, sh_y)
    c3a = c_from_pin1(r3b + 0.18, sh_y)
    c3b = c_from_pin1(r3b + 0.55, sh_y)
    c5 = c_from_pin1(u2p_x - 0.35, sh_y)

    vdd = vdc_from_plus(ox + 9.35, oy + 0.25)
    vss = vdc_from_plus(ox + 9.35, oy + 4.50)

    cmds: list[str] = [
        place_tl081(*u1),
        place_tl081(*u2),
        place_part(*vac, SOURCE, "VAC"),
        place_part(*r1, ANALOG, "R"),
        place_part(*r2, ANALOG, "R"),
        place_part(*r3, ANALOG, "R"),
        place_part(*r4, ANALOG, "R"),
        place_part(*r5, ANALOG, "R"),
        place_part(*c1, ANALOG, "C"),
        place_part(*c2a, ANALOG, "C"),
        place_part(*c2b, ANALOG, "C"),
        place_part(*c3a, ANALOG, "C"),
        place_part(*c3b, ANALOG, "C"),
        place_part(*c4, ANALOG, "C"),
        place_part(*c5, ANALOG, "C"),
        place_part(*vdd, SOURCE, "VDC"),
        place_part(*vss, SOURCE, "VDC"),
    ]

    vac_p, vac_m = tip_vac(vac, "+"), tip_vac(vac, "-")
    r1_1, r1_2 = tip_r(r1, "1"), tip_r(r1, "2")
    r2_1, r2_2 = tip_r(r2, "1"), tip_r(r2, "2")
    r3_1, r3_2 = tip_r(r3, "1"), tip_r(r3, "2")
    r4_1, r4_2 = tip_r(r4, "1"), tip_r(r4, "2")
    r5_1, r5_2 = tip_r(r5, "1"), tip_r(r5, "2")
    c1_1, c1_2 = tip_c(c1, "1"), tip_c(c1, "2")
    c2a_1, c2a_2 = tip_c(c2a, "1"), tip_c(c2a, "2")
    c2b_1, c2b_2 = tip_c(c2b, "1"), tip_c(c2b, "2")
    c3a_1, c3a_2 = tip_c(c3a, "1"), tip_c(c3a, "2")
    c3b_1, c3b_2 = tip_c(c3b, "1"), tip_c(c3b, "2")
    c4_1, c4_2 = tip_c(c4, "1"), tip_c(c4, "2")
    c5_1, c5_2 = tip_c(c5, "1"), tip_c(c5, "2")
    u1p, u1m = tip_u(u1, "+"), tip_u(u1, "-")
    u1vp, u1vm, u1out = tip_u(u1, "V+"), tip_u(u1, "V-"), tip_u(u1, "OUT")
    u2p, u2m = tip_u(u2, "+"), tip_u(u2, "-")
    u2vp, u2vm, u2out = tip_u(u2, "V+"), tip_u(u2, "V-"), tip_u(u2, "OUT")
    vdd_p, vdd_m = tip_vdc(vdd, "+"), tip_vdc(vdd, "-")
    vss_p, vss_m = tip_vdc(vss, "+"), tip_vdc(vss, "-")

    # ---- Stage 1: 2nd-order Sallen-Key (left) ----
    cmds += path(vac_p, r1_1)                    # VIN rail
    cmds += path(r1_2, r2_1)                     # nA visible gap
    cmds += path(r2_2, u1p)
    cmds += follower_fb(u1out, u1m)
    # C1 feedback on the upper rail; enter OUT from the left at OUT y
    cmds += path(r1_2, (r1_2[0], fb_y), c1_1)
    out1_in = (u1out[0] - 0.30, u1out[1])
    cmds += path(c1_2, (c1_2[0], fb_y), (out1_in[0], fb_y), out1_in, u1out)
    # C2A||C2B: independent drops left of the +/− column
    cmds += path(u1p, (c2a_1[0], sy), c2a_1)
    cmds += path((c2b_1[0], sy), c2b_1)

    # ---- Stage 2: 3rd-order Sallen-Key (right) ----
    cmds += path(u1out, (r3_1[0], u1out[1]), r3_1)   # leave OUT to the right
    cmds += path(r3_2, r4_1)
    cmds += path(r4_2, r5_1)
    cmds += path(r5_2, u2p)
    cmds += follower_fb(u2out, u2m)
    cmds += path(r3_2, (c3a_1[0], sy), c3a_1)
    cmds += path((c3b_1[0], sy), c3b_1)
    out2_in = (u2out[0] - 0.30, u2out[1])
    cmds += path(r4_2, (r4_2[0], fb_y), c4_1)
    cmds += path(c4_2, (c4_2[0], fb_y), (out2_in[0], fb_y), out2_in, u2out)
    cmds += path(u2p, (c5_1[0], sy), c5_1)
    vout_stub = (u2out[0] + 0.40, u2out[1])
    cmds += path(u2out, vout_stub)

    # ---- ±15 V: V+ hop on the op-amp V+ y; V- drops around the shunt field ----
    vdd_x = vdd_p[0] - 0.45
    cmds += path(vdd_p, (vdd_x, vdd_p[1]), (vdd_x, u2vp[1]), u2vp, u1vp)
    vss_x = vss_m[0] - 0.55
    vee_bus = sh_y + 1.05
    cmds += path(u1vm, (u1vm[0], vee_bus))
    cmds += path(u2vm, (u2vm[0], vee_bus))
    cmds += path((u1vm[0], vee_bus), (u2vm[0], vee_bus), (vss_x, vee_bus), (vss_x, vss_m[1]), vss_m)

    for pin in (vac_m, c2a_2, c2b_2, c3a_2, c3b_2, c5_2, vdd_m):
        cmds += gnd_down(pin, 0.55)
    cmds += gnd_offset(vss_p, dx=-0.45, dy=0.60)

    cmds += [
        place_alias((vac_p[0] + r1_1[0]) / 2, sy - 0.12, "VIN"),
        place_alias(vout_stub[0] - 0.05, vout_stub[1] - 0.12, "VOUT"),
        set_props_at_xy(*r1, {"VALUE": "24.9k", "Reference": "R1"}),
        set_props_at_xy(*r2, {"VALUE": "24.9k", "Reference": "R2"}),
        set_props_at_xy(*r3, {"VALUE": "24.3k", "Reference": "R3"}),
        set_props_at_xy(*r4, {"VALUE": "24.3k", "Reference": "R4"}),
        set_props_at_xy(*r5, {"VALUE": "24.3k", "Reference": "R5"}),
        set_props_at_xy(*c1, {"VALUE": "2.2n", "Reference": "C1"}),
        set_props_at_xy(*c2a, {"VALUE": "270p", "Reference": "C2A"}),
        set_props_at_xy(*c2b, {"VALUE": "330p", "Reference": "C2B"}),
        set_props_at_xy(*c3a, {"VALUE": "1.5n", "Reference": "C3A"}),
        set_props_at_xy(*c3b, {"VALUE": "390p", "Reference": "C3B"}),
        set_props_at_xy(*c4, {"VALUE": "2.2n", "Reference": "C4"}),
        set_props_at_xy(*c5, {"VALUE": "680p", "Reference": "C5"}),
        set_props_at_xy(*vac, {"ACMAG": "1", "DC": "0", "Reference": "VIN"}),
        set_props_at_xy(*vdd, {"VALUE": "15Vdc", "DC": "15Vdc", "Reference": "VDD"}),
        set_props_at_xy(*vss, {"VALUE": "15Vdc", "DC": "15Vdc", "Reference": "VSS"}),
        set_props_at_xy(*u1, {"Reference": "U1"}),
        set_props_at_xy(*u2, {"Reference": "U2"}),
        f'PlaceText {ox:.2f} {oy - 0.05:.2f} {ox + 5.2:.2f} {oy + 0.25:.2f} "N=5 Bessel LPF   Av=0 dB   fc=3 kHz"',
        f'PlaceText {ox + 0.9:.2f} {oy + 0.85:.2f} {ox + 3.4:.2f} {oy + 1.10:.2f} "Stage 1  2nd-order SK"',
        f'PlaceText {ox + 4.5:.2f} {oy + 0.85:.2f} {ox + 7.6:.2f} {oy + 1.10:.2f} "Stage 2  3rd-order SK"',
        save_cmd(),
    ]
    return cmds


def measure_pins_at(x: float, y: float, tol: float = 0.08) -> str:
    return tcl(
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set lIter [$lPage NewPartInstsIter $lStatus]; set lInst [$lIter NextPartInst $lStatus]; "
        "set out {}; while {$lInst != $lNullObj} { "
        "set loc [$lInst GetLocation $lStatus]; "
        "set ox [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
        "set oy [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
        f"if {{abs($ox-{x})<{tol} && abs($oy-{y})<{tol}}} {{ "
        "set lPlaced [DboPartInstToDboPlacedInst $lInst]; "
        "set lPinIter [$lPlaced NewPinsIter $lStatus]; set lPin [$lPinIter NextPin $lStatus]; "
        "while {$lPin != $lNullObj} { "
        "set pn [DboTclHelper_sMakeCString]; $lPin GetPinName $pn; "
        "set num [DboTclHelper_sMakeCString]; $lPin GetPinNumber $num; "
        "set hs [$lPin GetOffsetHotSpot $lStatus]; "
        "set hx [expr {[DboTclHelper_sGetCPointX $hs]/100.0}]; "
        "set hy [expr {[DboTclHelper_sGetCPointY $hs]/100.0}]; "
        "lappend out \"[DboTclHelper_sGetConstCharPtr $pn]/[DboTclHelper_sGetConstCharPtr $num]=[expr {$hx-$ox}],[expr {$hy-$oy}]\"; "
        "set lPin [$lPinIter NextPin $lStatus] }; delete_DboPartInstPinsIter $lPinIter }; "
        "set lInst [$lIter NextPartInst $lStatus] }; delete_DboPagePartInstsIter $lIter; "
        "return [join $out {|}]"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--place", action="store_true")
    ap.add_argument("--probe-tl081", action="store_true")
    ap.add_argument("--rewire", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--origin", default="0.50,1.20")
    args = ap.parse_args()
    ox, oy = (float(v) for v in args.origin.split(","))

    if args.inspect:
        print("ping", tcl("expr 1"))
        print("active", tcl("IsSchematicViewActive"))
        print("count", count_parts())
        print("parts", list_parts())
        return 0

    if args.probe_tl081:
        cmd = place_tl081(1.00, 6.80)
        print("PLACE probe", cmd)
        print(" ", tcl(cmd, timeout=20))
        time.sleep(0.8)
        tcl(save_cmd(), timeout=20)
        print("pins", measure_pins_at(1.00, 6.80))
        print("count", count_parts())
        return 0

    cmds = build_lpf((ox, oy))
    if args.dry_run:
        for c in cmds:
            print(c)
        return 0

    if args.rebuild:
        print("clear parts", clear_parts())
        print("clear wires", clear_wires())
        print("clear grounds", clear_globals())
        print(f"place clean layout from {ox},{oy}")
        send_all(cmds)
        print("parts now:", list_parts())
        return 0

    if args.rewire:
        n = clear_wires()
        print(f"deleted {n} wires")
        time.sleep(0.3)
        buckets = split_place_wire_prop(cmds)
        send_all(buckets["ground"] + buckets["wire"] + [save_cmd()])
        print("rewire done")
        return 0

    if not args.place:
        ap.print_help()
        return 2

    print("DELETE probe TL081 @1.00,6.80", tcl(delete_at(1.00, 6.80)))
    time.sleep(0.3)
    tcl(save_cmd(), timeout=20)
    print(f"Sending {len(cmds)} Tcl commands from origin {ox},{oy} …")
    send_all(cmds)
    print("parts now:", list_parts())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
