import json
import subprocess

import pytest

from ledgato.adapters.host import (
    HostActionAdapter,
    RUNTIME_ACTIVATE_TOOL,
    RUNTIME_STATUS_TOOL,
)
from ledgato.models import Action


class Runner:
    def __init__(self):
        self.calls = []
        self.results = {
            "agentos-runtime-status": {
                "operation": "agentos-runtime-status",
                "status": "ok",
                "healthy": True,
                "runtime_sha": "abc123",
            },
            "agentos-runtime-activate": {
                "operation": "agentos-runtime-activate",
                "status": "ok",
                "healthy": True,
                "activated": True,
                "runtime_sha": "abc123",
            },
        }

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), dict(kwargs)))
        operation = argv[-1]
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(self.results[operation]),
            stderr="",
        )


def adapter(runner):
    return HostActionAdapter(
        resource="ashwood-host-01",
        helper_path="/usr/local/libexec/ledgato-host-op",
        sudo_path="/usr/bin/sudo",
        validate_helper=False,
        runner=runner,
    )


def test_status_uses_one_fixed_noninteractive_helper_command():
    runner = Runner()
    result = adapter(runner).execute(
        Action(
            tool=RUNTIME_STATUS_TOOL,
            impact="readonly",
            domain="ashwood-host-01",
        )
    )

    assert result.executed is True
    assert result.result["healthy"] is True
    assert runner.calls[0][0] == [
        "/usr/bin/sudo",
        "-n",
        "/usr/local/libexec/ledgato-host-op",
        "agentos-runtime-status",
    ]


def test_activation_never_forwards_caller_arguments():
    runner = Runner()
    target = adapter(runner)

    with pytest.raises(ValueError, match="do not accept caller parameters"):
        target.execute(
            Action(
                tool=RUNTIME_ACTIVATE_TOOL,
                impact="write",
                domain="ashwood-host-01",
                params={"unit": "ssh.service", "command": "anything"},
            )
        )

    assert runner.calls == []


def test_unlisted_host_action_is_rejected_before_sudo():
    runner = Runner()

    with pytest.raises(ValueError, match="not allowlisted"):
        adapter(runner).execute(
            Action(
                tool="host.shell.exec",
                impact="write",
                domain="ashwood-host-01",
            )
        )

    assert runner.calls == []


def test_wrong_host_or_impact_is_rejected_before_sudo():
    runner = Runner()
    target = adapter(runner)

    with pytest.raises(ValueError, match="domain must exactly match"):
        target.execute(
            Action(
                tool=RUNTIME_ACTIVATE_TOOL,
                impact="write",
                domain="different-host",
            )
        )
    with pytest.raises(ValueError, match="requires impact 'write'"):
        target.execute(
            Action(
                tool=RUNTIME_ACTIVATE_TOOL,
                impact="readonly",
                domain="ashwood-host-01",
            )
        )

    assert runner.calls == []


def test_denied_verification_never_touches_helper():
    runner = Runner()
    result = adapter(runner).verify_denied(
        Action(
            tool=RUNTIME_ACTIVATE_TOOL,
            impact="write",
            domain="ashwood-host-01",
        )
    )

    assert result["helper_invoked"] is False
    assert runner.calls == []


def test_post_action_verification_uses_only_fixed_status_operation():
    runner = Runner()
    target = adapter(runner)
    receipt = target.execute(
        Action(
            tool=RUNTIME_ACTIVATE_TOOL,
            impact="write",
            domain="ashwood-host-01",
        )
    )
    verified = target.verify(
        Action(
            tool=RUNTIME_ACTIVATE_TOOL,
            impact="write",
            domain="ashwood-host-01",
        ),
        receipt,
    )

    assert verified["verified"] is True
    assert [call[0][-1] for call in runner.calls] == [
        "agentos-runtime-activate",
        "agentos-runtime-status",
    ]


def test_malformed_helper_output_fails_closed():
    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="not-json", stderr="")

    target = HostActionAdapter(
        resource="ashwood-host-01",
        validate_helper=False,
        runner=runner,
    )
    with pytest.raises(RuntimeError, match="malformed JSON"):
        target.execute(
            Action(
                tool=RUNTIME_STATUS_TOOL,
                impact="readonly",
                domain="ashwood-host-01",
            )
        )


def test_host_adapter_env_is_explicit_opt_in(monkeypatch):
    import ledgato.api as api

    for key in (
        "LEDGATO_HOST_OP_ENABLED",
        "LEDGATO_HOST_OP_RESOURCE",
        "LEDGATO_HOST_OP_HELPER",
    ):
        monkeypatch.delenv(key, raising=False)

    assert "host" not in api._default_adapters_from_env()

    monkeypatch.setenv("LEDGATO_HOST_OP_ENABLED", "1")
    with pytest.raises(RuntimeError, match="LEDGATO_HOST_OP_RESOURCE"):
        api._default_adapters_from_env()


def test_host_adapter_env_binds_fixed_resource(monkeypatch):
    import ledgato.api as api

    captured = {}

    class StubHost:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(api, "HostActionAdapter", StubHost)
    monkeypatch.setenv("LEDGATO_HOST_OP_ENABLED", "true")
    monkeypatch.setenv("LEDGATO_HOST_OP_RESOURCE", "ashwood-host-01")
    monkeypatch.setenv("LEDGATO_HOST_OP_HELPER", "/usr/local/libexec/ledgato-host-op")

    adapters = api._default_adapters_from_env()
    assert "host" in adapters
    assert captured["resource"] == "ashwood-host-01"
    assert captured["helper_path"] == "/usr/local/libexec/ledgato-host-op"
    assert captured["validate_helper"] is True


def test_gateway_deny_never_invokes_privileged_helper(tmp_path):
    from fastapi.testclient import TestClient

    from ledgato.api import create_app
    from ledgato.principals import PrincipalRegistry

    fence = tmp_path / "fence.yaml"
    fence.write_text(
        """
policies:
  - agent: agent-os-workspace
    allow_tool:
      - host.agentos.runtime.status
    impact_max: write
    data_domains:
      - ashwood-host-01
"""
    )
    runner = Runner()
    target = adapter(runner)
    app = create_app(
        config_path=fence,
        ledger_path=tmp_path / "ledger.jsonl",
        key_dir=tmp_path / "keys",
        approvals_path=tmp_path / "approvals.json",
        authority_path=tmp_path / "authority.json",
        adapters={"host": target},
        principals=PrincipalRegistry(
            [("agent-os-workspace", "agent", "agent-secret")]
        ),
    )
    client = TestClient(app)

    denied = client.post(
        "/v1/gateway/execute",
        headers={"Authorization": "Bearer agent-secret"},
        json={
            "agent": "agent-os-workspace",
            "adapter": "host",
            "task_id": "proof-1",
            "action": {
                "tool": RUNTIME_ACTIVATE_TOOL,
                "impact": "write",
                "domain": "ashwood-host-01",
            },
        },
    )

    assert denied.status_code == 200
    assert denied.json()["status"] == "DENY"
    assert denied.json()["executed"] is False
    assert runner.calls == []


def test_gateway_approval_pauses_before_helper_and_runs_once_after_owner_approval(tmp_path):
    from fastapi.testclient import TestClient

    from ledgato.api import create_app
    from ledgato.principals import PrincipalRegistry

    fence = tmp_path / "fence.yaml"
    fence.write_text(
        """
policies:
  - agent: agent-os-workspace
    allow_tool:
      - host.agentos.runtime.activate
    approve_tool:
      - host.agentos.runtime.activate
    impact_max: write
    data_domains:
      - ashwood-host-01
"""
    )
    runner = Runner()
    target = adapter(runner)
    app = create_app(
        config_path=fence,
        ledger_path=tmp_path / "ledger.jsonl",
        key_dir=tmp_path / "keys",
        approvals_path=tmp_path / "approvals.json",
        authority_path=tmp_path / "authority.json",
        adapters={"host": target},
        principals=PrincipalRegistry(
            [
                ("agent-os-workspace", "agent", "agent-secret"),
                ("tk", "approver", "owner-secret"),
            ]
        ),
    )
    client = TestClient(app)

    pending = client.post(
        "/v1/gateway/execute",
        headers={"Authorization": "Bearer agent-secret"},
        json={
            "agent": "agent-os-workspace",
            "adapter": "host",
            "task_id": "agentos-runtime-autonomy-reboot-proof",
            "idempotency_key": "host-activation-proof",
            "action": {
                "tool": RUNTIME_ACTIVATE_TOOL,
                "impact": "write",
                "domain": "ashwood-host-01",
            },
        },
    )
    assert pending.status_code == 200
    assert pending.json()["status"] == "APPROVE"
    assert runner.calls == []

    approval_id = pending.json()["approval"]["id"]
    resumed = client.post(
        f"/v1/approvals/{approval_id}/approve-and-resume",
        headers={"Authorization": "Bearer owner-secret"},
        json={"decided_by": "tk", "jit_ttl_seconds": 60},
    )

    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["execution"]["status"] == "ALLOW"
    assert [call[0][-1] for call in runner.calls] == [
        "agentos-runtime-activate",
        "agentos-runtime-status",
    ]

    replay = client.post(
        f"/v1/approvals/{approval_id}/approve-and-resume",
        headers={"Authorization": "Bearer owner-secret"},
        json={"decided_by": "tk", "jit_ttl_seconds": 60},
    )
    assert replay.status_code == 409
    assert [call[0][-1] for call in runner.calls] == [
        "agentos-runtime-activate",
        "agentos-runtime-status",
    ]
