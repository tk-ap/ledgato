"""Ledgato command-line interface.

Mirrors the terminal in the landing page:

    $ ledgato attestation --agent researcher --release v2.4
    # gating release v2.4 · 3 agents · attack surface signed
    [SIGN ] 00:00:12 github.read verified · attestation #9f31…c2
    [DRIFT] 00:00:44 researcher gained **db.write** · map changed
    [GATE ] 00:00:45 release v2.4 blocked · not re-verified + alert
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .crypto import Signer
from .gate import attest_release
from .ledger import Ledger
from .models import Action, load_policies
from .probes import run_probes, summarize


DEFAULT_CONFIG = "fence.yaml"


def _load_state(config: Path, ledger_file: Path, key_dir: Path):
    signer = Signer()
    if key_dir.exists():
        signer = Signer.load(key_dir)
    else:
        signer.save(key_dir)
    doc = yaml.safe_load(config.read_text()) or {}
    policies = load_policies(doc)
    ledger = Ledger(signer=signer, path=ledger_file)
    if ledger_file.exists():
        ledger = Ledger.load(ledger_file, signer=signer)
    return policies, ledger


def cmd_init(args) -> int:
    target = Path(args.dir)
    target.mkdir(parents=True, exist_ok=True)
    cfg = target / "fence.yaml"
    if not cfg.exists():
        cfg.write_text(_EXAMPLE_FENCE)
    (target / "keys").mkdir(exist_ok=True)
    Signer().save(target / "keys")
    print(f"[init ] scaffolded Ledgato workspace at {target}/")
    print(f"        - {cfg.name}")
    print(f"        - keys/ledgato_private.pem")
    print("Run: ledgato attestation --config fence.yaml --agent ops-agent --release v1.0")
    return 0


def cmd_check(args) -> int:
    policies, _ = _load_state(Path(args.config).resolve(), Path(args.ledger), Path(args.keys))
    policy = policies.get(args.agent)
    if not policy:
        print(f"[check] no policy for agent '{args.agent}'")
        return 1
    action = Action(tool=args.tool, impact=args.impact, domain=args.domain)
    from .engine import evaluate_action

    d = evaluate_action(policy, action)
    print(f"[check] agent={args.agent} tool={action.tool} impact={action.impact}")
    print(f"        -> {d.reason}")
    return 0 if d.allow else 1


def cmd_probe(args) -> int:
    policies, _ = _load_state(Path(args.config).resolve(), Path(args.ledger), Path(args.keys))
    policy = policies.get(args.agent)
    if not policy:
        print(f"[probe] no policy for agent '{args.agent}'")
        return 1
    summary = summarize(run_probes(policy))
    print(f"[probe] agent={args.agent} · {summary['passed']}/{summary['total']} probes held")
    for r in summary["results"]:
        flag = "PASS" if r["passed"] else "GAP "
        print(f"  [{flag}] {r['name']:<20} expected_deny={r['expected_deny']} -> allow={r['decision']['allow']}")
    if summary["gap"]:
        print(f"[probe] CONTAINMENT GAPS: {', '.join(summary['gap'])}")
        return 1
    return 0


def cmd_attestation(args) -> int:
    policies, ledger = _load_state(Path(args.config).resolve(), Path(args.ledger), Path(args.keys))
    policy = policies.get(args.agent)
    if not policy:
        print(f"[attest] no policy for agent '{args.agent}'")
        return 1
    actions = [Action(tool=t, impact="readonly") for t in sorted(policy.allow_tools)]
    # include a drift in observed scope to mirror the landing-page demo
    observed = None
    if args.drift:
        observed = set(policy.allow_tools) | {"db.write"}
    print(f"# gating release {args.release} · agent {args.agent} · attack surface signed")
    result = attest_release(ledger, policy, args.release, actions, observed_scope=observed)
    for a in result.attestations:
        mark = "SIGN" if a["decision"] else "DENY"
        print(f"[{mark:4}] {a['action']:<16} verified · attestation #{a['attestation']}")
    for g in result.gap:
        print(f"[DRIFT] {args.agent} → {g} · map changed")
    if result.verdict == "APPROVED":
        print(f"[GATE ] release {args.release} APPROVED · signed + verified")
    else:
        print(f"[GATE ] release {args.release} BLOCKED · not re-verified + alert")
    ok, errs = ledger.verify_chain()
    print(f"[chain] ledger integrity: {'OK' if ok else 'BROKEN ' + str(errs)} ({len(ledger.entries)} entries)")
    return 0 if result.verdict == "APPROVED" else 1


def cmd_ledger(args) -> int:
    signer = Signer()
    if Path(args.keys).exists():
        signer = Signer.load(Path(args.keys))
    ledger = Ledger.load(Path(args.ledger), signer=signer)
    ok, errs = ledger.verify_chain()
    print(f"[ledger] {len(ledger.entries)} entries · chain integrity: {'OK' if ok else 'BROKEN'}")
    for e in ledger.entries[-args.tail:]:
        print(f"  #{e.index:<4} {e.decision:<8} {e.agent:<12} {e.action or '-'}  {e.hash[:12]}")
    if not ok:
        for er in errs:
            print("  !!", er)
        return 1
    return 0


def cmd_api(args) -> int:
    import uvicorn

    from .api import app

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ledgato", description="Ledgato — release gate + signed evidence for agentic AI")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="scaffold a Ledgato workspace")
    s.add_argument("--dir", default=".")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("check", help="check one action against an agent's scope")
    s.add_argument("--agent", required=True)
    s.add_argument("--tool", required=True)
    s.add_argument("--impact", default="readonly")
    s.add_argument("--domain")
    _add_state(s)
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("probe", help="run the adversarial probe battery for an agent")
    s.add_argument("--agent", required=True)
    _add_state(s)
    s.set_defaults(func=cmd_probe)

    s = sub.add_parser("attestation", help="gate a release for an agent (signed evidence)")
    s.add_argument("--agent", required=True)
    s.add_argument("--release", required=True)
    s.add_argument("--drift", action="store_true", help="simulate a live-map drift")
    _add_state(s)
    s.set_defaults(func=cmd_attestation)

    s = sub.add_parser("ledger", help="verify the attestation ledger")
    _add_state(s)
    s.add_argument("--tail", type=int, default=8)
    s.set_defaults(func=cmd_ledger)

    s = sub.add_parser("api", help="run the Ledgato API server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    _add_state(s)
    s.set_defaults(func=cmd_api)
    return p


def _add_state(p) -> None:
    p.add_argument("--config", default=_CONFIG, help="fence.yaml path")
    p.add_argument("--ledger", default=_LEDGER, help="ledger file (jsonl)")
    p.add_argument("--keys", default=_KEYS, help="key directory")


_CONFIG = "fence.yaml"
_LEDGER = "ledger.jsonl"
_KEYS = "keys"

_EXAMPLE_FENCE = """# fence.yaml · agent \"ops-agent\" · attack surface as code
policies:
  - agent: ops-agent
    allow_tool:
      - read.docs
      - search
      - github.read
    deny_tool:
      - db.write
    impact_max: readonly
    data_domains:
      - sandbox::*
    on_deny:
      - alert
      - human_review
  - agent: researcher
    allow_tool:
      - read.docs
      - search
      - github.read
      - docs.write
    deny_tool:
      - db.write
      - exec.shell
    impact_max: write
    data_domains:
      - sandbox::*
      - docs::*
    on_deny:
      - alert
"""


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())