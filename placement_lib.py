"""Helpers to build Capture Tcl place/wire command lists quickly.

Use with MCP execute_tcl_batch so placement is one MCP call, many PlaceParts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

_ROOT = Path(__file__).resolve().parent
_OFFSETS = json.loads((_ROOT / "pin_offsets.json").read_text(encoding="utf-8"))

CADENCE_CAPTURE_LIB = "C:/Cadence/OrCADX_25.1/tools/capture/library"


def lib_path(*parts: str) -> str:
    return "/".join((CADENCE_CAPTURE_LIB, *parts))


def pin_tip(origin: tuple[float, float], lib_key: str, part: str, pin: str) -> tuple[float, float]:
    """Return absolute inch coords of a pin tip from cached offsets."""
    ox, oy = origin
    dx, dy = _OFFSETS["libraries"][lib_key][part][pin]
    return (ox + dx, oy + dy)


def place_part(x: float, y: float, olb: str, part: str, device: str = "") -> str:
    return f'PlacePart {x:.2f} {y:.2f} "{olb}" "{part}" "{device}" FALSE'


def place_ground(x: float, y: float) -> str:
    """Place PSpice ground 0. Pass place origin so hotspot lands on desired wire X.

    hotspot ≈ (x+0.1, y); to land hs at (hx, hy), place at (hx-0.1, hy).
    """
    olb = lib_path("capsym.olb")
    return f'PlaceGround {x:.2f} {y:.2f} "{olb}" "0" "0"'


def place_wire(x1: float, y1: float, x2: float, y2: float) -> str:
    return f"PlaceWire {x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f}"


def set_prop(ref_match: str, name: str, value: str) -> str:
    """Short Tcl to set one effective prop on the first ref matching glob (e.g. R?)."""
    return (
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set lIter [$lPage NewPartInstsIter $lStatus]; set t NULL; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { "
        "set ref [DboTclHelper_sMakeCString]; $lInst GetReference $ref; "
        f"if {{[string match {{{ref_match}}} [DboTclHelper_sGetConstCharPtr $ref]]}} "
        "{{ set t $lInst }}; "
        "set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; "
        f"set n [DboTclHelper_sMakeCString {{{name}}}]; "
        f"set v [DboTclHelper_sMakeCString {{{value}}}]; "
        "$t SetEffectivePropStringValue $n $v; expr 1"
    )


def build_series_rlc(
    r_xy: tuple[float, float] = (2.5, 3.0),
    l_xy: tuple[float, float] = (4.0, 3.0),
    c_xy: tuple[float, float] = (5.5, 3.0),
) -> list[str]:
    """Example: ordered PlacePart/PlaceWire list using cached R/L/C offsets."""
    analog = lib_path("pspice/analog.olb")
    cmds = [
        place_part(*r_xy, analog, "R"),
        place_part(*l_xy, analog, "L"),
        place_part(*c_xy, analog, "C"),
    ]
    r1 = pin_tip(r_xy, "pspice/analog.olb", "R", "1")
    r2 = pin_tip(r_xy, "pspice/analog.olb", "R", "2")
    l1 = pin_tip(l_xy, "pspice/analog.olb", "L", "1")
    l2 = pin_tip(l_xy, "pspice/analog.olb", "L", "2")
    c1 = pin_tip(c_xy, "pspice/analog.olb", "C", "1")
    c2 = pin_tip(c_xy, "pspice/analog.olb", "C", "2")
    cmds.extend(
        [
            place_wire(*r2, *l1),
            place_wire(*l2, *c1),
        ]
    )
    # Unused tips kept for callers extending the list
    _ = (r1, c2)
    return cmds


def chunked(commands: Sequence[str], size: int = 8) -> list[list[str]]:
    """Split a long place list into safer MCP batch sizes."""
    return [list(commands[i : i + size]) for i in range(0, len(commands), size)]
