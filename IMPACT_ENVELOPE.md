# LEDGATo Impact Envelope

> Status: **approved architecture direction; contract-first, implementation gated**
>
> Applies to: **the canonical approval plane**, not only the mobile app.

## Core product rule

A consequential approval should answer:

> **What will change if I approve this, what else could be affected, how confident are we, and what actually changed afterward?**

LEDGATo should not present a naked binary approval when material impact can be derived.

The Impact Envelope is advisory context attached to the exact action. It never grants authority.

## Canonical approval-plane flow

```text
exact requested action
        ↓
impact resolution
  ├─ deterministic provider/repo/runtime facts
  ├─ AgentOS active-workstream relationships
  └─ bounded model inference where useful
        ↓
Impact Envelope
        ↓
canonical DecisionPrompt
        ↓
web / Telegram / TUI / chat / mobile / future client
        ↓
human decision
        ↓
exact action executes
        ↓
observed impact
        ↓
expected-vs-actual impact verification
```

Every approval surface renders the same server-derived semantic object. A channel may change layout, not scope, impact semantics, confidence labels, or authority.

## DecisionPrompt migration

The currently implemented `ledgato.decision-prompt/v1` remains valid during migration.

A new `ledgato.decision-prompt/v2` should become the canonical approval-plane target. V2 binds:

- the exact action contract digest;
- the exact parameter digest;
- the Impact Envelope digest;
- the impact preview shown to the operator;
- explicit impact-resolution state.

Do not silently reinterpret v1 as if it had impact analysis. V1 approvals remain valid evidence only for what v1 actually showed.

During migration, a surface may support both v1 and v2. Once v2 becomes required for a protected boundary, that boundary must not downgrade to v1 merely because a transport has not upgraded.

## Impact dimensions

The envelope should be capable of representing:

### Direct delta

What directly changes?

Use provider-derived change classes where possible:

- `CREATE`
- `MODIFY`
- `REPLACE`
- `DELETE`
- `MOVE`
- `GRANT`
- `REVOKE`
- `RESTART`
- `MIGRATE`
- `EXECUTE`
- `OTHER`

For code/data/provider changes, report material additions, overwrites/replacements, deletions, permission changes, migrations, and runtime transitions.

### Dependency impact

What technical resources depend on the changed thing?

Examples:

- source modules/functions/packages;
- services;
- database objects;
- CI/release paths;
- provider resources;
- authorization/enforcement boundaries;
- API consumers.

### Active-workstream impact

What currently active or queued work may be affected?

AgentOS is the canonical source for work/task/sprint/runtime relationships.

Examples:

- active task becomes stale;
- sprint item depends on changed contract;
- waiting approval references an old revision;
- another worker is editing the same surface;
- downstream mobile/LEDGATo milestone becomes blocked/unblocked.

### Authority impact

Does approval:

- add reachable authority;
- revoke authority;
- widen/narrow scope;
- alter an enforcement path;
- expose or remove a bypass route;
- change credentials or trust anchors?

### Runtime impact

Examples:

- process restart;
- service interruption;
- worker/session invalidation;
- migration;
- stale revision;
- downtime;
- required resynchronization.

### Data impact

Examples:

- records created;
- values overwritten;
- rows/files deleted;
- schema migrated;
- irreversible data loss;
- recoverability/backup state.

### User/product impact

Examples:

- user-visible behavior change;
- broken/changed API;
- UI behavior;
- availability;
- authentication flow.

### Security impact

Examples:

- credential exposure/removal;
- new dependency;
- changed trust boundary;
- changed authorization policy;
- changed reachable tool/provider surface.

### Reversibility

Classify and explain:

- `REVERSIBLE`
- `PARTIALLY_REVERSIBLE`
- `IRREVERSIBLE`
- `UNKNOWN`

A "revert commit exists" is not necessarily full reversibility if data, external side effects, or authority changes cannot be restored.

### Novelty

Classify whether the request is:

- `KNOWN_REPEATED` — materially equivalent action/path has prior relevant evidence;
- `KNOWN_CHANGED` — known class but material parameters/environment/dependencies changed;
- `NEW` — no sufficiently similar proven action/path;
- `UNKNOWN` — evidence insufficient.

Novelty never directly decides authority. Policy may require stronger review for novel actions.

## Evidence confidence

Every impact item must carry one of:

- **KNOWN** — established by deterministic/provider/repository/runtime evidence;
- **INFERRED** — supported by model/context analysis but not deterministically established;
- **UNKNOWN** — impact could not be determined.

Do not collapse inferred impact into known fact.

The UI should make uncertainty understandable without creating alarmist prose.

## Sources and ecosystem ownership

### AgentOS

May supply:

- active task/workstream/sprint relationships;
- runtime/worker/session state;
- repository leases/collisions;
- current task revision/scope digest;
- dependency on pending milestones;
- host/runtime operational consequences.

AgentOS context informs impact. It does not grant LEDGATo authority.

### Repository/provider adapters

May supply deterministic:

- diff/change information;
- file/resource relationships;
- permission changes;
- provider plans/diffs;
- affected resources;
- provider-side expected operations.

### ALVIRA/context

May supply relevant human/project context when explicitly permitted.

Context may help explain why an effect matters. It does not become authority.

### Model/analysis layer

May infer:

- indirect dependency relationships;
- plausible workstream implications;
- semantic novelty;
- risk to related components.

Model output is `INFERRED` unless independently established.

## Change classification should prefer deterministic evidence

Whenever the provider/repository can state what will be:

- added;
- modified;
- overwritten/replaced;
- deleted;
- moved;
- granted;
- revoked;

use that evidence directly rather than asking a model to infer it from prose.

Model reasoning is most useful for indirect consequences and missing relationships.

## Human-facing Impact Preview

Primary approval presentation should be compact:

```text
What changes
+ new ...
↻ replaces ...
− deletes ...

Related impact
• workstream A — high / known
• service B — medium / inferred

Operational effect
• restart required
• 2 workers become stale

Reversibility
Reversible by ... / Partially reversible because ...

Novelty
New / Known changed / Known repeated

Unknowns
• downstream X has not been verified
```

Technical evidence and full relationship details remain inspectable under **Impact details / Evidence**.

Do not reduce impact to a synthetic single risk score.

## Approval binding

The operator's decision should bind the Impact Envelope digest that was presented.

Target signing/decision binding includes:

- approval/decision ID;
- action/contract digest;
- parameters digest;
- impact-envelope digest;
- presentation/representation version;
- nonce/freshness;
- decision;
- approver/device where applicable.

If the exact action changes, the Impact Envelope must be recomputed or explicitly revalidated.

If a material dependency/workstream/authority fact changes before decision consumption, policy may require the approval to be superseded and re-presented.

## Expected vs actual impact

After execution, LEDGATo should compare the expected envelope with observed provider/runtime evidence.

Target states:

- `MATCHED` — material observed impact matches the approved expectation;
- `PARTIAL` — some expected impact observed; material parts unresolved;
- `DRIFTED` — a material unexpected effect or missing expected effect was observed;
- `UNKNOWN` — sufficient post-action evidence unavailable.

Examples:

### Runtime restart

Expected:
- service restarts;
- two workers reconnect;
- persisted task state survives.

Observed:
- service restarted;
- one worker reconnected;
- second worker failed to reconnect;
- task state survived.

Result: `DRIFTED` or `PARTIAL` depending on policy/materiality.

### Repository change

Expected:
- add one file;
- replace one function;
- remove one legacy route;
- no integration contract changes.

Observed:
- provider/readback confirms those changes;
- integration contract unexpectedly changed.

Result: `DRIFTED`.

This turns the approval record into:

```text
request
→ expected impact
→ approval
→ execution
→ observed impact
→ comparison
```

## Policy use

Impact context may affect deterministic policy.

Examples:

- `DELETE + IRREVERSIBLE` → require human approval;
- authority expansion → require human approval;
- novel protected-runtime replacement → require approval + impact preview;
- known reversible restart with no dependent workstreams → may follow configured standing policy.

The Impact Envelope itself must never return executable `ALLOW`.

LEDGATo's normal deterministic policy/authority layer remains the source of the decision.

## First implementation slice

Do not require a full Greptile-like dependency graph before proving the approval plane.

For the first Impact Envelope implementation, require only:

1. direct change classification;
2. create/modify/replace/delete facts where provider evidence exists;
3. resource/environment;
4. reversibility classification or `UNKNOWN`;
5. novelty classification or `UNKNOWN`;
6. any directly known AgentOS work/task relationship;
7. explicit `KNOWN / INFERRED / UNKNOWN` evidence levels;
8. impact-envelope digest bound into the v2 prompt.

Then expand to richer dependency/workstream graphs after the canonical flow works.

## Non-goals

Do not:

- make the impact model a second authorization engine;
- create a generic AI risk score;
- block all approvals because some indirect impact is unknown;
- represent inference as provider fact;
- require Greptile as a hard dependency;
- make mobile the canonical source of impact;
- let each transport independently generate impact text;
- authorize a changed action using a stale impact envelope.

## Product implication

The approval-plane promise becomes:

> **LEDGATo does not just ask whether you approve an action. It shows what is expected to change, what else may be affected, how certain that analysis is, and whether reality matched what you approved.**
