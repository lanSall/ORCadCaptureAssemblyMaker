from dump_page import tcl, CMDS
print(tcl(CMDS["pins"]).replace("|||", "\n"))
print("---WIRES---")
print(tcl(CMDS["wires"]))
