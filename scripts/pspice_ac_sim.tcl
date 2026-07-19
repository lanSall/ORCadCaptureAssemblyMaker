# RLC_VSweep simulation profile
# Path:
#   orcadcpmtest-PSpiceFiles/SCHEMATIC1/RLC_VSweep.sim
# Registered in ORCadCPMTest.opj as active profile.
#
# Requested: voltage 0..1 with 10dB steps
# Fitted because log/dB sweeps cannot include 0V:
#   Start = 1mV, End = 1V
#   Logarithmic, 2 points/decade  ~=  10dB voltage steps
#   Sweep source = V1 (VAC)
# Values: 1m, 3.16m, 10m, 31.6m, 100m, 316m, 1
#
# In Capture: PSpice > Edit Simulation Profile to verify
#   Analysis Type = DC Sweep
#   Sweep variable = Voltage source V1
#   Sweep type = Logarithmic (Decade)
#   Start=1m  End=1  Points/Decade=2
# Then PSpice > Run
#
# Note: series capacitor blocks DC; if the DC sweep looks flat,
# use AC Sweep for frequency response, or parametric ACMAG for
# AC amplitude steps instead.
