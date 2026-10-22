# Lab / circuit status

What is currently built in Capture and where results live. Update after each session.

## ECEN 3314 labs (`orcadcpmtest\1\orcadcpmtest.dsn`, PAGE1)

### Lab 2: done (2026-07-20)
- Non-inverting: U1 TL074, R1=1k, R2=9k, RL=1Meg, VIN VAC, VDD/VSS ±15 V (x≈1–4.7)
- Inverting: U2, R3=1k, R4=20k, RL2=1Meg, VIN2 (x≈5.5–9.9)
- Profile `Lab2_AC`: AC DEC 10 1 100Meg. Verified gains 10.0 / 20.0 V/V, f3dB ≈ 398k / 200k
- Results: `labs/lab2_results/lab2_bode.png`. Scripts: `lab2_place.py`, `lab2_rewire.py`, `lab2_results.py`

### Lab 3: done (sims + Word report)
- Report: `labs/lab3_results/ECEN3314_Lab3_Simulation_Results.docx`; regenerate with `scripts/lab3_run_sims.py`, `scripts/build_lab3_docx.py`
- Diode circuits may remain in the upper area of PAGE1

### Lab 5: was in progress
- Profile `SCHEMATIC1-Lab5_TRAN` may still exist on disk; `sim_lib.ParametricSettings` encodes the Lab 5 parametric block

### Lab 8: Fig 6 on page (readable rebuild pending)
- CS amp: M1 MbreakN MODEL=`2N7000`, VGG VSIN (2.8/0.1/1kHz, ACMAG=1), RD=330, VDD=10 V, C1=47u, RL=10k, aliases Vin/Vout
- Rebuild: `scripts/lab8_place.py --rebuild`. Next: AC profile DEC 10 1 100Meg with `2n7000.lib`; add markers manually

### Lab 9: schematics on page (y≈1.5–4)
- Fig 5 (left): Q1 Q2N3904, VIN VSIN (330mV/10mV/1kHz), RC=1k, VCC=5 V
- Fig 6 (right): Q2, VIN2, RC2, VCC2, C1=10u, RL=10k
- Netlists: `labs/lab9_results/netlists/`. Rebuild with `placement_lib.build_ce_amp_fig5`. Next: DC/AC profiles for §6

## ECEN 4013 homework

### Wk 2 simulation HW: N=5 Bessel LPF, fc = 3 kHz (2026-08-26)
- Unity-gain Sallen-Key 2nd order + 3rd-order VCVS, TL081
- Script: `scripts/hw_bessel_lpf.py` (`--inspect`, `--dry-run`, `--rebuild`, `--place`); results in `labs/hw_lpf_results/`

## Other projects

### Starter motor MOSFET / SS56 drive (`joeldesign`, 2026-09-10)
- Reliability study of the 11.1 V DC motor driver (diode/MOSFET failures under transients)
- Script: `scripts/starter_motor_place.py`; pulse stimuli patched into the `.cir` (VPULSE via Tcl crashes)
- Capture restart for this project: `scripts/restart_capture.py`
- Report: `C:/Users/lance/Downloads/PDFExtraction/starter_motor/Starter_MOSFET_Reliability_Report.pdf`
