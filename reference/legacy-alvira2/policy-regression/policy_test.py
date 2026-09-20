"""Policy regression tests — "clawpatrol test".

A Claw Patrol-style ``test`` harness that replays recorded agent actions
against the policy and fails the build whenever a policy change flips a
verdict.

Workflow
--------
1. ``ledgato test --record <dir>`` reads the current agents/scopes from
   ``fence.yaml``, runs ``engine.evaluate`` (and optionally the canonical
   probes) against them, and writes JSON fixtures capturing each
   ``(agent, tool, impact, data_domain) -> decision`` into
   ``<dir>/fixtures/``.
2. ``ledgato test <dir>`` loads those fixtures, re-runs ``engine.evaluate``
   against the *current* ``fence.yaml``, and asserts every current verdict
   still matches the recorded one. Any flip prints a readable diff and the
   command exits non-zero (build fails). If all match it prints a summary and
   exits 0.

The harness is read-only and memory-light: it never touches the ledger or an
HTTP server, and it reuses the existing allow/deny logic from ``engine`` /
``models`` rather than reimplementing evaluation.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict

from .engine import evaluate
from .models import parse_fence
from .probes import PROBES


@dataclass
class Case:
    """A single recorded (agent, tool, impact, data_domain) action case."""

    agent: str
    tool: str
    impact: str
    data_domain: str | None
    decision: str  # expected verdict recorded from the baseline policy
    source: str = "case"  # allow | deny | outside | escalate | probe

    def label(self) -> str:
        """A compact human-readable case identifier for diffs."""
        return f"{self.agent}.{self.tool}"


def generate_cases(policy, include_probes: bool = False) -> list[Case]:
    """Derive representative action cases from the declared scope.

    For every agent we record the behaviours the fence *intends*:
      * each allowed tool at its ceiling impacts + a valid data domain (ALLOW),
      * each explicitly denied tool (DENY),
      * an out-of-scope tool (DENY),
      * an impact escalation of an allowed tool (DENY),
      * optionally every canonical probe fanned out to the agent (DENY).
    """
    cases: list[Case] = []
    for name, pol in (policy.agents or {}).items():
        domains = sorted(pol.data_domains or [])
        dom = domains[0] if domains else None
        for tool in sorted(pol.allow or set()):
            cases.append(
                Case(name, tool, pol.max_impact, dom, "ALLOW", source="allow")
            )
        for tool in sorted(pol.deny or set()):
            cases.append(
                Case(name, tool, pol.max_impact, dom, "DENY", source="deny")
            )
        # Out-of-scope command straight to DENY.
        cases.append(
            Case(name, "shell.exec", pol.max_impact, dom, "DENY", source="outside")
        )
        # Escalation: an allowed tool above the impact ceiling -> DENY.
        if pol.allow:
            tool = sorted(pol.allow)[0]
            cases.append(
                Case(name, tool, "admin", dom, "DENY", source="escalate")
            )
        if include_probes:
            for probe in PROBES:
                cases.append(
                    Case(
                        name,
                        probe.tool,
                        probe.impact,
                        probe.data_domain,
                        "DENY",
                        source="probe",
                    )
                )
    return cases


def record_fixtures(
    fence_path: str, fixtures_dir: str, include_probes: bool = False
) -> int:
    """Run ``engine.evaluate`` over derived cases and write JSON fixtures.

    Returns the number of cases recorded.
    """
    policy = parse_fence(fence_path)
    cases = generate_cases(policy, include_probes=include_probes)
    os.makedirs(fixtures_dir, exist_ok=True)
    by_agent: dict[str, list[dict]] = {}
    for case in cases:
        decision, _ = evaluate(
            policy, case.agent, tool=case.tool,
            impact=case.impact, data_domain=case.data_domain,
        )
        # Record the decision the *current* policy produces — this is the
        # expected verdict the replay will later guard against flips.
        case.decision = decision
        by_agent.setdefault(case.agent, []).append(asdict(case))
    for agent, records in by_agent.items():
        path = os.path.join(fixtures_dir, f"{agent}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"agent": agent, "cases": records}, fh, indent=2)
    return len(cases)


def load_fixtures(fixtures_dir: str) -> list[Case]:
    """Load all JSON fixtures under ``fixtures_dir`` into a flat Case list."""
    cases: list[Case] = []
    if not os.path.isdir(fixtures_dir):
        return cases
    for name in sorted(os.listdir(fixtures_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(fixtures_dir, name), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for record in data.get("cases", []):
            cases.append(Case(**record))
    return cases


def run_policy_test(fence_path: str, fixtures_dir: str) -> tuple[int, list[dict]]:
    """Replay fixtures against the current ``fence.yaml``.

    Returns ``(num_checked, mismatches)`` where each mismatch is a dict with
    the fixture's case fields plus ``want`` (recorded) and ``got`` (current).
    """
    policy = parse_fence(fence_path)
    fixtures = load_fixtures(fixtures_dir)
    mismatches: list[dict] = []
    for case in fixtures:
        got, _ = evaluate(
            policy, case.agent, tool=case.tool,
            impact=case.impact, data_domain=case.data_domain,
        )
        if got != case.decision:
            mismatches.append(
                {
                    "agent": case.agent,
                    "tool": case.tool,
                    "impact": case.impact,
                    "data_domain": case.data_domain,
                    "source": case.source,
                    "want": case.decision,
                    "got": got,
                }
            )
    return len(fixtures), mismatches


def print_mismatch(m: dict) -> None:
    """Print a single policy flip in a readable one-line diff format."""
    extra = f" source={m['source']}" if m.get("source") else ""
    print(
        f"  want={m['want']} got={m['got']}  case={m['tool']} "
        f"agent={m['agent']}{extra}"
    )
