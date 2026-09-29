# AgentOS host-action boundary

Status: bounded host-integration slice for the canonical AgentOS runtime proof.

## Purpose

Ledgato may authorize one root-affecting AgentOS host operation without turning
Ledgato into a generic shell or sudo broker.

The supported actions are:

- `host.agentos.runtime.status` — read-only status
- `host.agentos.runtime.activate` — install/refresh the fixed AgentOS board
  runtime units and activate their two timers

No caller-supplied command, path, unit, environment variable, or argument is
forwarded to the privileged helper.

## Trust boundary

The protected path is:

```text
AgentOS principal
  -> Ledgato policy
  -> APPROVE owner checkpoint for activation
  -> HostActionAdapter
  -> sudo -n /usr/local/libexec/ledgato-host-op <fixed-operation>
  -> root-owned canonical AgentOS mirror
  -> fixed systemd unit installation/activation
  -> post-action status readback
  -> Ledgato evidence
```

A DENY never invokes sudo or the helper.

The helper accepts only:

```text
agentos-runtime-status
agentos-runtime-activate
```

The sudoers installation grants those exact command lines only. It contains no
wildcard and no `NOPASSWD: ALL`.

## Canonical source rule

Root installation must never trust a mutable developer or worker checkout.

The helper owns and validates:

```text
/var/lib/ledgato/agent-os-source
origin = https://github.com/tk-ap/agent-os.git
branch = main
owner = root
clean = true
```

Because `tk-ap/agent-os` is private, the root helper never performs a GitHub
fetch and never receives an owner GitHub credential.

Instead, the owner stages the current authenticated `origin/main` into the
root-owned immutable bundle:

```text
/var/lib/ledgato/agent-os-main.bundle
```

The helper validates that bundle, fast-forwards only the root-owned mirror from
its `refs/heads/main`, preserves
`https://github.com/tk-ap/agent-os.git` as canonical upstream metadata, and
requires mirror HEAD plus its local `origin/main` reference to equal the staged
bundle SHA. A stale bundle can leave the mirror unchanged; a bundle that would
move the mirror backward or sideways fails closed.

Only these files can be installed:

- `agentos-runtime-checkout.service`
- `agentos-runtime-checkout.timer`
- `agentos-board-projection.service`
- `agentos-board-projection.timer`
- `agentos-workspace-board-publisher.service`
- `agentos-board-projection.service.d/20-workspace-board-publisher.conf`
- `/usr/local/libexec/agentos-runtime-sync` from
  `runtime/agentos_runtime_sync.sh`

The retired workspace publisher timer is disabled if it still exists.

The helper cannot manage SSH, Tailscale, arbitrary services, arbitrary files,
or arbitrary AgentOS code.

## Installation

Bootstrap a root-owned canonical Ledgato checkout first; do not run the
installer from a mutable developer/agent checkout:

```bash
sudo install -d -o root -g root -m 0755 /var/lib/ledgato
sudo git clone --branch main --single-branch https://github.com/tk-ap/ledgato.git /var/lib/ledgato/source
sudo bash /var/lib/ledgato/source/ops/install_ledgato_host_op.sh --service-user tk
```

If the root-owned source already exists, the installer itself verifies exact
origin, clean `main`, fast-forward-only history, and convergence to fetched
`origin/main` before it installs any helper code.

The installer:

1. installs the helper root-owned at
   `/usr/local/libexec/ledgato-host-op`;
2. creates `/var/lib/ledgato` as a root-owned state parent;
3. installs a sudoers fragment containing only the two exact helper commands;
4. validates the sudoers file;
5. performs only the read-only status operation as the configured service user.

It does **not** execute activation.

The configured service account is part of this bounded host TCB. AgentOS worker
processes must continue to run as the separate `agentos` account and must not
receive this sudo permission.

## Stage private AgentOS source

Before activation, stage the current canonical AgentOS main using the owner
account's existing GitHub authentication:

```bash
bash /var/lib/ledgato/source/ops/stage_agentos_source.sh
```

The staging script:

1. runs as the owner account, not root;
2. verifies the source checkout points at
   `https://github.com/tk-ap/agent-os.git`;
3. fetches only `origin/main` using the owner's existing Git credential path;
4. builds a temporary bundle exposing only `refs/heads/main`;
5. installs only that bundle root-owned at
   `/var/lib/ledgato/agent-os-main.bundle`;
6. prints the staged commit SHA but never prints or copies a GitHub credential.

Root and the `agentos` runtime account therefore need no GitHub credential.
The bundle must be refreshed before a later activation is expected to adopt a
new AgentOS revision.

## Enable the adapter

The owner-managed Ledgato environment must add these non-secret values:

```text
LEDGATO_HOST_OP_ENABLED=1
LEDGATO_HOST_OP_RESOURCE=ashwood-host-01
LEDGATO_HOST_OP_HELPER=/usr/local/libexec/ledgato-host-op
```

Do not replace or print the existing principal secrets while editing that file.

The default AgentOS workspace policy now:

- allows `host.agentos.runtime.status`;
- requires owner approval for `host.agentos.runtime.activate`;
- binds both to the exact `ashwood-host-01` domain.

Restart the existing Ledgato service after adding the variables, then verify
`/health` reports the `host` adapter.

## Activation semantics

The activation helper performs only the following bounded sequence:

1. validate the root-owned staged AgentOS bundle and fast-forward the
   root-owned canonical AgentOS mirror from it;
2. validate fixed unit files with `systemd-analyze verify`;
3. install those files root-owned under `/etc/systemd/system` and install the
   fixed credential-free runtime sync helper under `/usr/local/libexec`;
4. reload the system systemd manager;
5. run `agentos-runtime-checkout.service` once to provision the account-owned
   clean runtime from the root-owned local mirror;
6. enable/start `agentos-runtime-checkout.timer` and
   `agentos-board-projection.timer`;
7. run one board projection, whose existing `OnSuccess` hook publishes the
   matching snapshot;
8. verify the runtime checkout is clean/canonical, both timers are active and
   enabled, and the runtime revision matches the root-owned canonical mirror.

Any failed step fails the Ledgato execution rather than widening the operation.

## Proof boundary

This makes the previously missing root helper available. It does not itself
prove the full AgentOS autonomy loop.

The next canonical proof remains:

```text
fresh canonical task
-> persistent runtime claim
-> one real owner checkpoint
-> same-task exactly-once resume
-> independent verification/evidence
-> autonomous next-task claim
-> reboot
-> recovery without duplicate execution or manual reconstruction
```
