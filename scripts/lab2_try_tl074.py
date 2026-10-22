"""Try TL074 PlacePart variations on Capture PAGE1, dismissing error dialogs.

Handles the ORCAP-1687 'Unable to place object' modal that blocks the Tcl socket.
"""
import ctypes
import socket
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
CAPTURE_PID = int(sys.argv[1]) if len(sys.argv) > 1 else 34256
OLB = "C:/Cadence/OrCADX_25.1/tools/capture/library/pspice/tex_inst.olb"


def tcl(cmd, timeout=6):
    try:
        s = socket.create_connection(("127.0.0.1", 9020), timeout=3)
        s.settimeout(timeout)
        s.sendall((cmd + "\n").encode())
        data = s.recv(65536)
        s.close()
        return data.decode(errors="replace").strip()
    except Exception as e:  # noqa: BLE001
        return "TIMEOUT/" + str(e)


def find_dialogs():
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lp):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == CAPTURE_PID and user32.IsWindowVisible(hwnd):
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, 64)
            if cls.value == "#32770":
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found


def dismiss():
    for dlg in find_dialogs():
        btns = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb2(h, lp):
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(h, cls, 64)
            n = user32.GetWindowTextLengthW(h)
            b = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(h, b, n + 1)
            if cls.value == "Button":
                btns.append((h, b.value))
            elif cls.value == "Static" and b.value:
                print("  dialog text:", b.value.replace("\n", " "))
            return True

        user32.EnumChildWindows(dlg, cb2, 0)
        for h, label in btns:
            if label in ("OK", "&No", "No", "Cancel"):
                user32.PostMessageW(h, 0x00F5, 0, 0)  # BM_CLICK
                print("  clicked", label)
                break


def count_parts():
    return tcl(
        "set lStatus [DboState]; set lNullObj NULL; set lPage [GetActivePage]; "
        "set n 0; set lIter [$lPage NewPartInstsIter $lStatus]; "
        "set lInst [$lIter NextPartInst $lStatus]; "
        "while {$lInst != $lNullObj} { incr n; set lInst [$lIter NextPartInst $lStatus] }; "
        "delete_DboPagePartInstsIter $lIter; return $n"
    )


DSN = (
    "C:/Users/lance/AppData/Roaming/SPB_Data/cdssetup/workspace/projects/"
    "orcadcpmtest/1/orcadcpmtest.dsn"
)

ATTEMPTS = [
    (f'PlacePart 5.00 1.00 "{OLB}" "TL074/301/TI" "A" FALSE', "olb + section A"),
    (f'PlacePart 5.00 1.00 "{DSN}" "TL074/301/TI" "A" FALSE', "cache + section A"),
    (f'PlacePart 5.00 1.00 "{DSN}" "TL074/301/TI" "" FALSE', "cache no dev"),
]


def main():
    base = count_parts()
    print("baseline parts:", base)
    for cmd, label in ATTEMPTS:
        print("try:", label)
        print("  ret:", tcl(cmd, timeout=8))
        time.sleep(1.0)
        dismiss()
        time.sleep(0.5)
        c = count_parts()
        print("  parts now:", c)
        try:
            if int(c) > int(base):
                print("  SUCCESS with", label)
                return
        except ValueError:
            print("  count unreadable, continuing")
    print("all attempts failed")


if __name__ == "__main__":
    main()
