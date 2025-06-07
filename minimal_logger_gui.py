"""Minimal Tkinter GUI to control race_data_runner logging."""

from __future__ import annotations

import signal
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import Tk, Label, Button, StringVar


class MinimalLoggerGUI:
    def __init__(self, master: Tk) -> None:
        self.master = master
        master.title("Minimal Logger")

        self.status = StringVar(value="Stopped")
        self.proc: subprocess.Popen | None = None

        self.status_label = Label(master, textvariable=self.status)
        self.status_label.pack(padx=10, pady=10)

        self.start_btn = Button(master, text="Start", command=self.start)
        self.start_btn.pack(fill="x", padx=10, pady=5)

        self.stop_btn = Button(master, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(fill="x", padx=10, pady=5)

        # Periodically check the subprocess state
        self.master.after(1000, self.check_proc)

    # path to race_data_runner.py relative to this file or parent
    def _runner_path(self) -> Path:
        base = Path(__file__).resolve().parent
        runner = base / "race_data_runner.py"
        if not runner.exists():
            runner = base.parent / "race_data_runner.py"
        return runner

    def start(self) -> None:
        if self.proc:
            return
        runner = self._runner_path()
        cmd = [sys.executable, str(runner), "--db", "eec_log.db"]
        try:
            self.proc = subprocess.Popen(cmd, cwd=runner.parent)
        except Exception:
            self.proc = None
            return

        self.status.set("Running")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

    def stop(self) -> None:
        if not self.proc:
            return

        def _wait() -> None:
            try:
                self.proc.send_signal(signal.SIGINT)
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.terminate()
                    self.proc.wait(timeout=5)
                except Exception:
                    pass
            finally:
                self.proc = None
                self.master.after(0, self._update_stopped)

        threading.Thread(target=_wait, daemon=True).start()

    def _update_stopped(self) -> None:
        self.status.set("Stopped")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def check_proc(self) -> None:
        if self.proc and self.proc.poll() is not None:
            self.proc = None
            self._update_stopped()
        self.master.after(1000, self.check_proc)


def main() -> None:
    root = Tk()
    MinimalLoggerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
