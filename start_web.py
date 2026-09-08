#!/usr/bin/env python
"""Start the ContentForge web interface at http://localhost:8000."""
import sys
from pathlib import Path


def main() -> None:
    if not Path(".env").exists():
        print("No .env file found. Copy ENV_TEMPLATE.txt to .env and add your API keys.")
    print("Starting ContentForge on http://localhost:8000  (Ctrl+C to stop)")
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is not installed. Run: pip install -e .")
        sys.exit(1)
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
