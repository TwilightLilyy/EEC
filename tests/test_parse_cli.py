import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from race_gui import parse_cli

import argparse


def _ns(**kwargs) -> argparse.Namespace:
    ns = argparse.Namespace()
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


def test_parse_cli_defaults():
    assert parse_cli([]) == _ns(debug=False, debug_shell=False, classic_theme=False, no_openai=False, db="eec_log.db", time_left=None)


def test_parse_cli_all_flags():
    args = ["--debug", "--debug-shell", "--classic-theme", "--no-openai", "--db", "foo.db", "--time-left", "1:00:00"]
    assert parse_cli(args) == _ns(debug=True, debug_shell=True, classic_theme=True, no_openai=True, db="foo.db", time_left=3600)


def test_parse_cli_bug_repro():
    parse_cli(["C:\\path\\race_data_runner.py", "--db", "eec_log.db"])


def test_parse_cli_mixed_unknown():
    ns = parse_cli(["--debug", "--foo", "extra.txt", "--db", "bar.db"])
    assert ns == _ns(debug=True, debug_shell=False, classic_theme=False, no_openai=False, db="bar.db", time_left=None)
