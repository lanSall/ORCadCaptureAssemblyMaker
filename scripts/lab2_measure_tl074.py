"""Measure pin offsets of the TL074 just placed at (5.0, 1.0) on PAGE1."""
import socket

def tcl(cmd, timeout=10):
    s = socket.create_connection(("127.0.0.1", 9020), timeout=3)
    s.settimeout(timeout)
    s.sendall((cmd + "\n").encode())
    data = s.recv(65536)
    s.close()
    return data.decode(errors="replace").strip()

raw = tcl(
    "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
    "set lIter [$lPage NewPartInstsIter $lStatus]; set lInst [$lIter NextPartInst $lStatus]; "
    "set out {}; while {$lInst != $lNullObj} { "
    "set loc [$lInst GetLocation $lStatus]; "
    "set ox [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
    "set oy [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
    "if {abs($ox-5.0)<0.05 && abs($oy-1.0)<0.05} { "
    "set lPlaced [DboPartInstToDboPlacedInst $lInst]; "
    "set lPinIter [$lPlaced NewPinsIter $lStatus]; set lPin [$lPinIter NextPin $lStatus]; "
    "while {$lPin != $lNullObj} { "
    "set pn [DboTclHelper_sMakeCString]; $lPin GetPinName $pn; "
    "set num [DboTclHelper_sMakeCString]; $lPin GetPinNumber $num; "
    "set hs [$lPin GetOffsetHotSpot $lStatus]; "
    "set hx [expr {[DboTclHelper_sGetCPointX $hs]/100.0}]; "
    "set hy [expr {[DboTclHelper_sGetCPointY $hs]/100.0}]; "
    "lappend out \"[DboTclHelper_sGetConstCharPtr $pn]/[DboTclHelper_sGetConstCharPtr $num]=[expr {$hx-$ox}],[expr {$hy-$oy}]\"; "
    "set lPin [$lPinIter NextPin $lStatus] }; delete_DboPartInstPinsIter $lPinIter }; "
    "set lInst [$lIter NextPartInst $lStatus] }; delete_DboPagePartInstsIter $lIter; "
    "return [join $out {|}]"
)
print(raw)
