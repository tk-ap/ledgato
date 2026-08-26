"""Vercel entry point. Runtime files live in /tmp and are intentionally ephemeral."""

from pathlib import Path

from fastapi import FastAPI

from ledgato.api import create_app


ROOT = Path(__file__).resolve().parent.parent
engine = create_app(
    config_path=ROOT / "fence.yaml",
    ledger_path="/tmp/ledgato-ledger.jsonl",
    key_dir="/tmp/ledgato-keys",
)

app = FastAPI(title="Ledgato Preview API")
app.mount("/api", engine)
