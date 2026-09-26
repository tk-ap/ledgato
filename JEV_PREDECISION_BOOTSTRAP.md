# Jev Pre-Decision Bootstrap

Status: architecture + benchmark contract only. No live authorization role is created by this document.

## Purpose

Bootstrap Jev into the Ledgato/AgentOS direction as a bounded advisory component for Progressive Authority Calibration.

Jev's job is to reduce reasoning cost before a deterministic authority decision by helping answer:

- What kind of consequential boundary is this?
- Which existing policy or authority record is most relevant?
- Is this request materially different from previously covered requests?
- What authority dimension is unresolved?
- What is the minimum question that would resolve it?
- Is there a repeated decision pattern worth proposing as a standing rule?
- Is the evidence too weak or ambiguous, requiring abstention?

Jev does **not** answer the authoritative question: "Is this action allowed?"

## Placement

```text
request / action contract
        ↓
Jev pre-decision analysis
        ↓
structured advisory output
        ↓
Ledgato deterministic authority/policy evaluation
        ↓
ALLOW / DENY / APPROVE
        ↓
enforcement permit / pause / rejection
        ↓
downstream execution
        ↓
independent verification + evidence
```

## Advisory input

A benchmark/runtime adapter may provide only the context needed for the requested analysis, such as:

- principal / agent identity;
- requested action;
- resource / environment;
- task or workflow reference;
- declared scope and constraints;
- candidate policy references;
- prior scoped authority records;
- relevant prior approval/denial history;
- ALVIRA-derived context only when useful for question prioritization, never as authority;
- evidence freshness/provenance metadata.

Do not provide reusable credentials, secrets, wallet keys, or permit-signing material.

## Advisory output

Jev output should be structured and non-executable. Suggested fields:

```yaml
boundary_class: string | unknown
candidate_policy_refs: []
material_novelty:
  level: low | medium | high | unknown
  reasons: []
unresolved_authority_dimensions: []
recommended_question:
  required: true | false
  field: string | null
  prompt: string | null
  response_type: single_select | multi_select | bounded_number | resource_select | none
  options: []
pattern_candidate:
  detected: true | false
  evidence_refs: []
  proposed_scope: null | structured_scope
confidence: 0..1
abstain:
  value: true | false
  reason: string | null
evidence_refs: []
```

This schema is directional. It may evolve during benchmarking, but it must not gain executable authority fields.

## Structural safety invariants

1. Jev output cannot issue or encode an enforcement permit.
2. Jev output cannot activate, revoke, or widen standing authority.
3. Jev output cannot be treated as an authoritative `ALLOW`, `DENY`, or `APPROVE` decision.
4. Ledgato's deterministic policy/authority evaluation remains mandatory after Jev.
5. Context and model confidence do not grant authority.
6. Ambiguous/insufficient cases may abstain; abstention must not be converted into autonomy.
7. Repeated approvals may generate a proposal only; explicit confirmation is required before policy changes.
8. Downstream verification remains independent of Jev.

## Benchmark corpus

Build a labeled corpus from synthetic cases first, then add sanitized real cases when available.

Cover at least:

- known action + exact standing policy match;
- known action with changed resource;
- known action with changed environment;
- known action with changed scope;
- known action with expired authority;
- delegated action where delegation is prohibited;
- delegated action where authority is narrower than parent authority;
- unknown tool / unknown action;
- spend below and above an existing threshold;
- production vs preview distinction;
- repeated approvals under identical conditions;
- superficially similar approvals with a materially different condition;
- missing evidence / stale evidence;
- conflicting candidate policies;
- insufficient context requiring abstention.

## Benchmark outputs

For each case, compare Jev output with labeled expected values for:

- boundary classification;
- candidate policy match;
- material novelty;
- unresolved authority dimension;
- minimum sufficient question;
- pattern candidate;
- abstain / proceed-to-policy-evaluation recommendation.

Also record:

- schema validity;
- unsupported/invented fields;
- evidence references used;
- latency/cost where relevant;
- whether the proposed question contains unnecessary ambiguity or asks for more authority than needed.

## Promotion criteria

Before runtime use:

- every benchmark output must validate against the advisory schema;
- no benchmark output may directly authorize execution or produce permit material;
- no benchmark case may silently widen scope relative to the labeled request;
- known uncertainty cases must support abstention instead of fabricated certainty;
- classification/matching/question-selection quality must be measured against the labeled corpus and reviewed before choosing an acceptance threshold;
- failures must be observable and fall back to deterministic Ledgato behavior without increasing authority.

Passing the benchmark permits a bounded shadow-mode or advisory integration. It does **not** by itself authorize Jev to become an enforcement decision maker.

## First integration target

The first useful placement is Progressive Authority Calibration:

```text
uncovered consequential request
        ↓
Jev identifies unresolved authority + minimum question
        ↓
owner selects explicit scoped answer
        ↓
Ledgato creates typed authority record
        ↓
deterministic evaluation
        ↓
agent resumes if allowed
```

This supplies a concrete, measurable System-One-style workload without placing probabilistic inference on the enforcement side of the boundary.
