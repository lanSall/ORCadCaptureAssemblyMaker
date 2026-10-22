"""Build Capture Tcl command batches for Lab 9 BJT CE amplifier circuits.

Figures:
  Fig5 — CE amp (Q2N3904, VSIN, VCC, RC) — Section 6 sim schematic
  Fig6 — Fig5 + C coupling + RL load
  Fig1–3 — topology sketches (CE / CB / emitter follower)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from placement_lib import (  # noqa: E402
    chunked,
    lib_path,
    pin_tip,
    place_ground,
    place_part,
    place_wire,
    set_prop,
)

ANALOG = lib_path("pspice/analog.olb")
SOURCE = lib_path("pspice/source.olb")
BIPOLAR = lib_path("pspice/bipolar.olb")
BREAKOUT = lib_path("pspice/breakout.olb")

# Measured after PlacePart Q2N3904 (rot0); update if probe differs.
# Typical Capture NPN: C top, B left, E bottom relative to origin.
_DEFAULT_Q = {
    "c": [0.2, 0.0],
    "b": [-0.1, 0.2],
    "e": [0.2, 0.4],
}


def q_offsets() -> dict[str, list[float]]:
    offsets = json.loads((ROOT / "pin_offsets.json").read_text(encoding="utf-8"))
    libs = offsets.setdefault("libraries", {})
    bip = libs.setdefault("pspice/bipolar.olb", {})
    return bip.setdefault("Q2N3904", dict(_DEFAULT_Q))


def q_tip(origin: tuple[float, float], pin: str) -> tuple[float, float]:
    ox, oy = origin
    dx, dy = q_offsets()[pin]
    return (ox + dx, oy + dy)


def _set_ref_value(ref: str, value: str | None = None, extra: dict[str, str] | None = None) -> list[str]:
    cmds = [set_prop(ref, "Reference", ref)]
    if value is not None:
        cmds.append(set_prop(ref, "VALUE", value))
    if extra:
        for k, v in extra.items():
            cmds.append(set_prop(ref, k, v))
    return cmds


def fig5_cmds(
    origin: tuple[float, float] = (1.0, 2.0),
    *,
    label: str = "Fig5 CE amp (Q2N3904)",
    with_load: bool = False,
) -> list[str]:
    """Common-emitter amp per Lab9 Fig5 (+ optional Fig6 load).

    Uses single VSIN (VOFF=330mV, VAMP=10mV, FREQ=1kHz) as lab §6.1 step 2.
    """
    ox, oy = origin
    q = (ox + 2.4, oy + 1.0)
    vsin = (ox + 0.6, oy + 1.0)
    rc = (ox + 2.2, oy + 0.1)
    vcc = (ox + 3.6, oy + 0.0)
    cmds: list[str] = [
        f'PlaceText {ox:.2f} {oy - 0.45:.2f} {ox + 4.5:.2f} {oy - 0.20:.2f} "{label}"',
        place_part(*q, BIPOLAR, "Q2N3904"),
        place_part(*vsin, SOURCE, "VSIN"),
        place_part(*rc, ANALOG, "R"),
        place_part(*vcc, SOURCE, "VDC"),
    ]

    qb, qc, qe = q_tip(q, "b"), q_tip(q, "c"), q_tip(q, "e")
    vs_p = pin_tip(vsin, "pspice/source.olb", "VSIN", "+")
    vs_m = pin_tip(vsin, "pspice/source.olb", "VSIN", "-")
    rc1 = pin_tip(rc, "pspice/analog.olb", "R", "1")
    rc2 = pin_tip(rc, "pspice/analog.olb", "R", "2")
    vcc_p = pin_tip(vcc, "pspice/source.olb", "VDC", "+")
    vcc_m = pin_tip(vcc, "pspice/source.olb", "VDC", "-")

    # Wire: VSIN+ -> base; RC between collector and VCC+; emitter/VSIN-/VCC- to gnd
    cmds += [
        place_wire(*vs_p, *qb),
        place_wire(qc[0], qc[1], rc1[0], qc[1]),
        place_wire(rc1[0], qc[1], *rc1),
        place_wire(*rc2, *vcc_p),
        place_wire(vcc_p[0], vcc_p[1], vcc_p[0], rc2[1]) if abs(vcc_p[1] - rc2[1]) > 0.01 else "expr 1",
    ]

    # Grounds: under VSIN-, under emitter, under VCC-
    g_vs = (vs_m[0] - 0.1, vs_m[1] + 0.8)
    g_e = (qe[0] - 0.1, qe[1] + 0.5)
    g_vcc = (vcc_m[0] - 0.1, vcc_m[1] + 0.5)
    cmds += [
        place_ground(*g_vs),
        place_ground(*g_e),
        place_ground(*g_vcc),
        place_wire(*vs_m, vs_m[0], g_vs[1]),
        place_wire(*qe, qe[0], g_e[1]),
        place_wire(*vcc_m, vcc_m[0], g_vcc[1]),
        f"PlaceNetAlias {qb[0] - 0.3:.2f} {qb[1] - 0.15:.2f} VIN",
        f"PlaceNetAlias {qc[0] + 0.15:.2f} {qc[1] - 0.15:.2f} VOUT",
        f"PlaceNetAlias {vcc_p[0] + 0.15:.2f} {vcc_p[1] - 0.15:.2f} VCC",
    ]

    if with_load:
        # Fig6: C from collector, RL to ground
        c = (ox + 4.8, oy + 0.9)
        rl = (ox + 5.8, oy + 1.0)
        cmds += [
            place_part(*c, ANALOG, "C"),
            place_part(*rl, ANALOG, "R"),
        ]
        c1 = pin_tip(c, "pspice/analog.olb", "C", "1")
        c2 = pin_tip(c, "pspice/analog.olb", "C", "2")
        rl1 = pin_tip(rl, "pspice/analog.olb", "R", "1")
        rl2 = pin_tip(rl, "pspice/analog.olb", "R", "2")
        g_rl = (rl2[0] - 0.1 + 0.4, rl2[1] + 0.8)  # will fix after measure
        # Wire collector to C1, C2 to RL1, RL2 down to ground
        cmds += [
            place_wire(*qc, qc[0], c1[1]),
            place_wire(qc[0], c1[1], *c1),
            place_wire(*c2, *rl1),
            place_ground(rl2[0] - 0.1, rl2[1] + 0.7),
            place_wire(*rl2, rl2[0], rl2[1] + 0.7),
            f"PlaceNetAlias {rl1[0] + 0.1:.2f} {rl1[1] - 0.15:.2f} VOUTL",
        ]

    return [c for c in cmds if c != "expr 1"]


def topology_fig1(ox: float = 1.0, oy: float = 5.5) -> list[str]:
    """Fig1 CE stage sketch — QbreakN + Vin + Rc + Vcc."""
    q = (ox + 2.0, oy + 1.0)
    return [
        f'PlaceText {ox:.2f} {oy - 0.35:.2f} {ox + 3.5:.2f} {oy - 0.10:.2f} "Fig1 CE stage"',
        place_part(*q, BREAKOUT, "QbreakN"),
        place_part(ox + 0.5, oy + 1.0, SOURCE, "VAC"),
        place_part(ox + 1.8, oy + 0.1, ANALOG, "R"),
        place_part(ox + 3.2, oy + 0.0, SOURCE, "VDC"),
    ]


def main() -> None:
    # Print Fig5 place-only batch for interactive use
    cmds = fig5_cmds((1.0, 2.0), label="Fig5 CE amp Lab9", with_load=False)
    cmds += fig5_cmds((7.0, 2.0), label="Fig6 CE + load Lab9", with_load=True)
    for i, batch in enumerate(chunked(cmds, 6)):
        print(f"--- batch {i} ---")
        for c in batch:
            print(c)


if __name__ == "__main__":
    main()
