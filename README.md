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
