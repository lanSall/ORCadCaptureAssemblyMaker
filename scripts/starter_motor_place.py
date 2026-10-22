"""Place the starter MOSFET / SS56 motor-drive schematic on joeldesign PAGE1."""
from __future__ import annotations

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
    save_cmd,
    set_props_at_xy,
    snippet,
    split_place_wire_prop,
)

HOST, PORT = "127.0.0.1", 9020
ANALOG = lib_path("pspice/analog.olb")
SOURCE = lib_path("pspice/source.olb")
BREAKOUT = lib_path("pspice/breakout.olb")


def tcl(cmd: str, timeout: float = 30.0) -> str:
    if not cmd.endswith("\n"):
        cmd += "\n"
    with socket.create_connection((HOST, PORT), timeout=8) as sock:
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
        print("PLACE", c[:110])
        print(" ", tcl(c, timeout=25))
        time.sleep(0.50)
        print(f"  parts {before} -> {count_parts()}")
        tcl(save_cmd(), timeout=25)
        time.sleep(0.30)
    for c in buckets["ground"]:
        print("GND", c[:90])
        print(" ", tcl(c, timeout=15))
        time.sleep(0.40)
    tcl(save_cmd(), timeout=25)
    for i, c in enumerate(buckets["wire"]):
        toks = c.split()
        if len(toks) >= 5:
            try:
                x1, y1, x2, y2 = map(float, toks[1:5])
                if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
                    print("SKIP zero wire", c)
                    continue
            except ValueError:
                pass
        print("WIRE", c)
        print(" ", tcl(c, timeout=15))
        time.sleep(0.18)
        if i % 5 == 4:
            tcl(save_cmd(), timeout=25)
    tcl(save_cmd(), timeout=25)
    for c in buckets["other"]:
        print("OTHER", c[:120])
        print(" ", tcl(c, timeout=20))
        time.sleep(0.25)
    tcl(save_cmd(), timeout=25)


def clear_leftovers() -> None:
    print("Clearing leftover grounds…")
    for _ in range(8):
        r = tcl(
            "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
            "set gIter [$lPage NewGlobalsIter $lStatus]; set g [$gIter NextGlobal $lStatus]; "
            "delete_DboPageGlobalsIter $gIter; "
            "if {$g != $lNullObj} { $lPage DeleteGlobal $g; return deleted } else { return none }",
            timeout=15,
        )
        print(" ", r)
        if "none" in r.lower() or "error" in r.lower():
            break
        time.sleep(0.2)
    while True:
        r = tcl(snippet("delete_one_wire"), timeout=15)
        if "none" in r.lower():
            break
        time.sleep(0.08)
    tcl(save_cmd(), timeout=25)
    time.sleep(1.5)
    print("parts=", count_parts())


def tip(origin: tuple[float, float], dx: float, dy: float) -> tuple[float, float]:
    return (origin[0] + dx, origin[1] + dy)


def build_orig() -> list[str]:
    """As-drawn starter switch + motor + sources. All rot=0."""
    r1, r2 = (-0.1, 0.1), (0.3, 0.1)
    c1, c2 = (-0.1, 0.1), (0.2, 0.1)
    l1, l2 = (-0.1, 0.2), (0.5, 0.2)
    d1, d2 = (-0.1, 0.1), (0.3, 0.1)
    # VDC (VPULSE via Tcl crashed Capture). Pulse stimuli patched in the .cir.
    vp, vm = (0.1, 0.0), (0.1, 0.4)
    mg, md, ms, mb = (-0.1, 0.2), (0.2, 0.0), (0.2, 0.4), (0.3, 0.5)

    vsig = (0.70, 2.70)
    r14 = (1.80, 2.60)
    q5 = (3.20, 2.50)
    r15 = (2.20, 3.50)
    d6 = (4.55, 2.40)
    ls = (5.20, 2.30)
    lm = (3.50, 1.20)
    rm = (4.30, 1.30)
    cb = (6.40, 3.20)
    vbat = (7.40, 2.50)

    cmds = [
        place_part(*vsig, SOURCE, "VDC"),
        place_part(*r14, ANALOG, "R"),
        place_part(*q5, BREAKOUT, "MbreakN"),
        place_part(*r15, ANALOG, "R"),
        place_part(*d6, BREAKOUT, "Dbreak"),
        place_part(*ls, ANALOG, "L"),
        place_part(*lm, ANALOG, "L"),
        place_part(*rm, ANALOG, "R"),
        place_part(*cb, ANALOG, "C"),
        place_part(*vbat, SOURCE, "VDC"),
    ]

    vsig_p, vsig_m = tip(vsig, *vp), tip(vsig, *vm)
    r14_1, r14_2 = tip(r14, *r1), tip(r14, *r2)
    qg, qd, qs, qb = tip(q5, *mg), tip(q5, *md), tip(q5, *ms), tip(q5, *mb)
    r15_1, r15_2 = tip(r15, *r1), tip(r15, *r2)
    d6_a, d6_k = tip(d6, *d1), tip(d6, *d2)
    ls_1, ls_2 = tip(ls, *l1), tip(ls, *l2)
    lm_1, lm_2 = tip(lm, *l1), tip(lm, *l2)
    rm_1, rm_2 = tip(rm, *r1), tip(rm, *r2)
    cb_1, cb_2 = tip(cb, *c1), tip(cb, *c2)
    vb_p, vb_m = tip(vbat, *vp), tip(vbat, *vm)

    gate_y = r14_1[1]
    drain_y = qd[1]
    vpwr_y = ls_2[1]

    # Starter sgn → R14 → gate
    cmds += [
        place_wire(vsig_p[0], vsig_p[1], vsig_p[0], gate_y),
        place_wire(vsig_p[0], gate_y, r14_1[0], gate_y),
        place_wire(r14_2[0], r14_2[1], qg[0], qg[1]),
    ]
    # R15 pulldown from R14 pin2 (junction) 
    jx = r14_2[0]
    cmds += [
        place_wire(jx, gate_y, jx, r15_1[1]),
        place_wire(jx, r15_1[1], r15_1[0], r15_1[1]),
    ]
    # Drain → D6 anode → Lstray → VPWR
    cmds += [
        place_wire(qd[0], qd[1], d6_a[0], d6_a[1]),
        place_wire(d6_k[0], d6_k[1], ls_1[0], ls_1[1]),
    ]
    # Motor LM-RM from drain up to VPWR
    cmds += [
        place_wire(qd[0], qd[1], lm_1[0], lm_1[1]),
        place_wire(lm_2[0], lm_2[1], rm_1[0], rm_1[1]),
        place_wire(rm_2[0], rm_2[1], ls_2[0], rm_2[1]),
        place_wire(ls_2[0], rm_2[1], ls_2[0], ls_2[1]),
    ]
    # VPWR rail to battery +
    cmds += [
        place_wire(ls_2[0], ls_2[1], vb_p[0], vpwr_y),
        place_wire(vb_p[0], vpwr_y, vb_p[0], vb_p[1]),
    ]
    # CB from VPWR down to capacitor then GND
    cmds += [
        place_wire(ls_2[0], ls_2[1], cb_1[0], ls_2[1]),
        place_wire(cb_1[0], ls_2[1], cb_1[0], cb_1[1]),
    ]
    # MOSFET bulk to source
    cmds += [
        place_wire(qb[0], qb[1], qs[0], qb[1]),
        place_wire(qs[0], qb[1], qs[0], qs[1]),
    ]

    # Grounds — straight down only
    for pin, drop in (
        (vsig_m, 0.70),
        (r15_2, 0.55),
        (qs, 0.70),
        (cb_2, 0.55),
        (vb_m, 0.70),
    ):
        hy = pin[1] + drop
        cmds.append(ground_at_hotspot(pin[0], hy))
        cmds.append(place_wire(pin[0], pin[1], pin[0], hy))

    cmds += [
        place_alias((vsig_p[0] + r14_1[0]) / 2, gate_y - 0.18, "ST_SGN"),
        place_alias((r14_2[0] + qg[0]) / 2, gate_y - 0.18, "VG"),
        place_alias(qd[0] + 0.15, drain_y - 0.20, "START_M"),
        place_alias((ls_2[0] + vb_p[0]) / 2, vpwr_y - 0.18, "VPWR"),
        set_props_at_xy(
            *vsig,
            {"Reference": "VSIG", "VALUE": "5Vdc", "DC": "5Vdc"},
        ),
        set_props_at_xy(
            *vbat,
            {"Reference": "VBAT", "VALUE": "11.1Vdc", "DC": "11.1Vdc"},
        ),
        set_props_at_xy(*r14, {"Reference": "R14", "VALUE": "100"}),
        set_props_at_xy(*r15, {"Reference": "R15", "VALUE": "10k"}),
        set_props_at_xy(
            *q5,
            {"Reference": "Q5", "MODEL": "FDS8840NZ", "L": "2u", "W": "0.25"},
        ),
        set_props_at_xy(*d6, {"Reference": "D6", "MODEL": "SS56"}),
        set_props_at_xy(*ls, {"Reference": "Lstray", "VALUE": "400nH"}),
        set_props_at_xy(*lm, {"Reference": "LM", "VALUE": "47uH"}),
        set_props_at_xy(*rm, {"Reference": "RM", "VALUE": "0.75"}),
        set_props_at_xy(*cb, {"Reference": "CB", "VALUE": "100u"}),
        save_cmd(),
    ]
    return cmds


def build_fix() -> list[str]:
    """Hardened copy, lower on the page (y+3.55)."""
    dy = 3.55
    r1, r2 = (-0.1, 0.1), (0.3, 0.1)
    c1, c2 = (-0.1, 0.1), (0.2, 0.1)
    l1, l2 = (-0.1, 0.2), (0.5, 0.2)
    d1, d2 = (-0.1, 0.1), (0.3, 0.1)
    vp, vm = (0.1, -0.1), (0.1, 0.3)
    mg, md, ms, mb = (-0.1, 0.2), (0.2, 0.0), (0.2, 0.4), (0.3, 0.5)

    vsig = (0.70, 2.80 + dy)
    r14 = (1.80, 2.60 + dy)
    q5 = (3.20, 2.50 + dy)
    r15 = (1.70, 3.50 + dy)
    d6 = (4.55, 2.40 + dy)
    lm = (3.50, 1.20 + dy)
    rm = (4.30, 1.30 + dy)
    cb = (6.00, 3.20 + dy)
    cdec = (6.55, 3.20 + dy)
    vbat = (7.50, 2.60 + dy)
    dgs = (2.55, 3.50 + dy)
    dtvs = (3.70, 3.45 + dy)
    rsn = (4.70, 3.45 + dy)
    csn = (5.25, 3.45 + dy)

    cmds = [
        place_part(*vsig, SOURCE, "VPULSE"),
        place_part(*r14, ANALOG, "R"),
        place_part(*q5, BREAKOUT, "MbreakN"),
        place_part(*r15, ANALOG, "R"),
        place_part(*d6, BREAKOUT, "Dbreak"),
        place_part(*lm, ANALOG, "L"),
        place_part(*rm, ANALOG, "R"),
        place_part(*cb, ANALOG, "C"),
        place_part(*cdec, ANALOG, "C"),
        place_part(*vbat, SOURCE, "VPULSE"),
        place_part(*dgs, BREAKOUT, "Dbreak"),
        place_part(*dtvs, BREAKOUT, "Dbreak"),
        place_part(*rsn, ANALOG, "R"),
        place_part(*csn, ANALOG, "C"),
    ]

    vsig_p, vsig_m = tip(vsig, *vp), tip(vsig, *vm)
    r14_1, r14_2 = tip(r14, *r1), tip(r14, *r2)
    qg, qd, qs, qb = tip(q5, *mg), tip(q5, *md), tip(q5, *ms), tip(q5, *mb)
    r15_1, r15_2 = tip(r15, *r1), tip(r15, *r2)
    d6_a, d6_k = tip(d6, *d1), tip(d6, *d2)
    lm_1, lm_2 = tip(lm, *l1), tip(lm, *l2)
    rm_1, rm_2 = tip(rm, *r1), tip(rm, *r2)
    cb_1, cb_2 = tip(cb, *c1), tip(cb, *c2)
    cd_1, cd_2 = tip(cdec, *c1), tip(cdec, *c2)
    vb_p, vb_m = tip(vbat, *vp), tip(vbat, *vm)
    dgs_a, dgs_k = tip(dgs, *d1), tip(dgs, *d2)
    tvs_a, tvs_k = tip(dtvs, *d1), tip(dtvs, *d2)
    rsn_1, rsn_2 = tip(rsn, *r1), tip(rsn, *r2)
    csn_1, csn_2 = tip(csn, *c1), tip(csn, *c2)

    gate_y = r14_1[1]
    vpwr_y = d6_k[1]

    cmds += [
        place_wire(vsig_p[0], vsig_p[1], vsig_p[0], gate_y),
        place_wire(vsig_p[0], gate_y, r14_1[0], gate_y),
        place_wire(r14_2[0], r14_2[1], qg[0], qg[1]),
        place_wire(r15_2[0], r15_2[1], r15_2[0], gate_y),
        place_wire(r15_2[0], gate_y, r14_2[0], gate_y),
        place_wire(qd[0], qd[1], d6_a[0], d6_a[1]),
        place_wire(qd[0], qd[1], lm_1[0], lm_1[1]),
        place_wire(lm_2[0], lm_2[1], rm_1[0], rm_1[1]),
        place_wire(rm_2[0], rm_2[1], d6_k[0], rm_2[1]),
        place_wire(d6_k[0], rm_2[1], d6_k[0], d6_k[1]),
        place_wire(d6_k[0], d6_k[1], vb_p[0], vpwr_y),
        place_wire(vb_p[0], vpwr_y, vb_p[0], vb_p[1]),
        place_wire(d6_k[0], d6_k[1], cb_1[0], d6_k[1]),
        place_wire(cb_1[0], d6_k[1], cb_1[0], cb_1[1]),
        place_wire(cb_2[0], cb_2[1], cd_1[0], cd_1[1]),
        place_wire(qb[0], qb[1], qs[0], qb[1]),
        place_wire(qs[0], qb[1], qs[0], qs[1]),
        # GS zener: cathode (pin2) to gate, anode to GND via pin1 drop
        place_wire(dgs_k[0], dgs_k[1], dgs_k[0], gate_y),
        place_wire(dgs_k[0], gate_y, r14_2[0], gate_y),
        # TVS anode left / cathode toward drain X
        place_wire(tvs_k[0], tvs_k[1], tvs_k[0], qd[1]),
        place_wire(tvs_k[0], qd[1], qd[0], qd[1]),
        place_wire(rsn_1[0], rsn_1[1], rsn_1[0], qd[1]),
        place_wire(rsn_1[0], qd[1], qd[0], qd[1]),
        place_wire(rsn_2[0], rsn_2[1], csn_1[0], csn_1[1]),
    ]

    for pin, drop in (
        (vsig_m, 0.55),
        (r15_1, 0.50),
        (qs, 0.55),
        (cb_2, 0.40),
        (cd_2, 0.40),
        (vb_m, 0.55),
        (dgs_a, 0.45),
        (tvs_a, 0.45),
        (csn_2, 0.40),
    ):
        hy = pin[1] + drop
        if hy > 7.45:
            hy = 7.45
        cmds.append(ground_at_hotspot(pin[0], hy))
        cmds.append(place_wire(pin[0], pin[1], pin[0], hy))

    cmds += [
        place_alias((vsig_p[0] + r14_1[0]) / 2, gate_y - 0.18, "ST_SGN2"),
        place_alias(qd[0] + 0.15, qd[1] - 0.20, "START_M2"),
        place_alias((d6_k[0] + vb_p[0]) / 2, vpwr_y - 0.18, "VPWR2"),
        set_props_at_xy(
            *vsig,
            {
                "Reference": "VSIG2",
                "V1": "0",
                "V2": "5",
                "TD": "0.2m",
                "TR": "8n",
                "TF": "8n",
                "PW": "1.8m",
                "PER": "8m",
            },
        ),
        set_props_at_xy(
            *vbat,
            {
                "Reference": "VBAT2",
                "V1": "11.1",
                "V2": "0",
                "TD": "3.5m",
                "TR": "80n",
                "TF": "80n",
                "PW": "10m",
                "PER": "20m",
            },
        ),
        set_props_at_xy(*r14, {"Reference": "R14B", "VALUE": "220"}),
        set_props_at_xy(*r15, {"Reference": "R15B", "VALUE": "4.7k"}),
        set_props_at_xy(
            *q5,
            {"Reference": "Q5B", "MODEL": "FDS8840NZ", "L": "2u", "W": "0.25"},
        ),
        set_props_at_xy(*d6, {"Reference": "D6B", "MODEL": "SS10100"}),
        set_props_at_xy(*lm, {"Reference": "LM2", "VALUE": "47uH"}),
        set_props_at_xy(*rm, {"Reference": "RM2", "VALUE": "0.75"}),
        set_props_at_xy(*cb, {"Reference": "CB2", "VALUE": "470u"}),
        set_props_at_xy(*cdec, {"Reference": "CDEC", "VALUE": "100n"}),
        set_props_at_xy(*dgs, {"Reference": "DGS", "MODEL": "D15V"}),
        set_props_at_xy(*dtvs, {"Reference": "DTVS", "MODEL": "SMBJ28A"}),
        set_props_at_xy(*rsn, {"Reference": "RSN", "VALUE": "10"}),
        set_props_at_xy(*csn, {"Reference": "CSN", "VALUE": "2.2n"}),
        save_cmd(),
    ]
    return cmds


def main() -> None:
    ping = tcl("IsSchematicViewActive", timeout=8)
    if not ping.startswith("1"):
        print("Schematic view not active:", repr(ping))
        sys.exit(1)
    resume = "--resume" in sys.argv
    if not resume:
        clear_leftovers()
    cmds = build_orig()
    if "--fix" in sys.argv:
        cmds += build_fix()
    if resume:
        b = split_place_wire_prop(cmds)
        cmds = b["wire"] + b["other"]
        print("RESUME wires+props only")
    print(f"Sending {len(cmds)} commands…")
    send_all(cmds)
    print("DONE parts=", count_parts())
    print("LIST", tcl(snippet("list_parts")))


if __name__ == "__main__":
    main()
