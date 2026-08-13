"""Ledgato — a release gate + signed-evidence layer for agentic AI."""

from .engine import Decision, detect_drift, evaluate_action
from .gate import GateResult, attest_release
from .ledger import Ledger, LedgerEntry
from .models import Action, Policy, load_policies, parse_policy
from .probes import run_probes, summarize

__version__ = "0.1.0"
__all__ = [
    "Action",
    "Policy",
    "Ledger",
    "LedgerEntry",
    "Decision",
    "GateResult",
    "attest_release",
    "detect_drift",
    "evaluate_action",
    "load_policies",
    "parse_policy",
    "run_probes",
    "summarize",
    "__version__",
]