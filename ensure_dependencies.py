"""Utilities for ensuring runtime dependencies are installed."""

from __future__ import annotations

import importlib
import subprocess
import sys
from typing import Optional, Tuple


def _parse_spec(spec: str) -> Tuple[str, Optional[str]]:
    """Return package name and version from a spec like ``name==1.0``."""
    if "==" in spec:
        name, ver = spec.split("==", 1)
        return name, ver
    return spec, None


def _install(package: str, version: Optional[str]) -> subprocess.CompletedProcess:
    """Run pip install for the given package and version."""
    spec = package + (f"=={version}" if version else "")
    cmd = [sys.executable, "-m", "pip", "install", spec]
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def ensure_package(pkg: str, version: str | None = None) -> None:
    """Ensure that *pkg* is available, installing it when missing or mismatched."""
    if version is None:
        pkg, version = _parse_spec(pkg)

    try:
        module = importlib.import_module(pkg)
        if version and getattr(module, "__version__", None) != version:
            raise ImportError
    except ImportError:
        print(f"Package '{pkg}' not found.")
        spec = pkg + (f"=={version}" if version else "")
        print(f"Installing '{spec}'...")
        try:
            _install(pkg, version)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            err = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
            print(f"Installation failed: {err.strip()}")
            raise RuntimeError(err.strip()) from exc
        print("Successfully installed.")
        importlib.invalidate_caches()
        sys.modules.pop(pkg, None)
        module = importlib.import_module(pkg)
        if version and getattr(module, "__version__", None) != version:
            raise RuntimeError(f"Failed to install '{pkg}=={version}'.")
    else:
        print(f"Package '{pkg}' found.")


def main(args: list[str] | None = None) -> None:
    """Install packages specified on the command line."""
    args = sys.argv[1:] if args is None else args
    for spec in args:
        name, ver = _parse_spec(spec)
        ensure_package(name, ver)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    main()
