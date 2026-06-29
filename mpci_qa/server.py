"""
Production-ready MPCI Q&A Server with proper configuration.
Uses environment variables or .env file for settings.
"""

import os
import sys
import uvicorn
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def load_env_file():
    """Load simple KEY=VALUE settings from .env if python-dotenv is not installed."""
    for env_path in (PROJECT_ROOT / ".env", Path(__file__).parent / ".env"):
        if not env_path.exists():
            continue

        print(f"Loading configuration from {env_path}")
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
        return


load_env_file()

from mpci_qa.app import app

if __name__ == "__main__":
    host = os.environ.get("MPCI_HOST", "0.0.0.0")
    port = int(os.environ.get("MPCI_PORT", "8000"))
    workers = int(os.environ.get("MPCI_WORKERS", "1"))

    print(f"MPCI Q&A Server starting on {host}:{port}")
    print("Knowledge base: UAE MPCI Business Specification V1.0")
    print(f"LLM: {os.environ.get('MPCI_LLM_TYPE', 'template')}")

    uvicorn.run(
        "mpci_qa.server:app",
        host=host,
        port=port,
        workers=workers,
        log_level="info"
    )
