"""Query Capture design path / page name."""
from dump_page import tcl

print(
    "DESIGN",
    tcl(
        "set d [GetActivePMDesign]; set n [DboTclHelper_sMakeCString]; "
        "$d GetName $n; return [DboTclHelper_sGetConstCharPtr $n]"
    ),
)
print(
    "PATH",
    tcl(
        "set d [GetActivePMDesign]; set n [DboTclHelper_sMakeCString]; "
        "catch {$d GetPathName $n}; return [DboTclHelper_sGetConstCharPtr $n]"
    ),
)
print(
    "PAGE",
    tcl(
        "set p [GetActivePage]; set n [DboTclHelper_sMakeCString]; "
        "$p GetName $n; return [DboTclHelper_sGetConstCharPtr $n]"
    ),
)
print("VIEW", tcl("IsSchematicViewActive"))
print("PARTS", tcl(
    "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
    "set n 0; set lIter [$lPage NewPartInstsIter $lStatus]; "
    "set lInst [$lIter NextPartInst $lStatus]; "
    "while {$lInst != $lNullObj} { incr n; set lInst [$lIter NextPartInst $lStatus] }; "
    "delete_DboPagePartInstsIter $lIter; return $n"
))
print("GLOBS", tcl(__import__("dump_page").CMDS["globals"]))
