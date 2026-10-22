from dump_page import tcl

print("PING", tcl("expr 1"))
print("VIEW", tcl("IsSchematicViewActive"))
print("COUNT", tcl(
    "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
    "set n 0; set lIter [$lPage NewPartInstsIter $lStatus]; "
    "set lInst [$lIter NextPartInst $lStatus]; "
    "while {$lInst != $lNullObj} { incr n; set lInst [$lIter NextPartInst $lStatus] }; "
    "delete_DboPagePartInstsIter $lIter; return $n"
))
print("LIST", tcl(
    "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
    "set out {}; set lIter [$lPage NewPartInstsIter $lStatus]; "
    "set lInst [$lIter NextPartInst $lStatus]; "
    "while {$lInst != $lNullObj} { "
    "set ref [DboTclHelper_sMakeCString]; $lInst GetReference $ref; "
    "set loc [$lInst GetLocation $lStatus]; "
    "set ox [expr {[DboTclHelper_sGetCPointX $loc]/100.0}]; "
    "set oy [expr {[DboTclHelper_sGetCPointY $loc]/100.0}]; "
    "lappend out \"[DboTclHelper_sGetConstCharPtr $ref]@$ox,$oy\"; "
    "set lInst [$lIter NextPartInst $lStatus] }; "
    "delete_DboPagePartInstsIter $lIter; return [join $out { | }]"
))
print("GLOBS", tcl(__import__("dump_page").CMDS["globals"]))
