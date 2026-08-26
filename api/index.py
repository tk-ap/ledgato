"""Vercel entry point. Runtime files live in /tmp and are intentionally ephemeral."""

from pathlib import Path
import sys

from fastapi import FastAPI

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from ledgato.api import create_app  # noqa: E402


engine = create_app(
    config_path=ROOT / "fence.yaml",
    ledger_path="/tmp/ledgato-ledger.jsonl",
    key_dir="/tmp/ledgato-keys",
)

app = FastAPI(title="Ledgato Preview API")
app.mount("/api", engine)
