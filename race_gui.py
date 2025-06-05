import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import subprocess
import signal
import threading
import time
import os
import shutil
import sys
from pathlib import Path
from queue import Queue, Empty
import csv
import re

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
    "driver_times.csv",
]

# Map ANSI colour codes (foreground) to Tkinter tag names
ANSI_COLOUR_MAP = {
    "30": "black",
    "90": "black",
    "31": "red",
    "91": "red",
    "32": "green",
    "92": "green",
    "33": "yellow",
    "93": "yellow",
    "34": "blue",
    "94": "blue",
    "35": "magenta",
    "95": "magenta",
    "36": "cyan",
    "96": "cyan",
    "37": "white",
    "97": "white",
}


def filter_rows(rows):
    """Filter out non-racing entries from standings rows."""
    filtered = []
    car_re = re.compile(r"car\s*\d+$", re.IGNORECASE)
    for r in rows:
        driver = r.get("Driver", r.get("DriverName", ""))
        team = r.get("Team", r.get("TeamName", ""))
        try:
            pos = int(r.get("Pos", 0))
        except Exception:
            pos = 0
        try:
            laps = float(r.get("Laps", 0))
        except Exception:
            laps = 0.0
        if driver in {"Pace Car", "Lily Bowling"}:
            continue
        if team == "Lily Bowling":
            continue
        d = driver.strip().lower()
        t = team.strip().lower()
        if d == t and car_re.match(d):
            continue
        if pos <= 0 or laps <= 0:
            continue
        filtered.append(r)
    return filtered


class RaceLoggerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("EEC Logger")

        self.setup_style()
        icon_path = Path(__file__).resolve().parent / "Logos" / "App" / "EECApp.png"
        if icon_path.exists():
            try:
                self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
            except Exception:
                pass
        self.proc = None
        self.log_queue: Queue[str] = Queue()
        self.output_thread = None

        menubar = tk.Menu(root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Quit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        root.config(menu=menubar)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        frm = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frm, text="Logger")

        self.status_lbl = ttk.Label(frm, text="iRacing: ?")
        self.status_lbl.grid(column=0, row=0, sticky="w")
        self.start_btn = ttk.Button(
            frm, text="Start Logging", command=self.start_logging
        )
        self.start_btn.grid(column=0, row=1, pady=5, sticky="ew")
        self.stop_btn = ttk.Button(
            frm, text="Stop Logging", command=self.stop_logging, state="disabled"
        )
        self.stop_btn.grid(column=1, row=1, pady=5, sticky="ew")

        ttk.Button(frm, text="Reset Logs", command=self.reset_logs).grid(
            column=0, row=2, pady=5, sticky="ew"
        )
        ttk.Button(frm, text="Save Logs…", command=self.save_logs).grid(
            column=1, row=2, pady=5, sticky="ew"
        )
        ttk.Button(frm, text="View Standings…", command=self.view_standings).grid(
            column=0, row=4, columnspan=2, pady=5, sticky="ew"
        )
        ttk.Button(frm, text="View Drive Times…", command=self.view_driver_times).grid(
            column=0, row=5, columnspan=2, pady=5, sticky="ew"
        )
        ttk.Button(frm, text="Export to ChatGPT", command=self.export_logs).grid(
            column=0, row=6, columnspan=2, pady=5, sticky="ew"
        )

        self.log_box = ScrolledText(
            frm,
            width=80,
            height=20,
            state="disabled",
            background=self.log_box_bg,
            foreground=self.fg,
            insertbackground="white",
        )
        self.log_box.grid(column=0, row=7, columnspan=2, pady=5)

        # Additional tabs for CSV logs
        self.create_csv_tab("pitstop_log.csv", "Pit Stops")
        self.create_csv_tab("driver_swaps.csv", "Driver Swaps")
        self.create_csv_tab("standings_log.csv", "Standings Log")

        # ── ANSI colour setup for log output ────────────────────
        self._ansi_re = re.compile(r"\x1b\[([0-9;]+)m")
        self._current_tags: list[str] = []
        _colours = {
            "black": "black",
            "red": "red",
            "green": "green",
            "yellow": "#cccc00",
            "blue": "blue",
            "magenta": "magenta",
            "cyan": "cyan",
            "white": "white",
        }
        for name, colour in _colours.items():
            self.log_box.tag_config(f"fg-{name}", foreground=colour)
        self.log_box.tag_config("bold", font=("TkDefaultFont", 9, "bold"))

        self.update_thread = threading.Thread(
            target=self.update_status_loop, daemon=True
        )
        self.update_thread.start()
        self.root.after(100, self.update_log_box)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        self.bg = "#23272e"
        self.fg = "#e7e7ff"
        accent = "#3c445c"
        self.root.configure(bg=self.bg)
        # Escaped font family to avoid TclError when family name has spaces
        self.root.option_add("*Font", "{Segoe UI} 10")
        style.configure("TFrame", background=self.bg)
        style.configure("TLabel", background=self.bg, foreground=self.fg)
        style.configure("TButton", background="#2b3249", foreground=self.fg, padding=6)
        style.map("TButton", background=[("active", accent)])
        style.configure("TNotebook", background=self.bg)
        style.configure(
            "TNotebook.Tab", background="#2b3249", foreground=self.fg, padding=(10, 4)
        )
        style.map("TNotebook.Tab", background=[("selected", accent)])
        self.log_box_bg = "#111111"

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
            encoding="utf-8",
            errors="replace",
        )
        self.output_thread = threading.Thread(target=self.read_output, daemon=True)
        self.output_thread.start()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

    def stop_logging(self):
        if not self.proc:
            return
        try:
            # Gracefully stop the runner so it can terminate child processes
            self.proc.send_signal(signal.SIGINT)
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Fallback to force termination if it doesn't exit
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            pass
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

    def create_csv_tab(self, csv_path: str, title: str) -> None:
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=title)
        tree = ttk.Treeview(frame, show="headings")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        def load() -> None:
            tree.delete(*tree.get_children())
            path = Path(csv_path)
            if not path.exists():
                base = Path(sys.argv[0]).resolve().parent
                for p in (Path.cwd() / csv_path, base / csv_path, base.parent / csv_path):
                    if p.exists():
                        path = p
                        break
            if not path.exists():
                return
            # Some log files may contain characters that are not valid UTF-8.
            # Using errors="replace" avoids a crash when decoding such files by
            # substituting invalid bytes with the Unicode replacement character.
            with open(path, newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    return
                tree["columns"] = reader.fieldnames
                for c in reader.fieldnames:
                    tree.heading(c, text=c)
                    tree.column(c, anchor="center")
                for row in reader:
                    tree.insert(
                        "", "end", values=[row.get(c, "") for c in reader.fieldnames]
                    )

        ttk.Button(frame, text="Refresh", command=load).grid(
            row=1, column=0, columnspan=2, pady=5
        )
        load()

    def view_logs(self):
        log_dir = Path("logs")
        file_map = {f.name: f for f in log_dir.glob("*.txt")}
        swap_file = Path("driver_swaps.csv")
        if swap_file.exists():
            file_map[swap_file.name] = swap_file
        files = list(file_map.keys())
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
            path = file_map[sel.get()]
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

    def view_standings(self):
        base = Path(sys.argv[0]).resolve().parent
        csv_path = base / "sorted_standings.csv"
        if not csv_path.exists():
            csv_path = base.parent / "sorted_standings.csv"
        if not csv_path.exists():
            csv_path = Path("sorted_standings.csv")
        if not csv_path.exists():
            messagebox.showinfo("Standings", "No standings file found")
            return

        win = tk.Toplevel(self.root)
        win.title("Standings")
        cols = [
            "Team",
            "Driver",
            "Class",
            "Pos",
            "Class Pos",
            "Laps",
            "Pits",
            "Avg Lap",
            "Best Lap",
            "Last Lap",
            "In Pit",
        ]
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, anchor="center")
        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)

        def load():
            tree.delete(*tree.get_children())
            try:
                with csv_path.open("r", newline="", encoding="utf-8", errors="replace") as f:
                    rows = list(csv.DictReader(f))
                rows = filter_rows(rows)
                # determine order of classes based on their best overall position
                class_leaders = {}
                for r in rows:
                    try:
                        pos = int(r.get("Pos", 0))
                    except Exception:
                        pos = 0
                    cls = r.get("Class", "")
                    if cls not in class_leaders or pos < class_leaders[cls]:
                        class_leaders[cls] = pos
                order = {
                    c: i for i, c in enumerate(sorted(class_leaders, key=class_leaders.get))
                }
                rows.sort(
                    key=lambda r: (
                        order.get(r.get("Class", ""), len(order)),
                        int(r.get("Pos", 0)),
                    )
                )

                def fmt(val: str) -> str:
                    try:
                        num = float(val)
                    except Exception:
                        return val
                    return f"{num:.3f}".rstrip("0").rstrip(".")

                for r in rows:
                    vals = []
                    for c in cols:
                        v = r.get(c, "")
                        if c in {"Best Lap", "Last Lap"}:
                            v = fmt(v)
                        vals.append(v)
                    tree.insert("", "end", values=vals)
            except Exception as e:
                messagebox.showerror("Standings", f"Error reading {csv_path}: {e}")

        ttk.Button(win, text="Refresh", command=load).grid(
            row=1, column=0, columnspan=2, pady=5
        )
        load()

    def view_driver_times(self):
        base = Path(sys.argv[0]).resolve().parent
        csv_path = base / "driver_times.csv"
        if not csv_path.exists():
            csv_path = base.parent / "driver_times.csv"
        if not csv_path.exists():
            csv_path = Path("driver_times.csv")
        if not csv_path.exists():
            messagebox.showinfo("Driver Times", "No driver time file found")
            return

        win = tk.Toplevel(self.root)
        win.title("Driver Times")
        cols = ["Team", "Driver", "Total"]
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, anchor="center")
        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)

        def fmt(sec: str) -> str:
            try:
                val = float(sec)
            except Exception:
                return sec
            h = int(val // 3600)
            m = int((val % 3600) // 60)
            s = int(val % 60)
            return f"{h}:{m:02d}:{s:02d}"

        def load():
            tree.delete(*tree.get_children())
            try:
                with csv_path.open("r", newline="", encoding="utf-8", errors="replace") as f:
                    rows = list(csv.DictReader(f))
                for r in rows:
                    tree.insert(
                        "",
                        "end",
                        values=[
                            r.get("TeamName", r.get("Team", "")),
                            r.get("DriverName", r.get("Driver", "")),
                            r.get("Total Time (h:m:s)")
                            or fmt(r.get("Total Time (sec)", "")),
                        ],
                    )
            except Exception as e:
                messagebox.showerror("Driver Times", f"Error reading {csv_path}: {e}")

        ttk.Button(win, text="Refresh", command=load).grid(
            row=1, column=0, columnspan=2, pady=5
        )
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
            info = filedialog.asksaveasfilename(
                title="Save analysis", defaultextension=".txt"
            )
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

    def _apply_ansi_codes(self, codes: list[str]) -> None:
        for c in codes:
            if c == "0":
                self._current_tags.clear()
            elif c == "1":
                if "bold" not in self._current_tags:
                    self._current_tags.append("bold")
            else:
                colour = ANSI_COLOUR_MAP.get(c)
                if colour:
                    self._current_tags = [
                        t for t in self._current_tags if not t.startswith("fg-")
                    ]
                    self._current_tags.append(f"fg-{colour}")

    def insert_with_ansi(self, text: str) -> None:
        pos = 0
        for m in self._ansi_re.finditer(text):
            if m.start() > pos:
                self.log_box.insert(
                    "end", text[pos : m.start()], tuple(self._current_tags)
                )
            self._apply_ansi_codes(m.group(1).split(";"))
            pos = m.end()
        if pos < len(text):
            self.log_box.insert("end", text[pos:], tuple(self._current_tags))

    def update_log_box(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_box.configure(state="normal")
                self.insert_with_ansi(line)
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
