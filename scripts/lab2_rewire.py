"""Fix Lab2 wiring: move supplies clear, delete all wires, rewire cleanly.

Lesson (2026-07-20): wires that PASS THROUGH another pin hotspot connect to it.
Original routes crossed VDC '-' pins and R1 pin2, shorting nets to ground.
New routes only touch pin tips at wire ENDPOINTS.
"""
from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from placement_lib import (  # noqa: E402
    ground_at_hotspot,
    place_alias,
    place_wire,
    save_cmd,
    set_location,
    set_props_at_xy,
)


def tcl(cmd: str, timeout: float = 20.0) -> str:
    s = socket.create_connection(("127.0.0.1", 9020), timeout=5)
    s.settimeout(timeout)
    if not cmd.endswith("\n"):
        cmd += "\n"
    s.sendall(cmd.encode())
    data = s.recv(65536)
    s.close()
    return data.decode("utf-8", "replace").strip()


DEL_WIRE = (
    "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
    "set wIter [$lPage NewWiresIter $lStatus]; set w [$wIter NextWire $lStatus]; "
    "delete_DboPageWiresIter $wIter; "
    "if {$w != $lNullObj} { $lPage DeleteWire $w; return dw } else { return none }"
)


def clear_wires() -> None:
    for i in range(120):
        r = tcl(DEL_WIRE)
        if r == "none":
            print("wires cleared at", i)
            break
        time.sleep(0.25)
        if i % 6 == 5:
            tcl(save_cmd())
            time.sleep(0.3)
    tcl(save_cmd())


# --- pin tips (current placements) -------------------------------------------
# Non-inverting:  U1(2.6,1.6) VAC VIN(1.0,1.7) R1(1.7,2.7) R2(2.7,1.0) RL(3.9,1.7)
# Inverting:      U2(7.3,1.6) VAC VIN2(5.5,2.1) R3(6.2,2.1) R4(7.4,1.0) RL2(8.6,1.7)
# Supplies moved: VDD(4.6,0.6) VSS(4.6,2.6) VDD2(9.3,0.6) VSS2(9.3,2.6)

WIRES: list[tuple[float, float, float, float]] = [
    # --- non-inverting ---
    # VIN+ -> U1+
    (1.1, 1.6, 1.1, 1.7), (1.1, 1.7, 2.5, 1.7),
    # U1- -> R1 pin2 (down then left, endpoint at pin)
    (2.5, 2.1, 2.5, 2.8), (2.5, 2.8, 2.0, 2.8),
    # R2 pin1 -> U1-  (left at y=1.1, down at x=2.2, right into pin)
    (2.6, 1.1, 2.2, 1.1), (2.2, 1.1, 2.2, 2.1), (2.2, 2.1, 2.5, 2.1),
    # OUT -> R2 pin2
    (3.3, 1.9, 3.3, 1.1), (3.3, 1.1, 3.0, 1.1),
    # OUT -> RL pin1
    (3.3, 1.9, 3.3, 1.8), (3.3, 1.8, 3.8, 1.8),
    # VDD+ -> U1 V+
    (4.7, 0.6, 2.9, 0.6), (2.9, 0.6, 2.9, 1.6),
    # VSS- -> U1 V-
    (4.7, 3.0, 2.9, 3.0), (2.9, 3.0, 2.9, 2.2),
    # --- inverting ---
    # VIN2+ -> R3 pin1
    (5.6, 2.0, 5.6, 2.2), (5.6, 2.2, 6.1, 2.2),
    # R3 pin2 -> U2-
    (6.5, 2.2, 6.5, 2.1), (6.5, 2.1, 7.2, 2.1),
    # R4 pin1 -> U2- (left, down at x=6.9, right into pin)
    (7.3, 1.1, 6.9, 1.1), (6.9, 1.1, 6.9, 2.1), (6.9, 2.1, 7.2, 2.1),
    # OUT2 -> R4 pin2
    (8.0, 1.9, 8.0, 1.1), (8.0, 1.1, 7.7, 1.1),
    # OUT2 -> RL2 pin1
    (8.0, 1.9, 8.0, 1.8), (8.0, 1.8, 8.5, 1.8),
    # VDD2+ -> U2 V+
    (9.4, 0.6, 7.6, 0.6), (7.6, 0.6, 7.6, 1.6),
    # VSS2- -> U2 V-
    (9.4, 3.0, 7.6, 3.0), (7.6, 3.0, 7.6, 2.2),
    # U2+ -> ground (sideways at x=6.7 to avoid crossing U2- tip)
    (7.2, 1.7, 6.7, 1.7), (6.7, 1.7, 6.7, 2.9),
]

# ground hotspot positions + the wire dropping into each
GROUNDS: list[tuple[float, float, float, float]] = [
    # (pin_x, pin_y, hs_x, hs_y) — wire from pin/corner straight down into hotspot
    (1.1, 2.0, 1.1, 2.6),    # VIN-   (gnd exists already at 1.1,2.6 — rewire only)
    (1.6, 2.8, 1.6, 3.4),    # R1 pin1
    (4.2, 1.8, 4.2, 2.4),    # RL pin2 (gnd exists)
    (4.7, 1.0, 4.7, 1.6),    # VDD-
    (5.2, 2.6, 5.2, 3.2),    # VSS+ via sideways stub (below)
    (5.6, 2.4, 5.6, 3.0),    # VIN2-  (gnd exists)
    (6.7, 2.9, 6.7, 2.9),    # U2+ stub already ends at 6.7,2.9 (gnd only)
    (8.9, 1.8, 8.9, 2.4),    # RL2 pin2 (gnd exists)
    (9.4, 1.0, 9.4, 1.6),    # VDD2-
    (9.9, 2.6, 9.9, 3.2),    # VSS2+ via sideways stub (below)
]

# sideways stubs for VDC '+' pins that must reach ground without crossing '-'
STUBS: list[tuple[float, float, float, float]] = [
    (4.7, 2.6, 5.2, 2.6),    # VSS+ right
    (9.4, 2.6, 9.9, 2.6),    # VSS2+ right
]

EXISTING_GNDS = {(1.1, 2.6), (4.2, 2.4), (5.6, 3.0), (8.9, 2.4)}


def main() -> int:
    print("ping:", tcl("expr 1"))

    # 1. move supplies out of the wiring corridors
    for ref, x, y in (("VDD", 4.6, 0.6), ("VSS", 4.6, 2.6),
                      ("VDD2", 9.3, 0.6), ("VSS2", 9.3, 2.6)):
        print("move", ref, tcl(set_location(ref, x, y)))
        time.sleep(0.4)
        tcl(save_cmd())
        time.sleep(0.3)

    # 2. delete all wires
    clear_wires()

    # 3. stubs then grounds then drops
    for x1, y1, x2, y2 in STUBS:
        print("stub", tcl(place_wire(x1, y1, x2, y2)))
        time.sleep(0.25)

    for px, py, hx, hy in GROUNDS:
        if (hx, hy) not in EXISTING_GNDS:
            print("gnd", hx, hy, tcl(ground_at_hotspot(hx, hy)))
            time.sleep(0.4)
        if (px, py) != (hx, hy):
            print("drop", tcl(place_wire(px, py, hx, hy)))
            time.sleep(0.25)
    tcl(save_cmd())

    # 4. signal wires
    for i, (x1, y1, x2, y2) in enumerate(WIRES):
        print("wire", i, tcl(place_wire(x1, y1, x2, y2)))
        time.sleep(0.25)
        if i % 6 == 5:
            tcl(save_cmd())
            time.sleep(0.3)

    # 5. aliases exactly ON wire segments
    for x, y, name in ((1.5, 1.7, "VIN"), (3.5, 1.8, "VOUT"),
                       (5.8, 2.2, "VIN2"), (8.2, 1.8, "VOUT2")):
        print("alias", name, tcl(place_alias(x, y, name)))
        time.sleep(0.25)

    # 6. supply DC values (VDC netlists its DC prop, not VALUE)
    for x, y, ref in ((4.6, 0.6, "VDD"), (4.6, 2.6, "VSS"),
                      (9.3, 0.6, "VDD2"), (9.3, 2.6, "VSS2")):
        print("prop", ref, tcl(set_props_at_xy(x, y, {"DC": "15Vdc", "VALUE": "15Vdc"})))
        time.sleep(0.3)

    tcl(save_cmd())
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
