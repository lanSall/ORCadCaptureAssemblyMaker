"""Restart Capture on joeldesign and wait for Tcl port 9020."""
from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path

CAPTURE = Path(r"C:\Cadence\OrCADX_25.1\tools\bin\Capture.exe")
OPJ = Path(
    r"C:\Users\lance\AppData\Roaming\SPB_Data\cdssetup\workspace\projects\joeldesign\joeldesign.opj"
)


def port_up() -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", 9020), timeout=1.5)
        s.close()
        return True
    except OSError:
        return False


def main() -> None:
    if port_up():
        print("9020 already listening")
        return
    print("Stopping Capture…")
    subprocess.run(["taskkill", "/IM", "Capture.exe", "/F"], capture_output=True)
    time.sleep(3)
    print("Starting", OPJ)
    subprocess.Popen([str(CAPTURE), str(OPJ)])
    for i in range(40):
        time.sleep(1)
        if port_up():
            print(f"9020 up after {i + 1}s")
            return
        print(f"  wait {i + 1}s")
    raise SystemExit("port 9020 did not come up")


if __name__ == "__main__":
    main()
