#!/usr/bin/env python3
"""Prove a film task and score scenes against it. `python tools/task-check.py` with no arguments prints the commands."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task_check import cli  # noqa: E402

if __name__ == '__main__':
    sys.exit(cli.main())
