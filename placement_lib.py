"""Capture Tcl placement helpers + parts catalog.

Reads:
  pin_offsets.json  — pin hotspot geometry (inches, rot0)
  parts_catalog.json — OLB paths, props, crash rules, recipes, safe page bounds

Build command lists locally, then send via MCP execute_tcl / execute_tcl_batch
with catalog-recommended delays and batch sizes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Sequence

_ROOT = Path(__file__).resolve().parent
_OFFSETS = json.loads((_ROOT / "pin_offsets.json").read_text(encoding="utf-8"))
_CATALOG = json.loads((_ROOT / "parts_catalog.json").read_text(encoding="utf-8"))

CADENCE_CAPTURE_LIB = "C:/Cadence/OrCADX_25.1/tools/capture/library"


def reload_catalog() -> None:
    """Re-read JSON files (after measuring new pins mid-session)."""
    global _OFFSETS, _CATALOG
    _OFFSETS = json.loads((_ROOT / "pin_offsets.json").read_text(encoding="utf-8"))
    _CATALOG = json.loads((_ROOT / "parts_catalog.json").read_text(encoding="utf-8"))


def catalog() -> dict[str, Any]:
    return _CATALOG


def part_info(name: str) -> dict[str, Any]:
    """Lookup a catalog part by key (e.g. 'Q2N3904', 'VSIN', 'GND')."""
    parts = _CATALOG["parts"]
    if name not in parts:
        known = ", ".join(sorted(parts))
        raise KeyError(f"Unknown part {name!r}. Known: {known}")
    return parts[name]


def lib_path(*parts: str) -> str:
    return "/".join((CADENCE_CAPTURE_LIB, *parts))


def olb_for(part_key: str) -> str:
    info = part_info(part_key)
    return lib_path(info["olb"])


def pin_tip(origin: tuple[float, float], lib_key: str, part: str, pin: str) -> tuple[float, float]:
    """Absolute inch coords of a pin tip from cached offsets."""
    ox, oy = origin
    dx, dy = _OFFSETS["libraries"][lib_key][part][pin]
    return (ox + dx, oy + dy)


def pin_tip_catalog(origin: tuple[float, float], part_key: str, pin: str) -> tuple[float, float]:
    """pin_tip using catalog part key (resolves olb/symbol)."""
    info = part_info(part_key)
    return pin_tip(origin, info["olb"], info["symbol"], pin)


def assert_on_page(x: float, y: float, label: str = "") -> None:
    xmin, ymin, xmax, ymax = _CATALOG["page"]["safe_xy_inches"]
    if not (xmin <= x <= xmax and ymin <= y <= ymax):
        raise ValueError(
            f"Origin ({x}, {y}) {label} outside safe page "
            f"[{xmin},{ymin}]–[{xmax},{ymax}] — parts will be invisible / off-page"
        )


def place_part(x: float, y: float, olb: str, part: str, device: str = "", *, check_page: bool = True) -> str:
    if check_page:
        assert_on_page(x, y, f"{part}")
    return f'PlacePart {x:.2f} {y:.2f} "{olb}" "{part}" "{device}" FALSE'


def place_catalog_part(x: float, y: float, part_key: str, device: str = "") -> str:
    info = part_info(part_key)
    if info.get("place_cmd") == "PlaceGround":
        return place_ground(x, y)
    return place_part(x, y, olb_for(part_key), info["symbol"], device)


def place_ground(x: float, y: float, *, check_page: bool = True) -> str:
    """Place PSpice ground 0. Hotspot ≈ (x+0.1, y); wire down into hotspot."""
    if check_page:
        assert_on_page(x, y, "GND")
    olb = lib_path("capsym.olb")
    return f'PlaceGround {x:.2f} {y:.2f} "{olb}" "0" "0"'


def ground_at_hotspot(hx: float, hy: float) -> str:
    """Place ground so hotspot lands on (hx, hy)."""
    return place_ground(hx - 0.1, hy)


def place_wire(x1: float, y1: float, x2: float, y2: float) -> str:
    return f"PlaceWire {x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f}"


def place_alias(x: float, y: float, name: str) -> str:
    return f"PlaceNetAlias {x:.2f} {y:.2f} {name}"


def set_location(ref: str, x: float, y: float, *, check_page: bool = True) -> str:
    """Move existing part by exact Reference (DB units = inches*100). Save after moves!"""
    if check_page:
        assert_on_page(x, y, ref)
    xu, yu = int(round(x * 100)), int(round(y * 100))
    return (
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set lIter [$lPage NewPartInstsIter $lStatus]; set t NULL; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { "
        "set ref [DboTclHelper_sMakeCString]; $lInst GetReference $ref; "
        f"if {{[string equal [DboTclHelper_sGetConstCharPtr $ref] {ref}]}} {{set t $lInst}}; "
        "set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; "
        f"$t SetLocation [DboTclHelper_sMakeCPoint {xu} {yu}]; expr 1"
    )


def set_prop(ref_match: str, name: str, value: str) -> str:
    """Set one effective prop on first ref matching glob (e.g. R?, VIN)."""
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


def set_props_at_xy(x: float, y: float, props: dict[str, str], tol: float = 0.05) -> str:
    """Set props on the part whose origin is nearest (x,y) within tol."""
    assigns = " ".join(
        f"$t SetEffectivePropStringValue [DboTclHelper_sMakeCString {{{k}}}] "
        f"[DboTclHelper_sMakeCString {{{v}}}];"
        for k, v in props.items()
    )
    return (
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set lIter [$lPage NewPartInstsIter $lStatus]; set t NULL; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { "
        "set loc [$lInst GetLocation $lStatus]; "
        "set ox [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
        "set oy [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
        f"if {{abs($ox-{x})<{tol} && abs($oy-{y})<{tol}}} {{set t $lInst}}; "
        "set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; "
        f"{assigns} expr 1"
    )


def snippet(name: str) -> str:
    return _CATALOG["tcl_snippets"][name]


def save_cmd() -> str:
    return snippet("save")


def chunked(commands: Sequence[str], size: int | None = None, kind: str = "place") -> list[list[str]]:
    """Split commands using catalog-safe batch sizes."""
    mcp = _CATALOG["mcp"]
    if size is None:
        size = {
            "place": mcp["batch_max_place"],
            "wire": mcp["batch_max_wire"],
            "delete": mcp["batch_max_delete"],
        }.get(kind, 2)
    return [list(commands[i : i + size]) for i in range(0, len(commands), size)]


def mcp_delay_ms(kind: str = "place") -> int:
    return int(_CATALOG["mcp"].get(f"delay_ms_{kind}", 120))


def orthowire(a: tuple[float, float], b: tuple[float, float]) -> list[str]:
    """Manhattan path a→b (horizontal then vertical if needed)."""
    ax, ay = a
    bx, by = b
    if abs(ax - bx) < 1e-6 or abs(ay - by) < 1e-6:
        return [place_wire(ax, ay, bx, by)]
    mid = (ax, by)
    return [place_wire(ax, ay, *mid), place_wire(*mid, bx, by)]


def wire_down_to_ground(pin: tuple[float, float], hy: float | None = None) -> list[str]:
    """Place ground under pin and wire straight down into hotspot."""
    px, py = pin
    if hy is None:
        hy = py + 0.7
    cmds = [ground_at_hotspot(px, hy), place_wire(px, py, px, hy)]
    return cmds


# --- recipes -----------------------------------------------------------------


def build_series_rlc(
    r_xy: tuple[float, float] = (2.5, 3.0),
    l_xy: tuple[float, float] = (4.0, 3.0),
    c_xy: tuple[float, float] = (5.5, 3.0),
) -> list[str]:
    """Series R–L–C place+wire using cached offsets."""
    analog = lib_path("pspice/analog.olb")
    cmds = [
        place_part(*r_xy, analog, "R"),
        place_part(*l_xy, analog, "L"),
        place_part(*c_xy, analog, "C"),
    ]
    r2 = pin_tip(r_xy, "pspice/analog.olb", "R", "2")
    l1 = pin_tip(l_xy, "pspice/analog.olb", "L", "1")
    l2 = pin_tip(l_xy, "pspice/analog.olb", "L", "2")
    c1 = pin_tip(c_xy, "pspice/analog.olb", "C", "1")
    cmds.extend([place_wire(*r2, *l1), place_wire(*l2, *c1)])
    return cmds


def build_ce_amp_fig5(
    origin: tuple[float, float] = (1.2, 1.7),
    *,
    use_qbreak: bool = False,
) -> list[str]:
    """Lab9 Fig5 CE amp — place parts, wires, grounds, aliases.

    Prefer sending PlacePart cmds with batch_max_place=1 (Q2N3904 caution).
    """
    ox, oy = origin
    assert_on_page(ox, oy, "fig5 origin")

    q_key = "QbreakN" if use_qbreak else "Q2N3904"
    vsin = (ox + 0.0, oy + 1.3)
    q = (ox + 2.0, oy + 1.3)
    rc = (ox + 1.8, oy + 0.1)
    vcc = (ox + 3.3, oy + 0.0)

    for label, xy in (("VIN", vsin), ("Q1", q), ("RC", rc), ("VCC", vcc)):
        assert_on_page(*xy, label)

    cmds: list[str] = [
        place_catalog_part(*vsin, "VSIN"),
        place_catalog_part(*q, q_key),
        place_catalog_part(*rc, "R"),
        place_catalog_part(*vcc, "VDC"),
    ]

    qb = pin_tip_catalog(q, q_key, "b")
    qc = pin_tip_catalog(q, q_key, "c")
    qe = pin_tip_catalog(q, q_key, "e")
    vs_p = pin_tip_catalog(vsin, "VSIN", "+")
    vs_m = pin_tip_catalog(vsin, "VSIN", "-")
    rc1 = pin_tip_catalog(rc, "R", "1")
    rc2 = pin_tip_catalog(rc, "R", "2")
    vp = pin_tip_catalog(vcc, "VDC", "+")
    vm = pin_tip_catalog(vcc, "VDC", "-")

    cmds += orthowire(vs_p, qb)
    cmds += [place_wire(qc[0], qc[1], rc2[0], rc2[1])]
    cmds += orthowire(rc1, vp)
    cmds += wire_down_to_ground(vs_m)
    cmds += wire_down_to_ground(qe)
    cmds += wire_down_to_ground(vm, hy=vm[1] + 0.7)

    cmds += [
        place_alias(qb[0] - 0.5, qb[1] - 0.15, "VIN"),
        place_alias(qc[0] + 0.2, qc[1] - 0.15, "VOUT"),
        place_alias(vp[0] + 0.2, vp[1] - 0.15, "VCC"),
        set_props_at_xy(*rc, {"VALUE": "1k", "Reference": "RC"}),
        set_props_at_xy(*vcc, {"VALUE": "5V", "Reference": "VCC"}),
        set_props_at_xy(
            *vsin,
            {"VOFF": "330mV", "VAMPL": "10mV", "FREQ": "1kHz", "Reference": "VIN"},
        ),
        set_props_at_xy(*q, {"Reference": "Q1"}),
    ]
    if use_qbreak:
        cmds.append(set_props_at_xy(*q, {"MODEL": "Q2N3904"}))

    cmds.append(save_cmd())
    return cmds


def build_ce_amp_fig6(
    origin: tuple[float, float] = (6.5, 1.7),
    *,
    use_qbreak: bool = False,
) -> list[str]:
    """Lab9 Fig6 = Fig5 + C coupling + RL."""
    ox, oy = origin
    cmds = build_ce_amp_fig5(origin, use_qbreak=use_qbreak)
    # Strip trailing save; append load network then save once
    if cmds and cmds[-1] == save_cmd():
        cmds.pop()

    q_key = "QbreakN" if use_qbreak else "Q2N3904"
    q = (ox + 2.0, oy + 1.3)
    c = (ox + 3.8, oy + 1.1)
    rl = (ox + 5.1, oy + 1.2)
    assert_on_page(*c, "C1")
    assert_on_page(*rl, "RL")

    # Insert C/RL place after the four core places (indices 0..3)
    cmds[4:4] = [
        place_catalog_part(*c, "C"),
        place_catalog_part(*rl, "R"),
    ]

    qc = pin_tip_catalog(q, q_key, "c")
    c1 = pin_tip_catalog(c, "C", "1")
    c2 = pin_tip_catalog(c, "C", "2")
    rl1 = pin_tip_catalog(rl, "R", "1")
    rl2 = pin_tip_catalog(rl, "R", "2")

    cmds += orthowire(qc, c1)
    cmds += orthowire(c2, rl1)
    cmds += wire_down_to_ground(rl2)
    cmds += [
        place_alias(rl1[0], rl1[1] - 0.15, "VOUTL"),
        set_props_at_xy(*c, {"VALUE": "10u", "Reference": "C1"}),
        set_props_at_xy(*rl, {"VALUE": "10k", "Reference": "RL"}),
        save_cmd(),
    ]
    return cmds


def split_place_wire_prop(commands: Iterable[str]) -> dict[str, list[str]]:
    """Bucket commands so callers can send PlacePart at batch=1, wires at batch=3."""
    buckets: dict[str, list[str]] = {"place": [], "wire": [], "ground": [], "other": []}
    for c in commands:
        if c.startswith("PlacePart"):
            buckets["place"].append(c)
        elif c.startswith("PlaceGround"):
            buckets["ground"].append(c)
        elif c.startswith("PlaceWire"):
            buckets["wire"].append(c)
        else:
            buckets["other"].append(c)
    return buckets


def describe_part(name: str) -> str:
    """Human-readable how-to for agents / CLI."""
    info = part_info(name)
    lines = [
        f"{name}: {info.get('symbol')} @ {info.get('olb')}",
        f"  use: {info.get('use', '')}",
        f"  safe: {info.get('safe', '?')}",
    ]
    if "props" in info:
        lines.append(f"  default props: {info['props']}")
    if "danger" in info:
        lines.append(f"  danger: {info['danger']}")
    if "alt" in info:
        lines.append(f"  alt: {info['alt']}")
    lib = info.get("olb")
    sym = info.get("symbol")
    if lib and sym and lib in _OFFSETS.get("libraries", {}) and sym in _OFFSETS["libraries"][lib]:
        lines.append(f"  pins: {_OFFSETS['libraries'][lib][sym]}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        print(describe_part(sys.argv[1]))
    else:
        print("Parts:", ", ".join(sorted(_CATALOG["parts"])))
        print("Recipes:", ", ".join(sorted(_CATALOG["recipes"])))
        print("Safe page:", _CATALOG["page"]["safe_xy_inches"])
