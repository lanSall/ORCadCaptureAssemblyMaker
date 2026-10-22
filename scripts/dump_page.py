"""Dump the active Capture PAGE via the Tcl socket on 9020."""
from __future__ import annotations

import socket
import sys


def tcl(cmd: str, timeout: float = 25.0) -> str:
    s = socket.create_connection(("127.0.0.1", 9020), timeout=8)
    s.settimeout(timeout)
    payload = cmd if cmd.endswith("\n") else cmd + "\n"
    s.sendall(payload.encode("utf-8"))
    s.settimeout(2.0)
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


CMDS = {
    "ping": "expr 1",
    "snapshot": (
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set out {}; set lIter [$lPage NewPartInstsIter $lStatus]; "
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
        "lappend out \"[DboTclHelper_sGetConstCharPtr $ref]\\t[DboTclHelper_sGetConstCharPtr $pv]\\t"
        "[DboTclHelper_sGetConstCharPtr $spn]\\t$ox\\t$oy\\t$rot\"; "
        "set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; return [join $out {|||}]"
    ),
    "pins": (
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set out {}; set lIter [$lPage NewPartInstsIter $lStatus]; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { "
        "set ref [DboTclHelper_sMakeCString]; $lInst GetReference $ref; "
        "set lPlaced [DboPartInstToDboPlacedInst $lInst]; "
        "if {$lPlaced != $lNullObj} { "
        "set lPinIter [$lPlaced NewPinsIter $lStatus]; set lPin [$lPinIter NextPin $lStatus]; "
        "while {$lPin != $lNullObj} { "
        "set pn [DboTclHelper_sMakeCString]; $lPin GetPinName $pn; "
        "set num [DboTclHelper_sMakeCString]; $lPin GetPinNumber $num; "
        "set hs [$lPin GetOffsetHotSpot $lStatus]; "
        "set hx [expr {[DboTclHelper_sGetCPointX $hs]/100.0}]; "
        "set hy [expr {[DboTclHelper_sGetCPointY $hs]/100.0}]; "
        "lappend out \"[DboTclHelper_sGetConstCharPtr $ref]\\t[DboTclHelper_sGetConstCharPtr $pn]\\t"
        "[DboTclHelper_sGetConstCharPtr $num]\\t$hx\\t$hy\"; "
        "set lPin [$lPinIter NextPin $lStatus] }; delete_DboPartInstPinsIter $lPinIter }; "
        "set lInst [$lIter NextPartInst $lStatus] }; delete_DboPagePartInstsIter $lIter; "
        "return [join $out {|||}]"
    ),
    "wires": (
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set out {}; set n 0; set wIter [$lPage NewWiresIter $lStatus]; "
        "set w [$wIter NextWire $lStatus]; "
        "while {$w != $lNullObj} { incr n; "
        "set sx -1; set sy -1; set ex -1; set ey -1; "
        "catch {set sp [$w GetStartPoint $lStatus]; set sx [expr {[DboTclHelper_sGetCPointX $sp]/100.0}]; set sy [expr {[DboTclHelper_sGetCPointY $sp]/100.0}]}; "
        "catch {set ep [$w GetEndPoint $lStatus]; set ex [expr {[DboTclHelper_sGetCPointX $ep]/100.0}]; set ey [expr {[DboTclHelper_sGetCPointY $ep]/100.0}]}; "
        "lappend out \"$sx,$sy->$ex,$ey\"; "
        "set w [$wIter NextWire $lStatus] }; "
        "delete_DboPageWiresIter $wIter; return \"$n|||[join $out { | }]\""
    ),
    "globals": (
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set out {}; set gIter [$lPage NewGlobalsIter $lStatus]; "
        "set g [$gIter NextGlobal $lStatus]; "
        "while {$g != $lNullObj} { "
        "set nm [DboTclHelper_sMakeCString]; catch {$g GetName $nm}; "
        "set loc [$g GetLocation $lStatus]; "
        "set ox [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
        "set oy [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
        "lappend out \"[DboTclHelper_sGetConstCharPtr $nm]@$ox,$oy\"; "
        "set g [$gIter NextGlobal $lStatus] }; "
        "delete_DboPageGlobalsIter $gIter; return [join $out { | }]"
    ),
    "srcprops": (
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set out {}; set lIter [$lPage NewPartInstsIter $lStatus]; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { "
        "set ref [DboTclHelper_sMakeCString]; $lInst GetReference $ref; "
        "set rs [DboTclHelper_sGetConstCharPtr $ref]; "
        "if {[string match {V*} $rs]} { "
        "set pIter [$lInst NewUserPropsIter $lStatus]; "
        "set p [$pIter NextUserProp $lStatus]; "
        "set props {}; "
        "while {$p != $lNullObj} { "
        "set n [DboTclHelper_sMakeCString]; $p GetName $n; "
        "set v [DboTclHelper_sMakeCString]; catch {$p GetStringValue $v}; "
        "lappend props \"[DboTclHelper_sGetConstCharPtr $n]=[DboTclHelper_sGetConstCharPtr $v]\"; "
        "set p [$pIter NextUserProp $lStatus] }; "
        "catch {delete_DboUserPropsIter $pIter}; "
        "lappend out \"$rs:[join $props {,}]\"; "
        "}; "
        "set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; return [join $out {|||}]"
    ),
    "probe_dp": (
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set lIter [$lPage NewPartInstsIter $lStatus]; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "set dIter [$lInst NewDisplayPropsIter $lStatus]; "
        "set dp [$dIter NextProp $lStatus]; "
        "delete_DboPagePartInstsIter $lIter; "
        "catch {$dp NoSuchMethod}"
    ),
}


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    if label not in CMDS:
        print("unknown", label)
        return 2
    print(tcl(CMDS[label]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
