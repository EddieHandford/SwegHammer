"""
SwegHammer launcher.

Default:                       python run.py            (GUI menu)
Skip the GUI and run CLI:      python run.py --cli      (existing demo)

The launcher works on any machine with Python installed -- Tkinter ships
with the standard library, and Streamlit is invoked through
``sys.executable -m streamlit`` so PATH quirks don't matter.
"""

from __future__ import annotations

import atexit
import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

_dashboard_proc: Optional[subprocess.Popen] = None
_dashboard_port: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _free_port() -> int:
    """Ask the OS for a free TCP port we can hand to Streamlit."""
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 15.0) -> bool:
    """Block until localhost:port accepts connections (or timeout)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("localhost", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def _terminate_dashboard() -> None:
    if _dashboard_proc and _dashboard_proc.poll() is None:
        _dashboard_proc.terminate()
        try:
            _dashboard_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _dashboard_proc.kill()


atexit.register(_terminate_dashboard)


# ---------------------------------------------------------------------------
# Button actions
# ---------------------------------------------------------------------------

def launch_dashboard(status_var: tk.StringVar) -> None:
    """Start the Streamlit server (if not already running) and open a browser."""
    global _dashboard_proc, _dashboard_port

    if (
        _dashboard_proc
        and _dashboard_proc.poll() is None
        and _dashboard_port is not None
    ):
        webbrowser.open(f"http://localhost:{_dashboard_port}")
        status_var.set(f"Dashboard already running at port {_dashboard_port}.")
        return

    _dashboard_port = _free_port()
    status_var.set(f"Starting Streamlit on port {_dashboard_port}...")

    try:
        _dashboard_proc = subprocess.Popen(
            [
                sys.executable, "-m", "streamlit", "run", "app.py",
                "--server.headless=true",
                "--browser.gatherUsageStats=false",
                f"--server.port={_dashboard_port}",
            ],
            cwd=HERE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        messagebox.showerror(
            "Could not start Python",
            "Python is not on PATH. Make sure Python is installed.",
        )
        return

    def _open_when_ready() -> None:
        port = _dashboard_port
        if port is not None and _wait_for_port(port):
            webbrowser.open(f"http://localhost:{port}")
            status_var.set(f"Dashboard running at http://localhost:{port}")
        else:
            status_var.set(
                "Dashboard did not start within 15s. "
                "Try 'python -m streamlit run app.py' in a terminal to see the error."
            )

    threading.Thread(target=_open_when_ready, daemon=True).start()


def _open_console(cmd: list, status_var: tk.StringVar, label: str) -> None:
    """Open a new console window running cmd."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                ["cmd", "/k", *cmd],
                cwd=HERE,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        elif sys.platform == "darwin":
            quoted = " ".join(f'"{c}"' for c in cmd)
            script = (
                f'tell application "Terminal" to do script '
                f'"cd \\"{HERE}\\" && {quoted}"'
            )
            subprocess.Popen(["osascript", "-e", script])
        else:
            for term in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm"):
                try:
                    subprocess.Popen([term, "-e", *cmd], cwd=HERE)
                    break
                except FileNotFoundError:
                    continue
            else:
                subprocess.Popen(cmd, cwd=HERE)
        status_var.set(f"{label} launched in a new console window.")
    except Exception as exc:
        messagebox.showerror("Launch failed", str(exc))
        status_var.set("Launch failed — see error dialog.")


def run_tournament_dialog(parent: tk.Tk, status_var: tk.StringVar) -> None:
    """Small dialog: pick faction + sims, then launch the round-robin runner."""
    # Load factions lazily so the main window opens fast
    try:
        from code.units import UNIT_CATALOG
        factions = sorted({v.faction for v in UNIT_CATALOG.values() if v.faction})
    except Exception as exc:
        messagebox.showerror("Import error", str(exc))
        return

    dlg = tk.Toplevel(parent)
    dlg.title("Run Round-Robin Tournament")
    dlg.geometry("360x240")
    dlg.resizable(False, False)
    dlg.grab_set()  # modal

    tk.Label(dlg, text="Round-Robin Tournament Runner",
             font=("TkDefaultFont", 12, "bold")).pack(pady=(16, 4))

    faction_choices = ["— All factions —"] + factions
    faction_var = tk.StringVar(value="— All factions —")
    tk.Label(dlg, text="Faction:", anchor="w").pack(fill="x", padx=24)
    faction_menu = tk.OptionMenu(dlg, faction_var, *faction_choices)
    faction_menu.config(width=30)
    faction_menu.pack(padx=24, pady=(0, 8))

    tk.Label(dlg, text="Simulations per matchup:", anchor="w").pack(fill="x", padx=24)
    sims_var = tk.IntVar(value=100)
    tk.Spinbox(dlg, from_=10, to=1000, increment=10, textvariable=sims_var,
               width=8).pack(anchor="w", padx=24, pady=(0, 8))

    skip_var = tk.BooleanVar(value=True)
    tk.Checkbutton(dlg, text="Skip already-computed matchups (--skip-done)",
                   variable=skip_var).pack(anchor="w", padx=20, pady=(0, 12))

    def _launch() -> None:
        faction = faction_var.get()
        sims = sims_var.get()
        cmd = [sys.executable, "-m", "scripts.run_tournament"]
        if faction == "— All factions —":
            cmd += ["--all"]
            label = "Tournament (all factions)"
        else:
            cmd += ["--faction", faction]
            label = f"Tournament ({faction})"
        cmd += ["--sims", str(sims)]
        if skip_var.get():
            cmd += ["--skip-done"]
        dlg.destroy()
        _open_console(cmd, status_var, label)

    tk.Button(dlg, text="▶  Run Tournament", command=_launch,
              width=24, pady=5, font=("TkDefaultFont", 10, "bold")).pack()


def run_cli_demo(status_var: tk.StringVar) -> None:
    """Open a new console window running the CLI demo."""
    status_var.set("Launching CLI demo in a new window...")
    _open_console([sys.executable, "-m", "code.main"], status_var, "CLI demo")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def launch_gui() -> None:
    root = tk.Tk()
    root.title("SwegHammer Launcher")
    root.geometry("440x360")
    root.resizable(False, False)

    tk.Label(
        root, text="SwegHammer", font=("TkDefaultFont", 20, "bold"),
    ).pack(pady=(22, 2))
    tk.Label(
        root,
        text="Pick how you want to run the simulator",
        font=("TkDefaultFont", 10),
        fg="#555",
    ).pack(pady=(0, 18))

    status_var = tk.StringVar(value="Ready.")

    btn_kwargs = {"width": 32, "pady": 6, "font": ("TkDefaultFont", 11)}

    tk.Button(
        root,
        text="Launch web dashboard (browser)",
        command=lambda: launch_dashboard(status_var),
        **btn_kwargs,
    ).pack(pady=4)

    tk.Button(
        root,
        text="Run CLI demo (new console)",
        command=lambda: run_cli_demo(status_var),
        **btn_kwargs,
    ).pack(pady=4)

    tk.Button(
        root,
        text="Run Round-Robin Tournament…",
        command=lambda: run_tournament_dialog(root, status_var),
        **btn_kwargs,
    ).pack(pady=4)

    tk.Button(
        root, text="Quit", command=root.destroy, width=32, pady=4,
    ).pack(pady=(12, 0))

    tk.Label(
        root,
        textvariable=status_var,
        font=("TkDefaultFont", 9),
        fg="#666",
        wraplength=400,
        justify="center",
    ).pack(side="bottom", pady=10)

    root.mainloop()


if __name__ == "__main__":
    if "--cli" in sys.argv:
        from code.main import main as cli_main
        cli_main()
    else:
        launch_gui()
