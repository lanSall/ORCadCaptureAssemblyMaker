"""Parse Lab2_AC.out .PRINT table; report DC gain, -3dB BW; save Bode plot."""
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

OUT = Path(
    r"C:\Users\lance\AppData\Roaming\SPB_Data\cdssetup\workspace\projects"
    r"\orcadcpmtest\1\ORCadCPMTest-PSpiceFiles\SCHEMATIC1\Lab2_AC\Lab2_AC.out"
)
RESULTS = Path(r"C:\Users\lance\tcl-mcp-server\labs\lab2_results")
RESULTS.mkdir(parents=True, exist_ok=True)

rows = []
in_table = False
for line in OUT.read_text(errors="replace").splitlines():
    if re.match(r"\s*FREQ\s+V\(VOUT\)", line):
        in_table = True
        continue
    if in_table:
        m = re.findall(r"[-+]?\d+\.\d+E[-+]\d+", line)
        if len(m) >= 5:
            rows.append([float(x) for x in m[:5]])
        elif rows and not line.strip():
            in_table = False

data = np.array(rows)
f, vout, vin, vout2, vin2 = data.T
g1 = vout / vin
g2 = vout2 / vin2

def report(name, f, g):
    g0 = g[0]
    idx = np.where(g <= g0 / np.sqrt(2))[0]
    f3 = f[idx[0]] if len(idx) else float("nan")
    print(f"{name}: DC gain = {g0:.3f} V/V ({20*np.log10(g0):.2f} dB), "
          f"-3dB ~ {f3:.3g} Hz")
    return g0, f3

print(f"points: {len(f)}, {f[0]:.0f} Hz .. {f[-1]:.3g} Hz")
report("non-inverting V(VOUT)/V(VIN) ", f, g1)
report("inverting     V(VOUT2)/V(VIN2)", f, g2)

fig, ax = plt.subplots(figsize=(9, 5.5))
ax.semilogx(f, 20 * np.log10(np.maximum(g1, 1e-12)), label="Non-inv |VOUT/VIN| (ideal 20 dB)")
ax.semilogx(f, 20 * np.log10(np.maximum(g2, 1e-12)), label="Inv |VOUT2/VIN2| (ideal 26 dB)")
ax.set_xlabel("Frequency (Hz)")
ax.set_ylabel("Gain (dB)")
ax.set_title("ECEN 3314 Lab 2 — TL074 amplifier AC sweep (1 Hz – 100 MHz)")
ax.grid(True, which="both", alpha=0.4)
ax.legend()
fig.tight_layout()
png = RESULTS / "lab2_bode.png"
fig.savefig(png, dpi=130)
print("plot:", png)
