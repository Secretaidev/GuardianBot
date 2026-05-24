"""Convenience wrapper — run GuardianBot from project root."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bot.__main__ import main

if __name__ == "__main__":
    main()
