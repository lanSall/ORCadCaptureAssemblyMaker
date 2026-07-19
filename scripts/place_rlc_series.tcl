# PSpice-compatible series RLC + VAC + ground 0
# Parts used (must have PSPICETEMPLATE for simulation):
#   R, L, C  - from design cache (source: pspice/ANALOG.OLB)
#   VAC      - from design cache (source: pspice/SOURCE.OLB)
#   ground 0 - from capsym.olb (symbol "0", net name "0")
#
# Incompatible for PSpice (do not use for sim):
#   plain Capture libraries without PSPICETEMPLATE
#   capsym GND left named "GND" instead of "0"
#   TitleBlock / non-electrical symbols
#
# Place (one command at a time; avoid sourcing large scripts):
# PlacePart 1.00 3.00 "C:\\CADENCE\\ORCADX_25.1\\TOOLS\\CAPTURE\\LIBRARY\\PSPICE\\SOURCE.OLB" "VAC" "" FALSE
# PlacePart 2.50 3.00 "C:\\CADENCE\\ORCADX_25.1\\TOOLS\\CAPTURE\\LIBRARY\\PSPICE\\ANALOG.OLB" "R" "" FALSE
# PlacePart 4.00 3.00 "C:\\CADENCE\\ORCADX_25.1\\TOOLS\\CAPTURE\\LIBRARY\\PSPICE\\ANALOG.OLB" "L" "" FALSE
# PlacePart 5.50 3.00 "C:\\CADENCE\\ORCADX_25.1\\TOOLS\\CAPTURE\\LIBRARY\\PSPICE\\ANALOG.OLB" "C" "" FALSE
# PlaceGround 1.00 4.50 "C:/Cadence/OrCADX_25.1/tools/capture/library/capsym.olb" "0" "0"
#
# Wire using GetOffsetHotSpot/100 (see prior session measurements).
