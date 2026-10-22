"""Rebuild Lab 8 Figure 6 CS amp with document-like readable layout.

Matches ECEN3314 Lab8 Fig 6 topology (page 7) without SetRotation
(SetRotation hung Capture in this environment):

              VDD=10
                |
        +------RD 330------+   (horizontal above drain)
                |
  VGG --Vin-- g M1 d ----+---- C1 ---- Vout
               |s        |              |
              gnd     junction         RL 10k → gnd

Usage:
  py -3 scripts/lab8_place.py --rebuild
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from placement_lib import (  # noqa: E402
    ground_at_hotspot,
    lib_path,
    place_alias,
    place_part,
    place_wire,
    reload_catalog,
    save_cmd,
    set_props_at_xy,
    snippet,
    split_place_wire_prop,
)

HOST, PORT = "127.0.0.1", 9020
ANALOG = lib_path("pspice/analog.olb")
SOURCE = lib_path("pspice/source.olb")
BREAKOUT = lib_path("pspice/breakout.olb")
OFFSETS_PATH = ROOT / "pin_offsets.json"


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
    buckets = split_place_wire_prop(cmds)
    for c in buckets["place"]:
        before = count_parts()
        print("PLACE", c[:90])
        print(" ", tcl(c, timeout=20))
        time.sleep(0.55)
        print(f"  parts {before} -> {count_parts()}")
        tcl(save_cmd(), timeout=25)
        time.sleep(0.35)
    for c in buckets["ground"]:
        print("GND", c[:90])
        print(" ", tcl(c, timeout=15))
        time.sleep(0.45)
    tcl(save_cmd(), timeout=25)
    for i, c in enumerate(buckets["wire"]):
        print("WIRE", c)
        print(" ", tcl(c, timeout=15))
        time.sleep(0.22)
        if i % 5 == 4:
            tcl(save_cmd(), timeout=25)
    tcl(save_cmd(), timeout=25)
    for c in buckets["other"]:
        print("OTHER", c[:100])
        print(" ", tcl(c, timeout=20))
        time.sleep(0.28)
    tcl(save_cmd(), timeout=25)


def clear_page() -> None:
    print("Clearing wires…")
    while True:
        r = tcl(snippet("delete_one_wire"), timeout=15)
        if "none" in r.lower():
            break
        time.sleep(0.1)
    print("Clearing parts…")
    while True:
        r = tcl(snippet("delete_one_part"), timeout=15)
        if "none" in r.lower():
            break
        time.sleep(0.15)
    print("Clearing grounds…")
    for _ in range(20):
        r = tcl(
            "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
            "set gIter [$lPage NewGlobalsIter $lStatus]; set g [$gIter NextGlobal $lStatus]; "
            "delete_DboPageGlobalsIter $gIter; "
            "if {$g != $lNullObj} { $lPage DeleteGlobal $g; return deleted } else { return none }",
            timeout=15,
        )
        if "none" in r.lower() or "error" in r.lower():
            break
        time.sleep(0.2)
    tcl(save_cmd(), timeout=25)
    print("Cleared. parts=", count_parts())


def tip(origin: tuple[float, float], dx: float, dy: float) -> tuple[float, float]:
    return (origin[0] + dx, origin[1] + dy)


def measure_mbreakn(ox: float = 0.6, oy: float = 0.6) -> dict[str, list[float]]:
    print("Measuring MbreakN…")
    tcl(place_part(ox, oy, BREAKOUT, "MbreakN"), timeout=20)
    time.sleep(0.5)
    raw = tcl(
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set lIter [$lPage NewPartInstsIter $lStatus]; set lInst [$lIter NextPartInst $lStatus]; "
        "set out {}; while {$lInst != $lNullObj} { "
        "set loc [$lInst GetLocation $lStatus]; "
        "set px [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
        "set py [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
        f"if {{abs($px-{ox})<0.05 && abs($py-{oy})<0.05}} {{ "
        "set lPlaced [DboPartInstToDboPlacedInst $lInst]; "
        "set lPinIter [$lPlaced NewPinsIter $lStatus]; set lPin [$lPinIter NextPin $lStatus]; "
        "while {$lPin != $lNullObj} { "
        "set pn [DboTclHelper_sMakeCString]; $lPin GetPinName $pn; "
        "set hs [$lPin GetOffsetHotSpot $lStatus]; "
        "set hx [expr {[DboTclHelper_sGetCPointX $hs]/100.0}]; "
        "set hy [expr {[DboTclHelper_sGetCPointY $hs]/100.0}]; "
        "lappend out \"[DboTclHelper_sGetConstCharPtr $pn]=[expr {$hx-$px}],[expr {$hy-$py}]\"; "
        "set lPin [$lPinIter NextPin $lStatus] }; delete_DboPartInstPinsIter $lPinIter }; "
        "set lInst [$lIter NextPartInst $lStatus] }; delete_DboPagePartInstsIter $lIter; "
        "return [join $out {|}]"
    )
    tcl(
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set lIter [$lPage NewPartInstsIter $lStatus]; set victim NULL; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { "
        "set loc [$lInst GetLocation $lStatus]; "
        "set px [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
        "set py [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
        f"if {{abs($px-{ox})<0.05 && abs($py-{oy})<0.05}} {{ set victim $lInst }}; "
        "set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; "
        "if {$victim != $lNullObj} { $lPage DeletePartInst $victim }; expr 1"
    )
    tcl(save_cmd(), timeout=20)
    pins: dict[str, list[float]] = {}
    for piece in raw.split("|"):
        if "=" not in piece:
            continue
        name, xy = piece.split("=", 1)
        x, y = xy.split(",")
        pins[name.strip().lower()] = [round(float(x), 3), round(float(y), 3)]
    print("MbreakN pins", pins)
    if pins:
        data = json.loads(OFFSETS_PATH.read_text(encoding="utf-8"))
        old = data["libraries"]["pspice/breakout.olb"].get("MbreakN", {})
        merged = {k: v for k, v in old.items() if str(k).startswith("_")}
        for k in ("g", "d", "s", "b"):
            merged[k] = pins.get(k, old.get(k))
        data["libraries"]["pspice/breakout.olb"]["MbreakN"] = merged
        OFFSETS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return pins


def build_fig6_readable(origin: tuple[float, float] = (1.2, 1.5)) -> list[str]:
    """Readable Fig 6 — PDF topology, generous spacing, orthogonal rails.

    Capture analog R stays horizontal (rotation hangs Capture). Visual still
    follows the lab figure: input left, MOSFET center, RD/VDD above drain,
    C1 then RL to the right, four grounds.
    """
    ox, oy = origin

    # rot0 offsets
    r1, r2 = (-0.1, 0.1), (0.3, 0.1)
    c_off1, c_off2 = (-0.1, 0.1), (0.2, 0.1)
    vsin_p, vsin_m = (0.1, -0.1), (0.1, 0.3)
    vdc_p, vdc_m = (0.1, 0.0), (0.1, 0.4)
    mg_o, md_o = (-0.1, 0.2), (0.2, 0.0)
    ms_o, mb_o = (0.2, 0.4), (0.3, 0.5)

    # --- component origins (spread out like the PDF) ---
    vgg = (ox + 0.0, oy + 2.1)          # far left
    m1 = (ox + 2.8, oy + 2.0)           # center MOSFET
    md = tip(m1, *md_o)

    # RD above drain: pin mid-line above drain X; leave clear air gap
    rd = (md[0] - 0.1, oy + 0.55)       # pin Y ≈ oy+0.65
    rd1, rd2 = tip(rd, *r1), tip(rd, *r2)

    # VDD to the RIGHT of RD (PDF style battery on the top-right)
    vdd = (rd2[0] + 0.9, rd1[1] - 0.1)
    vddp, vddm = tip(vdd, *vdc_p), tip(vdd, *vdc_m)

    # C1 on the drain Y rail (horizontal coupling)
    c1 = (md[0] + 1.3, md[1] - 0.1)
    c_l, c_r = tip(c1, *c_off1), tip(c1, *c_off2)

    # RL: drop from Vout then horizontal to ground column (readable load)
    # Place RL below-right of C1 so Vout stub goes down into RL pin1
    rl = (c_r[0] + 0.9, md[1] + 0.55)
    rl1, rl2 = tip(rl, *r1), tip(rl, *r2)

    cmds: list[str] = [
        place_part(*vgg, SOURCE, "VSIN"),
        place_part(*m1, BREAKOUT, "MbreakN"),
        place_part(*rd, ANALOG, "R"),
        place_part(*vdd, SOURCE, "VDC"),
        place_part(*c1, ANALOG, "C"),
        place_part(*rl, ANALOG, "R"),
    ]

    vp, vm = tip(vgg, *vsin_p), tip(vgg, *vsin_m)
    mg, ms, mb = tip(m1, *mg_o), tip(m1, *ms_o), tip(m1, *mb_o)
    jx, jy = md[0], md[1]
    gate_y = mg[1]

    # 1) Clean Vin rail into gate (horizontal)
    cmds += [
        place_wire(vp[0], vp[1], vp[0], gate_y),
        place_wire(vp[0], gate_y, mg[0], gate_y),
    ]

    # 2) Drain junction UP to RD (pick nearer RD pin as bottom feed), then RD → VDD+
    # Use RD pin1 as the drain-side feed (left pin), pin2 toward VDD
    # Vertical riser on drain X up to RD pin Y, then into pin1
    cmds += [
        place_wire(jx, jy, jx, rd1[1]),
        place_wire(jx, rd1[1], rd1[0], rd1[1]),
        place_wire(rd2[0], rd2[1], vddp[0], rd2[1]),
        place_wire(vddp[0], rd2[1], vddp[0], vddp[1]),
    ]

    # 3) Drain → C1 on one horizontal rail (component body is the connection)
    cmds.append(place_wire(jx, jy, c_l[0], c_l[1]))

    # 4) Vout: from C1 right → stub → down into RL pin1; RL pin2 → ground
    vout_x = c_r[0] + 0.45
    cmds += [
        place_wire(c_r[0], c_r[1], vout_x, c_r[1]),
        place_wire(vout_x, c_r[1], vout_x, rl1[1]),
        place_wire(vout_x, rl1[1], rl1[0], rl1[1]),
    ]

    # 5) Bulk → source (short local, not on signal rails)
    cmds += [
        place_wire(mb[0], mb[1], ms[0], mb[1]),
        place_wire(ms[0], mb[1], ms[0], ms[1]),
    ]

    # 6) Four grounds like the PDF — straight down only
    for pin, drop in ((vm, 0.75), (ms, 0.70), (vddm, 0.80), (rl2, 0.65)):
        hy = pin[1] + drop
        cmds.append(ground_at_hotspot(pin[0], hy))
        cmds.append(place_wire(pin[0], pin[1], pin[0], hy))

    cmds += [
        place_alias((vp[0] + mg[0]) / 2, gate_y - 0.15, "Vin"),
        place_alias(vout_x + 0.05, c_r[1] - 0.15, "Vout"),
        set_props_at_xy(
            *vgg,
            {
                "Reference": "VGG",
                "VOFF": "2.8",
                "VAMPL": "0.1",
                "FREQ": "1kHz",
                "ACMAG": "1",
            },
        ),
        set_props_at_xy(*vdd, {"Reference": "VDD", "VALUE": "10Vdc", "DC": "10Vdc"}),
        set_props_at_xy(*rd, {"Reference": "RD", "VALUE": "330"}),
        set_props_at_xy(*c1, {"Reference": "C1", "VALUE": "47u"}),
        set_props_at_xy(*rl, {"Reference": "RL", "VALUE": "10k"}),
        set_props_at_xy(*m1, {"Reference": "M1", "MODEL": "2N7000"}),
        save_cmd(),
    ]
    return cmds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--origin", nargs=2, type=float, default=[1.2, 1.5])
    args = ap.parse_args()

    ping = tcl("IsSchematicViewActive", timeout=8)
    if not ping.startswith("1"):
        print("Schematic view not active / Capture not responding:", repr(ping))
        print("Restart Capture, re-source CaptureMCPPortConnection, open PAGE1, then re-run --rebuild.")
        sys.exit(1)

    if args.measure:
        measure_mbreakn()
        return

    cmds = build_fig6_readable((args.origin[0], args.origin[1]))
    if args.dry_run:
        for c in cmds:
            print(c)
        return

    if args.rebuild or count_parts() not in ("0", ""):
        clear_page()
        measure_mbreakn()
        reload_catalog()
        cmds = build_fig6_readable((args.origin[0], args.origin[1]))

    print(f"Sending {len(cmds)} commands…")
    send_all(cmds)
    print("DONE parts=", count_parts())
    print("LIST", tcl(snippet("list_parts")))


if __name__ == "__main__":
    main()
