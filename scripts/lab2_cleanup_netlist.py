"""Delete old Lab3/Lab9 leftover parts (y>7) one at a time, then save.

Leftovers: 4x D? 1N4007, V4 VSIN, RL=10k — all at y>=7.4 on PAGE1.
Also clears wires whose both endpoints are at y>6.9 (old circuits area).
"""
import socket
import time


def tcl(cmd: str, timeout: float = 15.0) -> str:
    s = socket.create_connection(("127.0.0.1", 9020), timeout=5)
    s.settimeout(timeout)
    if not cmd.endswith("\n"):
        cmd += "\n"
    s.sendall(cmd.encode())
    data = s.recv(65536)
    s.close()
    return data.decode("utf-8", "replace").strip()


DEL_PART_YMIN = (
    "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
    "set lIter [$lPage NewPartInstsIter $lStatus]; set victim NULL; "
    "set lInst [$lIter NextPartInst $lStatus]; "
    "while {$lInst != $lNullObj} { "
    "set loc [$lInst GetLocation $lStatus]; "
    "set oy [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
    "if {$oy > 6.9} { set victim $lInst }; "
    "set lInst [$lIter NextPartInst $lStatus] }; "
    "delete_DboPagePartInstsIter $lIter; "
    "if {$victim != $lNullObj} { $lPage DeletePartInst $victim; return deleted } "
    "else { return none }"
)

for i in range(12):
    r = tcl(DEL_PART_YMIN)
    print("part del", i, r)
    time.sleep(0.5)
    tcl("Menu {File::Save}")
    time.sleep(0.3)
    if r == "none":
        break

print("save:", tcl("Menu {File::Save}"))
