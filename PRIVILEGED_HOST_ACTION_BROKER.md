# Privileged Host Action Broker

> Status: **approved architecture direction; not implemented**
>
> Purpose: eliminate unnecessary human terminal switching for bounded privileged host actions without storing, forwarding, or exposing a reusable sudo/root credential to AgentOS or its agents.

## Decision

Do **not** store the operator's sudo password in an encrypted `.env`, secret file, database row, mobile payload, or AgentOS credential store for automated decryption and forwarding.

Instead, introduce a **root-owned Privileged Host Action Broker** on the governed host.

The broker is a protected resource. It accepts only a valid, exact-scope LEDGATo enforcement permit for a typed allowlisted host action.

Core model:

```text
AgentOS requests exact privileged host action
        ↓
existing LEDGATo action contract
        ↓
ALLOW / DENY / APPROVE
        ↓
if approved/allowed:
signed short-lived one-use enforcement permit
        ↓
root-owned host broker
        ↓
verify permit + host + action + parameters + expiry + replay state
        ↓
execute one allowlisted root operation
        ↓
host/provider readback
        ↓
evidence
        ↓
same AgentOS workflow continues
```

No sudo password is transmitted to the agent, app, broker API, or terminal.

## Why not encrypted sudo-password forwarding

Encrypting a sudo password improves at-rest secrecy but does not create least authority.

Any service able to decrypt the reusable password and feed it to `sudo` effectively possesses reusable root authority. Compromise of that service, its process boundary, its decryption path, or its runtime memory can turn the encrypted secret into broad privilege.

LEDGATo should instead authorize one action, on one host/resource, once, for a short period.

> **Move a scoped capability, not the human's reusable credential.**

## Ownership boundary

### LEDGATo owns

- decision over the exact privileged action at a boundary it enforces;
- exact action-contract binding;
- optional human approval;
- signed one-use permit;
- expiry/revocation semantics;
- evidence binding.

### AgentOS owns

- task/workflow state;
- determination that a privileged host action is needed;
- construction of the exact typed action request;
- pause/resume lifecycle;
- post-action workflow continuation;
- verification routing.

### Host broker owns

- root privilege on the host;
- validation that the permit is valid for this exact broker/host/action;
- translation from one typed allowlisted action to the root operation;
- execution;
- local readback/receipt.

The mobile app owns none of the above authority. It is only the authenticated human decision client.

## Reuse existing enforcement model

Do not create a parallel "sudo authorization" system.

A privileged host action should use the same canonical LEDGATo model already defined by:

- `contracts/action-contract.schema.json`
- `contracts/enforcement-permit.schema.json`

Conceptually:

```json
{
  "version": "ledgato.action-contract/v1",
  "work_id": "...",
  "agent": {"id": "agentos", "identity": "..."},
  "requested_action": {
    "name": "host.service.restart",
    "impact": "exec",
    "params": {
      "host_id": "omarchy",
      "service": "agentos-runtime.service"
    }
  },
  "resource": "host:omarchy/privileged-broker",
  "policy": {"id": "..."}
}
```

The broker accepts the resulting permit only if its action/resource/contract digest match the exact request it is about to execute.

## Broker shape

Preferred initial implementation direction:

```text
systemd
  ├─ root-owned broker service
  └─ root-owned Unix-domain socket
          ↑
      narrow local client
          ↑
        AgentOS
```

Properties:

- broker process runs with only the privilege required to execute its action registry;
- socket/file permissions limit who can submit requests;
- authentication to the local socket is not authorization by itself;
- every privileged operation still requires a valid LEDGATo permit unless explicitly classified as a non-consequential local health/read-only operation;
- broker verifies the permit independently of the AgentOS caller;
- broker never invokes a general-purpose shell from agent-controlled text by default;
- broker implementations/action handlers are root-owned and not writable by the governed `agentos` account;
- the governed agent does not receive the broker's signing keys, root credentials, sudo password, or reusable root token.

A systemd socket is a design preference, not a claim of implementation. Another local IPC mechanism may be used only if it preserves the same trust boundary and is independently reviewed.

## Action registry

The broker must expose a typed action registry, not arbitrary `sudo <string>`.

Examples that may be suitable after review:

- `host.service.restart(service=<allowlisted unit>)`
- `host.service.reload(service=<allowlisted unit>)`
- `host.runtime.sync(revision=<validated revision>)`
- `host.package.install(package=<allowlisted package/version>)` only if separately approved as an appropriate action class
- `host.file.install(source_digest=<known artifact>, destination=<allowlisted destination>)`
- `host.health.repair(repair_id=<known deterministic repair>)`

Every action must define:

- action identifier;
- typed argument schema;
- allowed resource scope;
- implementation handler;
- required privilege;
- consequence statement for human display;
- idempotency/retry behavior;
- verification/readback procedure;
- timeout/failure semantics;
- whether human approval is always required.

## Forbidden broker capabilities

Do not expose by default:

- arbitrary shell command execution;
- `sudo -S`;
- a reusable root shell;
- `NOPASSWD: ALL`;
- arbitrary `systemctl *`;
- arbitrary file write/chown/chmod paths;
- arbitrary package-manager arguments;
- arbitrary script paths;
- interpreters such as `bash -c`, `sh -c`, Python, Node, Ruby, Perl, etc. fed agent-controlled code;
- commands whose supposedly narrow arguments permit command/path/environment injection;
- a general "run as root" endpoint.

Adding a new privileged action is a security-boundary change and must be reviewed as such.

## Sudoers role

Command-specific `sudoers NOPASSWD` may be used as an implementation detail **behind a fixed root-owned wrapper** if that is demonstrably simpler and preserves least authority.

It must never become the external AgentOS contract.

If used:

- no `NOPASSWD: ALL`;
- no arbitrary command arguments;
- no shell/interpreter escape path;
- wrapper and downstream executable must not be writable by `agentos`;
- environment variables and PATH must be controlled;
- executable resolution must be absolute;
- the allowed operation must still require the LEDGATo permit at the broker boundary.

A root-owned daemon that does not require `sudo` is the preferred conceptual model.

## Three-level operator model

The ecosystem should distinguish:

### 1. Normal governed action

Example: GitHub merge.

```text
AgentOS → LEDGATo → protected provider adapter
```

No human terminal.

### 2. Privileged governed host action

Example: restart one named system service.

```text
AgentOS
  → LEDGATo exact approval
  → signed one-use permit
  → Privileged Host Action Broker
  → verified host effect
```

The operator may approve entirely from the LEDGATo phone app. No terminal and no password are required.

### 3. Human operator action

Example: 2FA, OS trust prompt, unknown recovery procedure, genuinely interactive root diagnosis.

```text
LEDGATo / AgentOS Host Action
  → Open operator session
  → Moshi / SSH / Mosh
  → human acts
  → runtime/provider verifies outcome
```

Human operator execution must remain labeled differently from agent-executed governed actions.

## Mobile UX

A privileged host action should appear like any other exact consequential action, with additional host/privilege context.

Example:

```text
Needs you

AgentOS wants to:
Restart AgentOS runtime

Host:
Omarchy

Privilege:
Elevated host action

Resource:
agentos-runtime.service

Reason:
Activate verified revision abc123

Scope:
One execution on this host

[Approve once] [Deny]

Details / Evidence
```

Approval signs the exact action contract. It does not reveal or transfer a sudo password.

## Broker permit validation

Before performing a privileged operation, the broker must validate at least:

- permit signature;
- issuer/trust anchor;
- permit version;
- permit ID;
- exact action-contract digest;
- exact broker resource/host identity;
- exact action identifier;
- typed arguments;
- principal/workflow binding;
- issue/expiry time;
- single-use/replay state;
- revocation/freshness requirements applicable to the permit;
- current action-registry version where material.

A permit valid for another host, another action, another service, another parameter set, or another request must fail.

## Execution integrity

Target invariant:

> **approved host action == broker-executed host action == verified host effect**

Do not regenerate the command from model prose after approval.

The broker must translate a typed action object through a deterministic, reviewed handler.

Where a privileged operation cannot be represented deterministically enough for this invariant, it belongs in the Human Operator Action lane instead.

## Evidence

Broker evidence should distinguish:

- request;
- LEDGATo decision;
- permit;
- broker receipt;
- privileged operation attempted;
- exit/result state;
- host readback;
- independent verification where required.

Examples:

- systemd unit active state after restart;
- runtime revision after sync;
- file digest/ownership after install;
- package version after bounded package operation.

The broker's own "success" response is not sufficient for high-consequence claims if an independent host/provider readback is available.

## Failure semantics

Fail closed.

At minimum:

- invalid/expired/replayed permit → do nothing;
- argument outside schema/allowlist → do nothing;
- registry version mismatch where relevant → do nothing;
- root handler missing or changed unexpectedly → do nothing;
- operation timeout → record UNKNOWN/PARTIAL as appropriate, then reconcile;
- crash after permit consumption → reconcile actual host state before any retry;
- LEDGATo unavailable before permit issuance → no new privileged authority;
- host broker unavailable → task remains waiting/recovering; do not fall back to password forwarding.

Do not silently route a failed broker action to Moshi/manual shell. Human intervention remains an explicit separate owner action.

## Secrets and credentials

Do not store the human sudo password for this design.

If the broker itself later requires a service secret, use an appropriate root/service credential mechanism and treat that secret as the broker's credential, not the operator's password.

Host-bound encrypted service credentials may be considered for genuine broker/service secrets, but they do not change the rule that reusable human sudo credentials must not be handed to AgentOS.

## Implementation and proof gate

This is not part of the first native approval vertical slice.

Sequence:

1. AgentOS E2E autonomy/persistence proof passes.
2. LEDGATo native approval proof passes.
3. Approval → signed permit convergence is proven.
4. Implement one broker action with no generic shell, e.g. restart one allowlisted non-production service.
5. Adversarially test argument mutation, replay, alternate host/resource, stale permit, broker bypass, writable-handler attack and direct sudo/root alternatives.
6. Independently verify the host effect.
7. Only then expand the action registry.

The first broker proof should demonstrate:

```text
AgentOS requests one elevated service restart
→ LEDGATo holds for approval
→ operator approves on phone
→ broker accepts one permit
→ correct service restarts
→ replay fails
→ altered service name fails
→ agent cannot execute equivalent root action directly
→ host readback verifies outcome
→ workflow resumes
```

## Product boundary

The broker exists to remove unnecessary manual terminal switching while preserving a stronger security boundary.

It must not turn LEDGATo into:

- a privileged remote shell;
- a general secrets vault;
- a password-forwarding system;
- a replacement for OS identity/privilege management;
- a second AgentOS runtime.

The intended result is simple:

> **If a task needs a bounded privileged operation, the human should usually approve the operation, not type their root credential.**
