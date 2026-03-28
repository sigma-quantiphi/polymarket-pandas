"""Polymarket Pandas Explorer — Streamlit entry point."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """CLI entry point: ``polymarket-explore``."""
    app_dir = Path(__file__).parent
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app_dir / "home.py")],
        check=True,
    )


if __name__ == "__main__":
    main()
