"""Atomic dump of the active Capture page, then draw a schematic PNG."""
from __future__ import annotations

import socket
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle
from matplotlib.lines import Line2D


def tcl(cmd: str, timeout: float = 30.0) -> str:
    s = socket.create_connection(("127.0.0.1", 9020), timeout=8)
    s.settimeout(timeout)
    payload = cmd if cmd.endswith("\n") else cmd + "\n"
    s.sendall(payload.encode("utf-8"))
    s.settimeout(2.5)
    chunks: list[bytes] = []
    try:
        while True:
            data = s.recv(65536)
            if not data:
                break
            chunks.append(data)
    except socket.timeout:
        pass
    s.close()
    return b"".join(chunks).decode("utf-8", "replace").strip()


DUMP = (
    "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
    "set pnm [DboTclHelper_sMakeCString]; catch {$lPage GetName $pnm}; "
    "set parts {}; set pins {}; "
    "set lIter [$lPage NewPartInstsIter $lStatus]; "
    "set lInst [$lIter NextPartInst $lStatus]; "
    "while {$lInst != $lNullObj} { "
    "set ref [DboTclHelper_sMakeCString]; $lInst GetReference $ref; "
    "set pv [DboTclHelper_sMakeCString]; catch {$lInst GetPartValue $pv}; "
    "set loc [$lInst GetLocation $lStatus]; "
    "set ox [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
    "set oy [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
    "set rot [$lInst GetRotation $lStatus]; "
    "set lPlaced [DboPartInstToDboPlacedInst $lInst]; "
    "set spn [DboTclHelper_sMakeCString]; catch {$lPlaced GetSourcePartName $spn}; "
    "set rs [DboTclHelper_sGetConstCharPtr $ref]; "
    "lappend parts \"$rs,[DboTclHelper_sGetConstCharPtr $pv],[DboTclHelper_sGetConstCharPtr $spn],$ox,$oy,$rot\"; "
    "if {$lPlaced != $lNullObj} { "
    "set lPinIter [$lPlaced NewPinsIter $lStatus]; set lPin [$lPinIter NextPin $lStatus]; "
    "while {$lPin != $lNullObj} { "
    "set pn [DboTclHelper_sMakeCString]; $lPin GetPinName $pn; "
    "set num [DboTclHelper_sMakeCString]; $lPin GetPinNumber $num; "
    "set hs [$lPin GetOffsetHotSpot $lStatus]; "
    "set hx [expr {[DboTclHelper_sGetCPointX $hs]/100.0}]; "
    "set hy [expr {[DboTclHelper_sGetCPointY $hs]/100.0}]; "
    "lappend pins \"$rs,[DboTclHelper_sGetConstCharPtr $pn],[DboTclHelper_sGetConstCharPtr $num],$hx,$hy\"; "
    "set lPin [$lPinIter NextPin $lStatus] }; delete_DboPartInstPinsIter $lPinIter }; "
    "set lInst [$lIter NextPartInst $lStatus] }; "
    "delete_DboPagePartInstsIter $lIter; "
    "set wires {}; set wIter [$lPage NewWiresIter $lStatus]; "
    "set w [$wIter NextWire $lStatus]; "
    "while {$w != $lNullObj} { "
    "set sx -1; set sy -1; set ex -1; set ey -1; "
    "catch {set sp [$w GetStartPoint $lStatus]; set sx [expr {[DboTclHelper_sGetCPointX $sp]/100.0}]; set sy [expr {[DboTclHelper_sGetCPointY $sp]/100.0}]}; "
    "catch {set ep [$w GetEndPoint $lStatus]; set ex [expr {[DboTclHelper_sGetCPointX $ep]/100.0}]; set ey [expr {[DboTclHelper_sGetCPointY $ep]/100.0}]}; "
    "lappend wires \"$sx,$sy,$ex,$ey\"; "
    "set w [$wIter NextWire $lStatus] }; "
    "delete_DboPageWiresIter $wIter; "
    "set globs {}; set gIter [$lPage NewGlobalsIter $lStatus]; "
    "set g [$gIter NextGlobal $lStatus]; "
    "while {$g != $lNullObj} { "
    "set nm [DboTclHelper_sMakeCString]; catch {$g GetName $nm}; "
    "set loc [$g GetLocation $lStatus]; "
    "set ox [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
    "set oy [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
    "lappend globs \"[DboTclHelper_sGetConstCharPtr $nm],$ox,$oy\"; "
    "set g [$gIter NextGlobal $lStatus] }; "
    "delete_DboPageGlobalsIter $gIter; "
    "return \"PAGE=[DboTclHelper_sGetConstCharPtr $pnm]\\nPARTS=[join $parts {;}]\\nPINS=[join $pins {;}]\\nWIRES=[join $wires {;}]\\nGLOBS=[join $globs {;}]\""
)


def parse(raw: str):
    sections: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            sections[k] = v
    parts = []
    for item in sections.get("PARTS", "").split(";"):
        if not item:
            continue
        ref, val, spn, x, y, rot = item.split(",")
        parts.append(
            {
                "ref": ref,
                "val": val,
                "spn": spn,
                "x": float(x),
                "y": float(y),
                "rot": int(float(rot)),
            }
        )
    pins = []
    for item in sections.get("PINS", "").split(";"):
        if not item:
            continue
        ref, name, num, x, y = item.split(",")
        pins.append(
            {
                "ref": ref,
                "name": name,
                "num": num,
                "x": float(x),
                "y": float(y),
            }
        )
    wires = []
    for item in sections.get("WIRES", "").split(";"):
        if not item:
            continue
        sx, sy, ex, ey = item.split(",")
        wires.append((float(sx), float(sy), float(ex), float(ey)))
    globs = []
    for item in sections.get("GLOBS", "").split(";"):
        if not item:
            continue
        name, x, y = item.split(",")
        globs.append({"name": name, "x": float(x), "y": float(y)})
    return sections.get("PAGE", "?"), parts, pins, wires, globs


def draw_resistor(ax, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5 or 0.01
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    n = 6
    pts = [(x1, y1)]
    for i in range(1, n):
        t = i / n
        amp = 0.06 if i % 2 else -0.06
        pts.append((x1 + ux * t * length + px * amp, y1 + uy * t * length + py * amp))
    pts.append((x2, y2))
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color="#1a1a1a", lw=1.4, solid_capstyle="round")


def draw_cap(ax, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5 or 0.01
    ux, uy = dx / length, dy / length
    px, py = -uy * 0.12, ux * 0.12
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    gap = 0.04
    ax.plot([x1, mx - ux * gap], [y1, my - uy * gap], color="#1a1a1a", lw=1.3)
    ax.plot([mx + ux * gap, x2], [my + uy * gap, y2], color="#1a1a1a", lw=1.3)
    ax.plot(
        [mx - ux * gap + px, mx - ux * gap - px],
        [my - uy * gap + py, my - uy * gap - py],
        color="#1a1a1a",
        lw=1.8,
    )
    ax.plot(
        [mx + ux * gap + px, mx + ux * gap - px],
        [my + uy * gap + py, my + uy * gap - py],
        color="#1a1a1a",
        lw=1.8,
    )


def draw_opamp(ax, part, pins):
    own = [p for p in pins if p["ref"] == part["ref"]]
    by = {p["name"]: p for p in own}
    plus = by.get("+")
    minus = by.get("-")
    out = by.get("OUT")
    if not (plus and minus and out):
        return
    left_x = plus["x"]
    mid_y = (plus["y"] + minus["y"]) / 2
    right_x = out["x"]
    top = min(plus["y"], minus["y"]) - 0.15
    bot = max(plus["y"], minus["y"]) + 0.15
    tri = [(left_x, top), (left_x, bot), (right_x, mid_y)]
    ax.add_patch(Polygon(tri, closed=True, fill=False, ec="#1a1a1a", lw=1.5))
    ax.text(plus["x"] + 0.08, plus["y"], "+", fontsize=8, va="center", color="#1a1a1a")
    ax.text(minus["x"] + 0.08, minus["y"], "\u2212", fontsize=8, va="center", color="#1a1a1a")
    ax.plot([out["x"], out["x"]], [out["y"], mid_y], color="#1a1a1a", lw=1.2)
    ax.text(
        (left_x + right_x) / 2 + 0.05,
        mid_y,
        part["ref"],
        fontsize=8,
        ha="center",
        va="center",
        color="#1a1a1a",
        fontweight="bold",
    )
    ax.text(
        (left_x + right_x) / 2 + 0.05,
        bot + 0.12,
        part["val"],
        fontsize=7,
        ha="center",
        va="top",
        color="#333",
    )


def draw_source(ax, part, pins):
    own = [p for p in pins if p["ref"] == part["ref"]]
    if len(own) >= 2:
        ys = [p["y"] for p in own]
        xs = [p["x"] for p in own]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        r = max(0.18, (max(ys) - min(ys)) / 2 + 0.02)
    else:
        cx, cy, r = part["x"] + 0.1, part["y"] + 0.4, 0.22
    circ = Circle((cx, cy), r, fill=False, ec="#1a1a1a", lw=1.5)
    ax.add_patch(circ)
    extra = {
        "V4": "1 Vac",
        "V5": "1 Vpk  3 kHz",
        "V6": "+15 V",
        "V7": "15 V",
    }.get(part["ref"], part["val"])
    glyph = "~" if part["val"] in {"VAC", "VSIN"} else "+"
    ax.text(cx, cy, glyph, fontsize=11, ha="center", va="center", color="#1a1a1a")
    ax.text(cx + r + 0.10, cy, f"{part['ref']}  {extra}", fontsize=7, va="center", color="#1a1a1a")
    for p in own:
        ax.plot([p["x"], cx], [p["y"], p["y"]], color="#1a1a1a", lw=1.1)
        ax.text(p["x"] - 0.08, p["y"], p["name"], fontsize=6, ha="right", va="center")


def draw_gnd(ax, x, y, label):
    ax.plot([x, x], [y - 0.12, y], color="#1a1a1a", lw=1.2)
    ax.plot([x - 0.12, x + 0.12], [y, y], color="#1a1a1a", lw=1.6)
    ax.plot([x - 0.08, x + 0.08], [y + 0.05, y + 0.05], color="#1a1a1a", lw=1.3)
    ax.plot([x - 0.04, x + 0.04], [y + 0.10, y + 0.10], color="#1a1a1a", lw=1.1)
    ax.text(x + 0.16, y, label, fontsize=7, va="center", color="#1a1a1a")


def main() -> None:
    raw = tcl(DUMP)
    out_txt = Path(r"C:\Users\lance\tcl-mcp-server\scripts\page_dump.txt")
    out_txt.write_text(raw, encoding="utf-8")
    print(raw[:4000])
    print("\n---END RAW---")
    page, parts, pins, wires, globs = parse(raw)
    print(f"page={page} parts={len(parts)} pins={len(pins)} wires={len(wires)} globs={len(globs)}")

    fig, ax = plt.subplots(figsize=(14.5, 8.2), dpi=140)
    fig.patch.set_facecolor("#f7f4ea")
    ax.set_facecolor("#f7f4ea")

    for sx, sy, ex, ey in wires:
        ax.plot([sx, ex], [sy, ey], color="#2b4c7e", lw=1.15, zorder=1)
        ax.plot([sx], [sy], "o", ms=2.4, color="#2b4c7e", zorder=2)
        ax.plot([ex], [ey], "o", ms=2.4, color="#2b4c7e", zorder=2)

    pins_by_ref: dict[str, list] = {}
    for p in pins:
        pins_by_ref.setdefault(p["ref"], []).append(p)

    for part in parts:
        ref = part["ref"]
        own = pins_by_ref.get(ref, [])
        kind = part["spn"].split(".")[0]
        if ref.startswith("U") or "LT" in part["val"] or kind.startswith("LT"):
            draw_opamp(ax, part, pins)
        elif ref.startswith("V") or kind in {"VAC", "VSIN", "VSFFM", "VDC"}:
            draw_source(ax, part, pins)
        elif ref.startswith("R") or kind == "R":
            if len(own) >= 2:
                draw_resistor(ax, own[0]["x"], own[0]["y"], own[1]["x"], own[1]["y"])
            mid_x = sum(p["x"] for p in own) / max(len(own), 1)
            mid_y = sum(p["y"] for p in own) / max(len(own), 1)
            ax.text(mid_x, mid_y - 0.16, f"{ref} {part['val']}", fontsize=7.5, ha="center", color="#1a1a1a")
        elif ref.startswith("C") or kind == "C":
            if len(own) >= 2:
                draw_cap(ax, own[0]["x"], own[0]["y"], own[1]["x"], own[1]["y"])
            mid_x = sum(p["x"] for p in own) / max(len(own), 1)
            mid_y = sum(p["y"] for p in own) / max(len(own), 1)
            ax.text(mid_x + 0.18, mid_y, f"{ref} {part['val']}", fontsize=7.5, va="center", color="#1a1a1a")
        else:
            ax.plot(part["x"], part["y"], "s", color="#444")
            ax.text(part["x"], part["y"] - 0.12, f"{ref} {part['val']}", fontsize=7)

        for p in own:
            ax.plot(p["x"], p["y"], "o", ms=3.2, color="#111", zorder=3)

    for g in globs:
        draw_gnd(ax, g["x"], g["y"], g["name"])

    ax.set_aspect("equal")
    ax.invert_yaxis()
    ax.set_xlim(0.3, 9.6)
    ax.set_ylim(5.55, 0.55)
    ax.set_title(
        f"OrCAD Capture {page}  —  5th-order Sallen-Key LPF (live Tcl dump)",
        fontsize=13,
        pad=10,
        color="#1a1a1a",
    )
    ax.set_xlabel("X (inches)")
    ax.set_ylabel("Y (inches)")
    for spine in ax.spines.values():
        spine.set_color("#c9c4b5")
    ax.tick_params(colors="#555")
    ax.grid(True, color="#e0dbc8", lw=0.6)
    fig.tight_layout()
    out_png = Path(r"C:\Users\lance\tcl-mcp-server\scripts\capture_page1.png")
    fig.savefig(out_png, dpi=140)
    print("WROTE", out_png)


if __name__ == "__main__":
    main()
