#!/usr/bin/env bash
# Simple setup script for the EEC utilities
set -e
PYTHON=${PYTHON:-python3}

# create venv if not present
if [ ! -d .venv ]; then
    $PYTHON -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

echo "Environment ready. Activate with 'source .venv/bin/activate'"
