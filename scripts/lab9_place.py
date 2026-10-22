"""Place Lab 9 CE amplifier circuits on Capture PAGE1 via MCP socket.

Requires Capture with:
  source C:/Users/lance/tcl-mcp-server/CaptureMCPPortConnection

Then:
  python scripts/lab9_place.py
"""

from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from placement_lib import lib_path, pin_tip, place_ground, place_part, place_wire, set_prop

HOST, PORT = "127.0.0.1", 9020
ANALOG = lib_path("pspice/analog.olb")
SOURCE = lib_path("pspice/source.olb")
BIPOLAR = lib_path("pspice/bipolar.olb")


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


def batch(cmds: list[str], delay_s: float = 0.08) -> list[str]:
    out = []
    for c in cmds:
        out.append(tcl(c if c.endswith("\n") else c + "\n"))
        time.sleep(delay_s)
    return out


def measure_q_pins() -> dict[str, list[float]]:
    """Place Q2N3904 at known origin, read pin offsets, delete it."""
    ox, oy = 0.5, 0.5
    batch([place_part(ox, oy, BIPOLAR, "Q2N3904")], 0.15)
    raw = tcl(
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set lIter [$lPage NewPartInstsIter $lStatus]; set lInst [$lIter NextPartInst $lStatus]; "
        "set out {}; while {$lInst != $lNullObj} { "
        "set ref [DboTclHelper_sMakeCString]; $lInst GetReference $ref; "
        "set loc [$lInst GetLocation $lStatus]; "
        "set ox [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
        "set oy [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
        "if {abs($ox-0.5)<0.05 && abs($oy-0.5)<0.05} { "
        "set lPlaced [DboPartInstToDboPlacedInst $lInst]; "
        "set lPinIter [$lPlaced NewPinsIter $lStatus]; set lPin [$lPinIter NextPin $lStatus]; "
        "while {$lPin != $lNullObj} { "
        "set pn [DboTclHelper_sMakeCString]; $lPin GetPinName $pn; "
        "set hs [$lPin GetOffsetHotSpot $lStatus]; "
        "set hx [expr {[DboTclHelper_sGetCPointX $hs]/100.0}]; "
        "set hy [expr {[DboTclHelper_sGetCPointY $hs]/100.0}]; "
        "lappend out \"[DboTclHelper_sGetConstCharPtr $pn]=[expr {$hx-$ox}],[expr {$hy-$oy}]\"; "
        "set lPin [$lPinIter NextPin $lStatus] }; delete_DboPartInstPinsIter $lPinIter }; "
        "set lInst [$lIter NextPartInst $lStatus] }; delete_DboPagePartInstsIter $lIter; "
        "return [join $out {|}]"
    )
    # delete probe part
    tcl(
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set lIter [$lPage NewPartInstsIter $lStatus]; set lInst [$lIter NextPartInst $lStatus]; "
        "set victim NULL; while {$lInst != $lNullObj} { set victim $lInst; "
        "set lInst [$lIter NextPartInst $lStatus] }; delete_DboPagePartInstsIter $lIter; "
        "if {$victim != $lNullObj} { $lPage DeletePartInst $victim }; expr 1"
    )
    pins: dict[str, list[float]] = {}
    for piece in raw.split("|"):
        if "=" not in piece:
            continue
        name, xy = piece.split("=", 1)
        x, y = xy.split(",")
        pins[name.strip().lower()] = [float(x), float(y)]
    return pins


def clear_page() -> None:
    while True:
        r = tcl(
            "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
            "set lIter [$lPage NewPartInstsIter $lStatus]; set lInst [$lIter NextPartInst $lStatus]; "
            "set victim NULL; while {$lInst != $lNullObj} { set victim $lInst; "
            "set lInst [$lIter NextPartInst $lStatus] }; delete_DboPagePartInstsIter $lIter; "
            "if {$victim != $lNullObj} { $lPage DeletePartInst $victim; return deleted } else { return none }"
        )
        if "none" in r.lower():
            break
        time.sleep(0.12)


def place_fig5(ox: float, oy: float, qoff: dict[str, list[float]], label: str) -> list[str]:
    q = (ox + 2.4, oy + 1.2)
    vsin = (ox + 0.5, oy + 1.2)
    rc = (ox + 2.1, oy + 0.2)
    vcc = (ox + 3.5, oy + 0.1)
    cmds = [
        f'PlaceText {ox:.2f} {oy - 0.4:.2f} {ox + 4.2:.2f} {oy - 0.15:.2f} "{label}"',
        place_part(*q, BIPOLAR, "Q2N3904"),
        place_part(*vsin, SOURCE, "VSIN"),
        place_part(*rc, ANALOG, "R"),
        place_part(*vcc, SOURCE, "VDC"),
    ]
    qb = (q[0] + qoff["b"][0], q[1] + qoff["b"][1])
    qc = (q[0] + qoff["c"][0], q[1] + qoff["c"][1])
    qe = (q[0] + qoff["e"][0], q[1] + qoff["e"][1])
    # pin name variants
    if "b" not in qoff:
        # try common names
        for k, v in qoff.items():
            kl = k.lower()
            if kl in ("b", "base"):
                qb = (q[0] + v[0], q[1] + v[1])
            elif kl in ("c", "collector"):
                qc = (q[0] + v[0], q[1] + v[1])
            elif kl in ("e", "emitter"):
                qe = (q[0] + v[0], q[1] + v[1])
    vs_p = pin_tip(vsin, "pspice/source.olb", "VSIN", "+")
    vs_m = pin_tip(vsin, "pspice/source.olb", "VSIN", "-")
    rc1 = pin_tip(rc, "pspice/analog.olb", "R", "1")
    rc2 = pin_tip(rc, "pspice/analog.olb", "R", "2")
    vp = pin_tip(vcc, "pspice/source.olb", "VDC", "+")
    vm = pin_tip(vcc, "pspice/source.olb", "VDC", "-")
    cmds += [
        place_wire(*vs_p, *qb),
        place_wire(qc[0], qc[1], rc1[0], qc[1]),
        place_wire(rc1[0], qc[1], *rc1),
        place_wire(*rc2, vp[0], rc2[1]),
        place_wire(vp[0], rc2[1], *vp),
        place_ground(vs_m[0] - 0.1, vs_m[1] + 0.7),
        place_ground(qe[0] - 0.1, qe[1] + 0.5),
        place_ground(vm[0] - 0.1, vm[1] + 0.5),
        place_wire(*vs_m, vs_m[0], vs_m[1] + 0.7),
        place_wire(*qe, qe[0], qe[1] + 0.5),
        place_wire(*vm, vm[0], vm[1] + 0.5),
        f"PlaceNetAlias {qb[0]:.2f} {qb[1] - 0.15:.2f} VIN",
        f"PlaceNetAlias {qc[0] + 0.2:.2f} {qc[1] - 0.15:.2f} VOUT",
        f"PlaceNetAlias {vp[0] + 0.15:.2f} {vp[1] - 0.15:.2f} VCC",
    ]
    return cmds


def place_fig6(ox: float, oy: float, qoff: dict[str, list[float]]) -> list[str]:
    cmds = place_fig5(ox, oy, qoff, "Fig6 CE + C/RL load (Lab9)")
    q = (ox + 2.4, oy + 1.2)
    qc = (q[0] + qoff.get("c", qoff.get("collector", [0.2, 0.0]))[0],
          q[1] + qoff.get("c", qoff.get("collector", [0.2, 0.0]))[1])
    c = (ox + 4.6, oy + 1.1)
    rl = (ox + 5.6, oy + 1.2)
    cmds += [
        place_part(*c, ANALOG, "C"),
        place_part(*rl, ANALOG, "R"),
    ]
    c1 = pin_tip(c, "pspice/analog.olb", "C", "1")
    c2 = pin_tip(c, "pspice/analog.olb", "C", "2")
    rl1 = pin_tip(rl, "pspice/analog.olb", "R", "1")
    rl2 = pin_tip(rl, "pspice/analog.olb", "R", "2")
    cmds += [
        place_wire(*qc, c1[0], qc[1]),
        place_wire(c1[0], qc[1], *c1),
        place_wire(*c2, *rl1),
        place_ground(rl2[0] - 0.1, rl2[1] + 0.7),
        place_wire(*rl2, rl2[0], rl2[1] + 0.7),
        f"PlaceNetAlias {rl1[0]:.2f} {rl1[1] - 0.15:.2f} VOUTL",
    ]
    return cmds


def set_lab9_values() -> list[str]:
    """Set RC=1k, VCC=5, VSIN params, C=10u, RL=10k by matching refs after place."""
    return [
        # These use first-match globs; place Fig5 then Fig6 so refs are sequential.
        set_prop("R1", "VALUE", "1k"),
        set_prop("R1", "Reference", "RC1"),
        set_prop("V1", "VALUE", "5V"),
        set_prop("V1", "Reference", "VCC1"),
        set_prop("V2", "VOFF", "330mV"),
        set_prop("V2", "VAMPL", "10mV"),
        set_prop("V2", "FREQ", "1kHz"),
        set_prop("V2", "Reference", "VIN1"),
    ]


def main() -> None:
    try:
        print(tcl("return ping"))
    except OSError as e:
        print("MCP socket not up:", e)
        print("In Capture Command Window run:")
        print("  source C:/Users/lance/tcl-mcp-server/CaptureMCPPortConnection")
        sys.exit(1)

    print("Clearing PAGE1...")
    clear_page()

    print("Measuring Q2N3904 pins...")
    qoff = measure_q_pins()
    print("Q pins:", qoff)
    if len(qoff) < 3:
        qoff = {"c": [0.2, 0.0], "b": [-0.1, 0.2], "e": [0.2, 0.4]}
        print("Using defaults", qoff)

    # cache offsets
    path = ROOT / "pin_offsets.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("libraries", {}).setdefault("pspice/bipolar.olb", {})["Q2N3904"] = qoff
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print("Placing Fig5...")
    batch(place_fig5(1.0, 1.8, qoff, "Fig5 CE amp Q2N3904 (Lab9)"), 0.09)
    print("Placing Fig6...")
    batch(place_fig6(7.0, 1.8, qoff), 0.09)

    # set values by scanning — safer than hard-coded refs
    print("Setting values...")
    # RC nearest left circuit
    batch(
        [
            # VSIN props: VOFF / VAMPL / FREQ — names vary; set all VSIN-like
            (
                "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
                "set lIter [$lPage NewPartInstsIter $lStatus]; set lInst [$lIter NextPartInst $lStatus]; "
                "while {$lInst != $lNullObj} { "
                "set ref [DboTclHelper_sMakeCString]; $lInst GetReference $ref; "
                "set r [DboTclHelper_sGetConstCharPtr $ref]; "
                "set loc [$lInst GetLocation $lStatus]; "
                "set ox [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
                "if {[string match {R*} $r]} { "
                "set n [DboTclHelper_sMakeCString {VALUE}]; "
                "set v [DboTclHelper_sMakeCString [expr {$ox < 6 ? {1k} : ($ox < 12 ? {1k} : {10k})} ]]; "
                "$lInst SetEffectivePropStringValue $n $v }; "
                "if {[string match {V*} $r]} { "
                "set n [DboTclHelper_sMakeCString {VALUE}]; "
                "set v [DboTclHelper_sMakeCString {5V}]; "
                "# only VDC-like at top get 5V — set VOFF on all V for safety "
                "catch {$lInst SetEffectivePropStringValue [DboTclHelper_sMakeCString {VOFF}] [DboTclHelper_sMakeCString {330mV}]}; "
                "catch {$lInst SetEffectivePropStringValue [DboTclHelper_sMakeCString {VAMPL}] [DboTclHelper_sMakeCString {10mV}]}; "
                "catch {$lInst SetEffectivePropStringValue [DboTclHelper_sMakeCString {FREQ}] [DboTclHelper_sMakeCString {1kHz}]}; "
                "}; "
                "if {[string match {C*} $r]} { "
                "set n [DboTclHelper_sMakeCString {VALUE}]; "
                "set v [DboTclHelper_sMakeCString {10u}]; "
                "$lInst SetEffectivePropStringValue $n $v }; "
                "set lInst [$lIter NextPartInst $lStatus] }; "
                "delete_DboPagePartInstsIter $lIter; expr 1"
            )
        ],
        0.2,
    )

    n = tcl(
        "set lStatus [DboState]; set lPage [GetActivePage]; set n 0; "
        "set lIter [$lPage NewPartInstsIter $lStatus]; set lNullObj NULL; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { incr n; set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; return \"parts=$n\""
    )
    print("Done:", n)


if __name__ == "__main__":
    main()
