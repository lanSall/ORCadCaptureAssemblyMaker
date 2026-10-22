"""Create PSpice netlist via Capture menu; auto-dismiss dialogs (OK/Yes)."""
import ctypes
import socket
import subprocess
import sys
import threading
import time
from ctypes import wintypes

user32 = ctypes.windll.user32


def capture_pid() -> int:
    out = subprocess.check_output(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process Capture).Id"], text=True)
    return int(out.strip())


def tcl(cmd: str, timeout: float = 30.0) -> str:
    s = socket.create_connection(("127.0.0.1", 9020), timeout=5)
    s.settimeout(timeout)
    if not cmd.endswith("\n"):
        cmd += "\n"
    s.sendall(cmd.encode())
    data = s.recv(65536)
    s.close()
    return data.decode("utf-8", "replace").strip()


def dismiss_loop(pid: int, stop: threading.Event) -> None:
    while not stop.is_set():
        hits = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(hwnd, lp):
            p = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid and user32.IsWindowVisible(hwnd):
                cls = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(hwnd, cls, 64)
                if cls.value == "#32770":
                    hits.append(hwnd)
            return True

        user32.EnumWindows(cb, 0)
        for dlg in hits:
            @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            def cb2(h, lp):
                cls = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(h, cls, 64)
                n = user32.GetWindowTextLengthW(h)
                b = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(h, b, n + 1)
                if cls.value == "Static" and b.value:
                    print("  dlg:", b.value.replace("\n", " ")[:120], flush=True)
                if cls.value == "Button" and b.value in ("OK", "&Yes", "Yes"):
                    user32.PostMessageW(h, 0x00F5, 0, 0)
                    print("  clicked", b.value, flush=True)
                return True

            user32.EnumChildWindows(dlg, cb2, 0)
        time.sleep(0.7)


def main() -> int:
    pid = capture_pid()
    print("capture pid", pid)
    stop = threading.Event()
    t = threading.Thread(target=dismiss_loop, args=(pid, stop), daemon=True)
    t.start()

    print("save:", tcl("Menu {File::Save}"))
    time.sleep(1)
    for menu in ("PSpice::Create Netlist", "Tools::Create Netlist"):
        print("menu try:", menu)
        try:
            r = tcl(f"Menu {{{menu}}}", timeout=60)
        except Exception as e:  # noqa: BLE001
            r = f"ERR {e}"
        print("  ->", r)
        if "No MenuID" not in r and not r.startswith("ERR"):
            break
        time.sleep(1)
    time.sleep(3)
    stop.set()
    t.join(timeout=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
