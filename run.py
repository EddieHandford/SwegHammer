"""
SwegHammer launcher.

Default:                       python run.py            (GUI menu)
Skip the GUI and run CLI:      python run.py --cli      (existing demo)

The launcher works on any machine with Python installed -- Tkinter ships
with the standard library, and Streamlit is invoked through
``sys.executable -m streamlit`` so PATH quirks don't matter.
"""

from __future__ import annotations

import glob
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


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


# ---------------------------------------------------------------------------
# Button actions
# ---------------------------------------------------------------------------

def launch_dashboard(root: tk.Tk, status_var: tk.StringVar) -> None:
    """Start Streamlit headlessly and open the browser once the port is ready."""
    port = _free_port()
    status_var.set(f"Starting Streamlit on port {port}…")
    streamlit_bin = shutil.which("streamlit") or next(
        iter(sorted(glob.glob(os.path.expanduser("~/.pyenv/versions/*/bin/streamlit")))),
        None,
    )
    if streamlit_bin:
        cmd = [streamlit_bin, "run", "app.py"]
    else:
        cmd = [sys.executable, "-m", "streamlit", "run", "app.py"]

    try:
        proc = subprocess.Popen(
            [
                *cmd,
                "--server.headless=true",
                "--browser.gatherUsageStats=false",
                f"--server.port={port}",
            ],
            cwd=HERE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        messagebox.showerror("Launch failed", "Streamlit not found. Run: pip install streamlit")
        return

    url = f"http://localhost:{port}"

    def _open_browser() -> None:
        # Give the process a moment; if it dies immediately show stderr.
        time.sleep(1.5)
        if proc.poll() is not None:
            err = (proc.stderr.read().decode(errors="replace") if proc.stderr else "")
            root.after(0, lambda: messagebox.showerror(
                "Streamlit failed to start",
                f"Command: {proc.args}\n\n{err or 'Process exited immediately.'}"
            ))
            root.after(0, lambda: status_var.set("Dashboard failed to start."))
            return
        if _wait_for_port(port, timeout=30.0):
            root.after(0, lambda: webbrowser.open(url))
            root.after(0, lambda: status_var.set(f"Dashboard open at {url}"))
        else:
            root.after(0, lambda: status_var.set(
                "Timed out waiting for Streamlit. "
                "Try 'python -m streamlit run app.py' in a terminal to see the error."
            ))

    threading.Thread(target=_open_browser, daemon=True).start()


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
        command=lambda: launch_dashboard(root, status_var),
        **btn_kwargs,
    ).pack(pady=4)

    tk.Button(
        root,
        text="Run CLI demo (new console)",
        command=lambda: run_cli_demo(status_var),
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
