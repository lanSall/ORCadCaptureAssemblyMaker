from dump_page import tcl

print("FIX", tcl("PlaceWire 4.75 2.50 5.10 2.50"))
print("SAVE", tcl("Menu {File::Save}"))
print("NET", tcl("Menu {PSpice::Create Netlist}"))
