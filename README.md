# EEC

A collection of utilities for logging and displaying data from iRacing AI races. The scripts were written for the **Eorzean Endurance Championship** and include tooling to track pit stops, driver swaps and live standings.

## Features

- **ai_standings_logger.py** – periodically records session standings to `standings_log.csv`.
- **pitstop_logger_enhanced.py** – tracks stints and pit stops, writing results to `pitstop_log.csv` and updating `live_standings_overlay.html`.
- **standings_sorter.py** – produces `sorted_standings.csv` so the overlay can show the latest order per class.
- **race_data_runner.py** – helper script that launches all of the above and restarts them if they stop.

## Requirements

Python 3.9 or newer with the packages `pandas`, `colorama` and `irsdk` installed.

```bash
pip install pandas colorama irsdk
```

## Usage

Run the race data runner which spawns the loggers and sorter:

```bash
python race_data_runner.py
```

This creates CSV log files in the repository directory and writes console output to the `logs/` folder. The `standings.html` file reads `sorted_standings.csv` and together with `standings.js` and `standings.css` provides a live overlay you can open in a browser or streaming tool.

Logos and spec maps under `Logos/` and `SpecMaps/` contain the Final Fantasy XIV themed assets used for the championship.

## GUI

A basic Tkinter interface is provided in `race_gui.py`.  It lets you start and stop the logging utilities, shows the current iRacing connection status and has buttons to reset or save the log files.  If the optional `openai` package is installed and an `OPENAI_API_KEY` environment variable is set, the GUI can send the logs to ChatGPT and store the resulting analysis in a text file.

Run it with:

```bash
python race_gui.py
```

### Building an executable

You can create a standalone Windows executable using [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile race_gui.py
```

The resulting `dist/race_gui.exe` will include all scripts and can be run without Python installed.
