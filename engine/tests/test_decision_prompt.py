from ledgato.approvals import Approval
from ledgato.decision_prompt import from_approval, render_text


def approval(**overrides):
    data = {
        "id": "approval_fixture123",
        "agent": "release-agent",
        "task_id": "task-7",
        "adapter": "github",
        "action": {
            "tool": "github.pull.merge",
            "domain": "repo::example",
            "impact": "write",
            "intent": "merge reviewed change",
            "params": {"pull_number": 7, "access_token": "secret-value"},
        },
        "grant_id": None,
        "requested_at": "2026-09-26T19:00:00+00:00",
        "requested_by": "agent-os",
        "decision_context": {"reason": "APPROVE: protected merge requires an owner"},
    }
    data.update(overrides)
    return Approval(**data)


def test_prompt_redacts_sensitive_display_facts_but_binds_exact_parameters():
    prompt = from_approval(approval()).to_dict()
    facts = {row["key"]: row for row in prompt["requested_action"]["facts"]}
    assert facts["pull_number"]["value"] == "7"
    assert facts["access_token"]["value"] == "[redacted]"
    assert "secret-value" not in str(prompt)
    assert len(prompt["requested_action"]["parameters_digest"]) == 64
    assert len(prompt["contract_digest"]) == 64


def test_prompt_digest_changes_when_exact_action_changes():
    first = from_approval(approval()).contract_digest
    changed = approval(action={
        "tool": "github.pull.merge",
        "domain": "repo::example",
        "impact": "write",
        "intent": "merge reviewed change",
        "params": {"pull_number": 8, "access_token": "secret-value"},
    })
    second = from_approval(changed).contract_digest
    assert first != second


def test_prompt_has_only_narrow_default_choices():
    prompt = from_approval(approval())
    assert [choice["id"] for choice in prompt.choices] == ["allow_once", "deny", "inspect"]
    assert "standing authority" in prompt.choices[0]["effect"]


def test_text_renderer_states_that_downstream_has_not_happened():
    text = render_text(from_approval(approval()))
    assert "LEDGATo paused this action" in text
    assert "Nothing downstream has happened yet." in text
    assert "github.pull.merge" in text
    assert "secret-value" not in text
