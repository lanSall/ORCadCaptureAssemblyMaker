"""Query the active Capture page without PowerShell eating $vars."""
from dump_page import tcl

print("PING", tcl("expr 1"))
print("PAGE_OBJ", tcl("set p [GetActivePage]; return $p"))
print(
    "PAGE_NAME",
    tcl(
        "set p [GetActivePage]; set n [DboTclHelper_sMakeCString]; "
        "$p GetName n; return [DboTclHelper_sGetConstCharPtr n]"
    ),
)
print(
    "PM",
    tcl(
        "set d [GetActivePMDesign]; set n [DboTclHelper_sMakeCString]; "
        "catch {$d GetName n}; return [DboTclHelper_sGetConstCharPtr n]"
    ),
)
print(
    "COUNT",
    tcl(
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set n 0; set lIter [$lPage NewPartInstsIter $lStatus]; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { incr n; set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; return $n"
    ),
)
print("SNAP", tcl(open(__file__).read() and __import__("dump_page").CMDS["snapshot"]))
print("GLOBS", tcl(__import__("dump_page").CMDS["globals"]))
