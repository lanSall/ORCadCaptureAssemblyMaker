import socket
import time


def tcl(cmd: str) -> str:
    s = socket.socket(socket.AF_INET6)
    s.settimeout(15)
    s.connect(("::1", 9020))
    if not cmd.endswith("\n"):
        cmd += "\n"
    s.sendall(cmd.encode())
    data = b""
    s.settimeout(2)
    try:
        while True:
            c = s.recv(65536)
            if not c:
                break
            data += c
    except socket.timeout:
        pass
    s.close()
    return data.decode("utf-8", "replace").strip()


DEL = (
    "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
    "set wIter [$lPage NewWiresIter $lStatus]; set w [$wIter NextWire $lStatus]; "
    "delete_DboPageWiresIter $wIter; if {$w != $lNullObj} { $lPage DeleteWire $w; return dw } else { return none }"
)

for i in range(60):
    r = tcl(DEL)
    if "none" in r:
        print("wires done at", i)
        break
    if i % 10 == 0:
        print(i, r)
    time.sleep(0.05)

print("parts:", tcl(
    "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; set out {}; "
    "set lIter [$lPage NewPartInstsIter $lStatus]; set lInst [$lIter NextPartInst $lStatus]; "
    "while {$lInst != $lNullObj} { set ref [DboTclHelper_sMakeCString]; $lInst GetReference $ref; "
    "set loc [$lInst GetLocation $lStatus]; set ox [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
    "set oy [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
    "lappend out \"[DboTclHelper_sGetConstCharPtr $ref]@$ox,$oy\"; "
    "set lInst [$lIter NextPartInst $lStatus] }; delete_DboPagePartInstsIter $lIter; "
    "return [join $out { | }]"
))
print("save:", tcl("Menu {File::Save}"))
