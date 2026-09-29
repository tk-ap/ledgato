import importlib.util
from pathlib import Path


def load_helper():
    source = Path(__file__).resolve().parents[2] / "ops" / "ledgato_host_op.py"
    spec = importlib.util.spec_from_file_location("ledgato_host_op_test", source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_cli_rejects_unknown_or_extra_operations(capsys):
    helper = load_helper()

    assert helper.main(["shell"]) == 64
    assert helper.main(["agentos-runtime-status", "extra"]) == 64

    output = capsys.readouterr().out
    assert "expected exactly one allowlisted operation" in output


def test_operation_dispatch_has_no_generic_shell_path(monkeypatch):
    helper = load_helper()
    monkeypatch.setattr(helper, "_require_root", lambda: None)
    monkeypatch.setattr(
        helper,
        "_status",
        lambda: {"operation": "agentos-runtime-status", "healthy": True},
    )

    status = helper.run_operation("agentos-runtime-status")
    assert status["healthy"] is True

    try:
        helper.run_operation("systemctl")
    except helper.HostOperationError as exc:
        assert "unsupported operation" in str(exc)
    else:
        raise AssertionError("unknown operation unexpectedly executed")


def test_source_file_must_not_be_symlink(monkeypatch, tmp_path):
    helper = load_helper()
    source_root = tmp_path / "source"
    source_root.mkdir()
    real = source_root / "real.service"
    real.write_text("[Unit]\n")
    link = source_root / "link.service"
    link.symlink_to(real)

    monkeypatch.setattr(helper, "SOURCE_ROOT", source_root)
    monkeypatch.setattr(helper, "_assert_root_owned_path", lambda path: None)

    try:
        helper._validated_source("link.service")
    except helper.HostOperationError as exc:
        assert "non-symlink" in str(exc)
    else:
        raise AssertionError("symlink source unexpectedly accepted")


def test_activation_installs_only_fixed_units_and_fixed_systemd_actions(monkeypatch):
    helper = load_helper()
    calls = []

    monkeypatch.setattr(helper, "_ensure_source", lambda: "abc123")
    monkeypatch.setattr(helper, "_install_units", lambda: calls.append(("install_units",)))
    monkeypatch.setattr(
        helper,
        "_run",
        lambda argv, **kwargs: calls.append(tuple(argv)) or type(
            "Result", (), {"returncode": 0, "stdout": "", "stderr": ""}
        )(),
    )
    monkeypatch.setattr(
        helper,
        "_status",
        lambda mirror_sha=None: {
            "operation": "agentos-runtime-status",
            "status": "ok",
            "healthy": True,
            "mirror_sha": mirror_sha,
            "runtime_sha": mirror_sha,
        },
    )

    result = helper._activate()
    assert result["activated"] is True

    flat = [" ".join(call) for call in calls if call and call[0] != "install_units"]
    joined = "\n".join(flat)
    assert "daemon-reload" in joined
    assert "agentos-runtime-checkout.service" in joined
    assert "agentos-runtime-checkout.timer" in joined
    assert "agentos-board-projection.timer" in joined
    assert "agentos-board-projection.service" in joined
    assert "ssh" not in joined
    assert "tailscale" not in joined


def test_runtime_sync_is_installed_before_systemd_verify(monkeypatch, tmp_path):
    helper = load_helper()
    calls = []

    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "runtime").mkdir()
    sync = source_root / "runtime" / "agentos_runtime_sync.sh"
    sync.write_text("#!/usr/bin/env bash\nexit 0\n")

    unit_dir = source_root / "runtime" / "systemd"
    unit_dir.mkdir()
    unit = unit_dir / "agentos-runtime-checkout.service"
    unit.write_text("[Service]\nExecStart=/usr/local/libexec/agentos-runtime-sync\n")

    monkeypatch.setattr(helper, "SOURCE_ROOT", source_root)
    runtime_sync_target = tmp_path / "installed" / "agentos-runtime-sync"
    monkeypatch.setattr(
        helper,
        "RUNTIME_EXECUTABLES",
        (("runtime/agentos_runtime_sync.sh", str(runtime_sync_target)),),
    )
    monkeypatch.setattr(
        helper,
        "VERIFY_UNITS",
        ("runtime/systemd/agentos-runtime-checkout.service",),
    )
    monkeypatch.setattr(helper, "UNIT_FILES", ())
    monkeypatch.setattr(helper, "_assert_root_owned_path", lambda path: None)
    monkeypatch.setattr(
        helper,
        "_run",
        lambda argv, **kwargs: calls.append(tuple(argv)) or type(
            "Result", (), {"returncode": 0, "stdout": "", "stderr": ""}
        )(),
    )

    helper._install_units()

    install_i = next(
        i for i, call in enumerate(calls)
        if call[:2] == ("/usr/bin/install", "-o")
        and str(runtime_sync_target) in call
    )
    verify_i = next(
        i for i, call in enumerate(calls)
        if call[:2] == ("/usr/bin/systemd-analyze", "verify")
    )
    assert install_i < verify_i


def test_runtime_status_uses_only_fixed_safe_directory(monkeypatch, tmp_path):
    helper = load_helper()
    runtime_root = tmp_path / "runtime"
    (runtime_root / ".git").mkdir(parents=True)

    calls = []
    monkeypatch.setattr(helper, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(
        helper,
        "_run",
        lambda argv, **kwargs: calls.append(tuple(argv)) or type(
            "Result", (), {"returncode": 0, "stdout": "abc\n", "stderr": ""}
        )(),
    )

    assert helper._runtime_git_text("rev-parse", "HEAD") == "abc"
    assert calls
    cmd = calls[0]
    assert cmd[0] == "/usr/bin/git"
    assert cmd[1] == "-c"
    assert cmd[2] == f"safe.directory={runtime_root}"
    assert cmd[3:5] == ("-C", str(runtime_root))
    assert "--global" not in cmd


def test_sudoers_template_contains_exact_commands_without_wildcards():
    installer = (
        Path(__file__).resolve().parents[2] / "ops" / "install_ledgato_host_op.sh"
    ).read_text()

    assert "${TARGET} agentos-runtime-status" in installer
    assert "${TARGET} agentos-runtime-activate" in installer
    assert "${TARGET} *" not in installer
    assert "NOPASSWD: ALL" not in installer


def test_installer_refuses_mutable_noncanonical_source_by_contract():
    installer = (
        Path(__file__).resolve().parents[2] / "ops" / "install_ledgato_host_op.sh"
    ).read_text()

    assert "stat -c '%u'" in installer
    assert "https://github.com/tk-ap/ledgato.git" in installer
    assert "branch --show-current" in installer
    assert "status --porcelain" in installer
    assert "merge-base --is-ancestor HEAD origin/main" in installer
    assert "merge --ff-only origin/main" in installer

def test_private_agentos_source_staging_never_exports_github_credentials():
    stage = (
        Path(__file__).resolve().parents[2] / "ops" / "stage_agentos_source.sh"
    ).read_text()

    assert 'git -C "${SOURCE_WORKTREE}" fetch --prune origin main' in stage
    assert "/var/lib/ledgato/agent-os-main.bundle" in stage
    assert "sudo install -o root -g root -m 0644" in stage
    assert "GITHUB_TOKEN" not in stage
    assert "GH_TOKEN" not in stage
    assert "AGENT_OS_LEDGATO_AGENT_TOKEN" not in stage


def test_root_helper_consumes_staged_bundle_not_github_network():
    helper = (
        Path(__file__).resolve().parents[2] / "ops" / "ledgato_host_op.py"
    ).read_text()

    assert 'SOURCE_BUNDLE = Path("/var/lib/ledgato/agent-os-main.bundle")' in helper
    assert '"bundle", "list-heads"' in helper
    assert 'str(SOURCE_BUNDLE)' in helper
    assert '"refs/heads/main:refs/remotes/staged/main"' in helper
    assert '"/usr/local/libexec/agentos-runtime-sync"' in helper
    assert '"fetch", "origin", "main"' not in helper
    assert 'GITHUB_TOKEN' not in helper
    assert 'GH_TOKEN' not in helper
