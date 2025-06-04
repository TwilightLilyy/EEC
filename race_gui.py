import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import subprocess
import threading
import time
import os
import shutil
import sys
from pathlib import Path
from queue import Queue, Empty
try:
    import irsdk
except ImportError:
    irsdk = None
try:
    import openai
except ImportError:
    openai = None

LOG_FILES = [
    "pitstop_log.csv",
    "standings_log.csv",
    "sorted_standings.csv",
    "driver_swaps.csv",
]

class RaceLoggerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("EEC Logger")
        self.proc = None
        self.log_queue: Queue[str] = Queue()
        self.output_thread = None

        frm = ttk.Frame(root, padding=10)
        frm.grid()

        self.status_lbl = ttk.Label(frm, text="iRacing: ?")
        self.status_lbl.grid(column=0, row=0, sticky="w")
        self.start_btn = ttk.Button(frm, text="Start Logging", command=self.start_logging)
        self.start_btn.grid(column=0, row=1, pady=5, sticky="ew")
        self.stop_btn = ttk.Button(frm, text="Stop Logging", command=self.stop_logging, state="disabled")
        self.stop_btn.grid(column=1, row=1, pady=5, sticky="ew")

        ttk.Button(frm, text="Reset Logs", command=self.reset_logs).grid(column=0, row=2, pady=5, sticky="ew")
        ttk.Button(frm, text="Save Logs…", command=self.save_logs).grid(column=1, row=2, pady=5, sticky="ew")
        ttk.Button(frm, text="View Logs…", command=self.view_logs).grid(column=0, row=3, columnspan=2, pady=5, sticky="ew")
        ttk.Button(frm, text="Export to ChatGPT", command=self.export_logs).grid(column=0, row=4, columnspan=2, pady=5, sticky="ew")

        self.log_box = ScrolledText(frm, width=80, height=20, state="disabled")
        self.log_box.grid(column=0, row=4, columnspan=2, pady=5)

        self.update_thread = threading.Thread(target=self.update_status_loop, daemon=True)
        self.update_thread.start()
        self.root.after(100, self.update_log_box)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ── logging subprocess management ────────────────────────────
    def start_logging(self):
        if self.proc:
            messagebox.showinfo("Logger", "Already running")
            return
        runner = Path(sys.argv[0]).resolve().parent / "race_data_runner.py"
        if not runner.exists():
            runner = Path(sys.argv[0]).resolve().parent.parent / "race_data_runner.py"
        self.proc = subprocess.Popen(
            ["python", str(runner)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self.output_thread = threading.Thread(target=self.read_output, daemon=True)
        self.output_thread.start()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

    def stop_logging(self):
        if not self.proc:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None
        self.output_thread = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    # ── connection status loop ──────────────────────────────────
    def update_status_loop(self):
        while True:
            status = "N/A"
            if irsdk:
                ir = irsdk.IRSDK()
                try:
                    ir.startup()
                    connected = ir.is_initialized and ir.is_connected
                    status = "Connected" if connected else "Waiting"
                except Exception:
                    status = "Error"
                finally:
                    try:
                        ir.shutdown()
                    except Exception:
                        pass
            self.status_lbl.config(text=f"iRacing: {status}")
            time.sleep(2)

    # ── log management helpers ──────────────────────────────────
    def reset_logs(self):
        if not messagebox.askyesno("Confirm", "Delete existing log files?"):
            return
        for f in LOG_FILES:
            if os.path.exists(f):
                open(f, "w").close()
        messagebox.showinfo("Reset", "Logs cleared")

    def save_logs(self):
        target = filedialog.askdirectory(title="Select folder to save logs")
        if not target:
            return
        for f in LOG_FILES:
            if os.path.exists(f):
                shutil.copy(f, target)
        messagebox.showinfo("Saved", f"Logs copied to {target}")

    def view_logs(self):
        log_dir = Path("logs")
        files = [f.name for f in log_dir.glob("*.txt")]
        if not files:
            messagebox.showinfo("Logs", "No log files found")
            return

        win = tk.Toplevel(self.root)
        win.title("View Logs")

        sel = tk.StringVar(value=files[0])
        combo = ttk.Combobox(win, textvariable=sel, values=files, state="readonly")
        combo.pack(fill="x", padx=5, pady=5)

        txt = tk.Text(win, wrap="none")
        txt.pack(fill="both", expand=True, padx=5, pady=5)

        def load(event=None):
            path = log_dir / sel.get()
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except Exception as e:
                content = f"Error reading {path}: {e}"
            txt.delete("1.0", tk.END)
            txt.insert(tk.END, content)
            txt.see(tk.END)

        ttk.Button(win, text="Refresh", command=load).pack(pady=5)
        combo.bind("<<ComboboxSelected>>", load)
        load()

    # ── ChatGPT export ──────────────────────────────────────────
    def export_logs(self):
        if openai is None:
            messagebox.showerror("Export", "openai package not installed")
            return
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            messagebox.showerror("Export", "OPENAI_API_KEY not set")
            return
        openai.api_key = api_key
        data = []
        for f in LOG_FILES:
            if os.path.exists(f):
                with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                    data.append(f"## {f}\n" + fh.read())
        prompt = "\n".join(data)[:12000]  # limit size
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            res_text = resp["choices"][0]["message"]["content"]
            info = filedialog.asksaveasfilename(title="Save analysis", defaultextension=".txt")
            if info:
                with open(info, "w", encoding="utf-8") as out:
                    out.write(res_text)
                messagebox.showinfo("Export", f"Analysis saved to {info}")
        except Exception as e:
            messagebox.showerror("Export", f"Error: {e}")

    # ── log output handling ─────────────────────────────────────
    def read_output(self):
        if self.proc and self.proc.stdout:
            for line in self.proc.stdout:
                self.log_queue.put(line)

    def update_log_box(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_box.configure(state="normal")
                self.log_box.insert("end", line)
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
        except Empty:
            pass
        self.root.after(100, self.update_log_box)

    def on_close(self):
        if self.proc:
            if messagebox.askyesno("Exit", "Stop logging and exit?"):
                self.stop_logging()
            else:
                return
        self.root.destroy()


def main():
    root = tk.Tk()
    RaceLoggerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
