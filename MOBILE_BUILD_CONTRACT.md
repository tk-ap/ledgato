# LEDGATo Mobile Build Contract

> Status: **canonical implementation contract; build currently gated**
>
> Applies to: first native LEDGATo operator-app vertical slice
>
> This file answers the implementation questions a contextless agent must not be forced to invent.

## 1. Purpose

Build one native iPhone approval client that can safely complete this exact loop:

```text
one AgentOS protected action
    ↓
LEDGATo durable approval challenge
    ↓
APNs notification
    ↓
trusted iPhone opens exact challenge
    ↓
operator sees exact consequential request
    ↓
Face ID permits use of device-bound signing key
    ↓
signed decision returned to LEDGATo
    ↓
LEDGATo verifies + atomically consumes decision
    ↓
same AgentOS workflow resumes at most once
    ↓
provider/resource result independently verified
    ↓
receipt visible in app
```

This is not a broad mobile-product build. The first milestone is proof that the authorization path works correctly on a real device.

## 2. Document precedence

For work under this build contract, use this precedence when guidance conflicts:

1. **Current governed task/work-item envelope and explicit owner decision**
2. **Repository `AGENTS.md`**
3. **This file — `MOBILE_BUILD_CONTRACT.md`**
4. **`.agent-os/mobile-build-readiness.yaml`**
5. **`MOBILE_OPERATOR_APP_DIRECTION.md`**
6. **`STRATEGIC_ARCHITECTURE_DIRECTION_2026-10.md`**
7. **Existing versioned contracts under `contracts/`**
8. **`PRODUCT_DIRECTION.md`**
9. **`GO_TO_MARKET.md` and broader roadmap material**

A lower-precedence document may provide context but may not silently widen the active task.

If two applicable sources remain materially inconsistent after applying this order, fail closed and surface the conflict. Do not choose whichever interpretation makes implementation easiest.

## 3. Machine-readable readiness gate

Before creating application code, changing mobile infrastructure, registering push credentials, or provisioning mobile services:

1. read `.agent-os/mobile-build-readiness.yaml`;
2. require `ready_for_first_vertical_slice: true`;
3. require non-empty evidence references for every required gate marked `satisfied: true`;
4. require the current AgentOS task to explicitly authorize this build.

A closed issue, merged PR, passing unit suite, reachable host, or prose statement is not a substitute for the readiness record.

The readiness file begins fail-closed. Updating it to ready is a separate evidence-backed change, not something the mobile implementation agent may infer or self-certify.

## 4. First-user scope

The first vertical slice is deliberately:

- **one human operator**;
- **one tenant/account context**;
- **one trusted physical iPhone**;
- **one LEDGATo backend environment**;
- **one AgentOS environment**;
- **one protected consequential action**;
- **one approval at a time for the proof**.

Do not add:

- organizations;
- invitations;
- teams;
- approver groups;
- quorum/multi-human approval;
- enterprise RBAC;
- device fleets;
- Android parity;
- policy editing;
- analytics dashboards;
- generalized remote-host management.

The architecture may avoid blocking those later, but the first slice must not implement them.

## 5. Settled implementation stack

### Repository shape

Use the existing `tk-ap/ledgato` repository.

Target layout:

```text
apps/
  mobile/                 # React Native + Expo + Expo Router

packages/
  contracts/              # generated/typed consumption of canonical JSON schemas where useful
  api-client/             # LEDGATo mobile API client only
  ui-tokens/              # shared non-security visual tokens where useful

native/
  ios-security/           # smallest possible native Secure Enclave/App Attest bridge
  android-security/       # reserved; not part of first proof

contracts/
  ...existing canonical contracts...
  mobile-device-enrollment.schema.json
  mobile-approval-challenge.schema.json
  mobile-signed-decision.schema.json
  mobile-approval-receipt.schema.json
  mobile-push-envelope.schema.json
  mobile-push-registration.schema.json
```

If the repository's current package manager/workspace structure makes an equivalent placement materially cleaner, preserve the same ownership boundaries rather than forcing these exact directory names. Do not rewrite the existing web application or Python engine to obtain monorepo aesthetic consistency.

### Mobile

- React Native
- Expo
- Expo Router
- Expo development build / EAS where required
- `expo-notifications`
- `expo-local-authentication`
- `expo-secure-store` only for ordinary session/small-secret material

### Security-critical signing

Do **not** store the approval private signing key as a normal JavaScript-accessible secret.

For iOS first proof:

- create a device-bound, non-exportable signing key through native Apple security APIs appropriate to the target device;
- require the local biometric ceremony before the private-key operation where supported;
- register only the corresponding public key with LEDGATo;
- use App Attest as app/device integrity evidence where available;
- keep the native bridge minimal and separately reviewed.

Do not invent cryptographic algorithms or protocol formats during implementation. The exact algorithm/key representation must be specified and reviewed before the native security module is accepted.

Android Keystore / Play Integrity is direction only for the first slice.

## 6. Backend ownership

There must be **one LEDGATo authorization authority**.

The mobile app:

- does not evaluate policy authoritatively;
- does not mint permits;
- does not advance approval state locally;
- does not write the approval database directly;
- does not call AgentOS as an authority shortcut.

The existing LEDGATo engine/backend owns:

- authoritative approval state;
- policy/authority evaluation;
- challenge generation;
- device/public-key registration validation;
- signed-decision verification;
- expiry/revocation/state validation;
- atomic decision consumption;
- permit/resume issuance;
- evidence/receipt binding.

AgentOS owns execution/workflow lifecycle.

Do not create a second authorization implementation in TypeScript, Supabase functions, Expo code, or mobile state because doing so is convenient.

### Database

Use durable shared Postgres for production-direction approval/device state.

Supabase is an implementation candidate for Postgres infrastructure only if required by an explicit infrastructure decision. Do not introduce Supabase Auth, edge authorization logic, or another source of policy truth simply because Supabase is selected as a database host.

## 7. Authentication and enrollment

Face ID is not account authentication.

The first proof requires two distinct concepts:

1. **authenticated LEDGATo operator session** — establishes which human account/principal is using the app;
2. **trusted device enrollment** — binds a device-generated public key and device/app integrity evidence to that authenticated operator.

Do not introduce a new identity vendor automatically.

Reuse the existing LEDGATo authenticated-user/principal mechanism if it can securely establish the operator identity required for enrollment.

If no suitable authenticated operator mechanism exists, stop at that integration boundary and record the blocker. Do not autonomously choose or provision Clerk, Auth0, Supabase Auth, Firebase Auth, Cognito, or another identity product.

### Enrollment requirements

Enrollment must:

- originate from an authenticated operator session;
- create the key on-device;
- send only the public key plus required integrity/device metadata;
- assign a stable server-side `device_id`;
- record key/version/created state server-side;
- permit explicit server-side revocation;
- never export/recover the original private approval key.

A replacement phone is a new device enrollment, not restoration of the old device key.

## 8. Versioned mobile contracts

The first slice must use the schemas under `contracts/mobile-*.schema.json`.

They are **contract specifications, not evidence that endpoints exist**.

The required conceptual API surface is:

```text
POST /v1/mobile/devices/enroll
POST /v1/mobile/push/register
GET  /v1/mobile/approvals/{approval_id}
POST /v1/mobile/approvals/{approval_id}/decision
GET  /v1/mobile/approvals/{approval_id}/receipt
POST /v1/mobile/devices/{device_id}/revoke
```

Route naming may change only through a reviewed contract update. Do not allow the client and server to invent divergent payloads independently.

The mobile app never receives the raw server permit-signing key, provider credential, or another reusable execution credential.

## 9. What-you-see-is-what-you-sign

The approval UI must render a server-derived challenge that is bound to the exact normalized consequential request.

The operator-facing representation must identify enough to understand:

- who/what is acting;
- action;
- protected resource/destination/environment;
- material parameters/facts;
- impact/consequence;
- why approval is required;
- expiry;
- relevant provenance warnings where applicable.

The signed decision must bind:

- approval/challenge ID;
- canonical request/contract digest;
- representation version;
- challenge nonce;
- decision;
- device ID/key ID;
- expiry/freshness fields required by the contract.

The app may improve layout or wording, but it may not fabricate a different scope.

If the server says the request changed, expired, was revoked, was superseded, or is otherwise stale, the client must refetch/re-render before a new decision.

## 10. Tool/server/schema and context provenance

For consequential actions, preserve relevant provenance supplied by the backend:

- provider/server identity;
- tool/capability identity;
- schema/protocol fingerprint/version where material;
- context-source provenance for consequential values.

Do not turn the mobile client into a classifier that decides whether provenance is trustworthy.

The client renders server-derived facts/warnings. LEDGATo policy remains authoritative.

## 11. Push and deep-link contract

Push is notification only.

The lock-screen push payload should be minimal and non-authoritative.

Allowed first-slice contents should be limited to fields equivalent to:

- push schema version;
- generic event kind;
- opaque approval ID;
- optional non-sensitive display hint.

Do not include:

- bearer tokens;
- signing material;
- permit/resume tokens;
- provider credentials;
- full commands;
- sensitive resource parameters;
- evidence payloads;
- anything whose possession is sufficient to approve.

After opening, the app authenticates to LEDGATo and fetches the authoritative challenge.

### State separation

Transport state and authority state are different domains.

```text
transport:
sent / delivered? / opened

authority:
PENDING / APPROVED / DENIED / EXPIRED / REVOKED / SUPERSEDED
```

No transport event may advance authority state.

## 12. Failure matrix

All ambiguous failure modes must fail closed for new authority.

At minimum:

| Condition | Required behavior |
|---|---|
| APNs delivery delayed/lost | approval remains pending until normal expiry/policy behavior |
| notification opened after expiry | refetch; show expired; no decision |
| app offline | no new approval |
| LEDGATo unreachable | no new approval |
| stale cached challenge | refetch before decision |
| App Attest unavailable/fails | follow explicit server policy; never silently ignore |
| biometric cancelled/fails | no signature/decision |
| device revoked while challenge open | server rejects decision |
| request superseded while screen open | server rejects; client refetches |
| duplicate decision submission | at most one authoritative consumption |
| two devices race | at most one authoritative consumption |
| AgentOS already cancelled task | server rejects resume/decision as applicable |
| provider outcome unknown | report UNKNOWN/PARTIAL; no blind success assumption |
| receipt fetch fails | execution truth remains server-side; UI shows unavailable rather than inventing success |

## 13. Environment separation

The first mobile proof must not accidentally become a production side-effect test.

Use explicit:

- development app configuration;
- staging/test LEDGATo backend;
- disposable or bounded protected action/resource;
- test APNs configuration appropriate to the build;
- test AgentOS work item/environment.

Production provider actions, production signing keys, production push credentials, paid infrastructure changes, and App Store release are separately authorized activities.

A physical iPhone is required for final device-security proof. Simulator success is not evidence for Secure Enclave/App Attest/real push behavior.

## 14. Privacy, telemetry and evidence

Keep three classes separate:

### Security evidence

Authoritative records such as:

- challenge/request;
- decision;
- approver/device;
- signature verification;
- permit/resume reference;
- execution result;
- provider/resource verification.

This is not ordinary analytics.

### Operational health

Examples:

- API errors;
- notification delivery attempts;
- latency;
- app crashes.

Operational health must not contain unnecessary approval payload contents.

### Product analytics

Optional later usage instrumentation.

Do not add product analytics to the first security proof unless explicitly authorized.

Rules:

- analytics outage must never affect authorization;
- evidence must not depend on analytics;
- sensitive approval parameters must not be copied into generic analytics/crash payloads;
- redact secrets/tokens/signatures where not necessary for evidence;
- do not log private signing material under any circumstance.

## 15. Dependency and supply-chain policy

The security-critical kernel should have a deliberately small dependency surface.

For device enrollment, attestation, challenge signing, cryptography, secure-key handling, or authorization state:

- prefer platform primitives and existing reviewed repository code;
- pin dependency versions;
- document why a new dependency is needed;
- require independent review for a new native security dependency;
- do not substitute crypto/auth libraries solely because an AI-generated example uses them;
- do not download/copy unknown security code into the repository.

UI-only dependencies must not become implicit trust anchors.

## 16. Cost and external-service authority

Do not autonomously:

- create paid cloud resources;
- upgrade Expo/EAS/Vercel/Supabase or another plan;
- create a new commercial monitoring/auth/security subscription;
- fund wallets or paid test providers;
- purchase developer memberships;
- create production certificates/credentials beyond the explicitly authorized task.

A free tier is still an external architectural dependency and must be documented if introduced.

## 17. App Store / account identity inputs

Do not invent:

- Apple Team ID;
- bundle identifier;
- production app display name if unresolved;
- App Store listing identity;
- legal entity/account holder;
- production privacy/support URLs;
- production signing/certificate ownership.

When an owner/account value is required and is not already canonical in repository configuration, record it as an owner input/blocker.

Do not create or mutate external store/developer accounts merely to keep the task moving.

## 18. UX railguard

The first app is an **operator instrument**, not an enterprise security dashboard.

Default hierarchy:

```text
Needs you
  ↓
what is trying to happen
  ↓
why it stopped
  ↓
scope / resource / consequence
  ↓
Approve once / Deny

after decision

What happened
  ↓
provider-verified result
  ↓
Evidence / Details
```

Use plain-language outcome labels in the primary interface.

Keep policy digests, signatures, attestation records, permit IDs, hashes, and low-level protocol details under Evidence/Details.

Preserve the existing LEDGATo visual direction and product language rather than inventing a generic cybersecurity dashboard aesthetic.

## 19. Operator terminal railguard

The first approval slice does not include an embedded terminal.

After the first approval proof, a context-aware **Open operator session** may hand off to documented Moshi deep links for active Herdr/tmux sessions.

Opening a terminal:

- is a human operator action;
- is not an LEDGATo approval;
- does not expand agent authority;
- does not prove task completion.

Manual operator evidence must be labeled distinctly from agent-executed LEDGATo-governed evidence.

Useful evidence vocabulary:

- `AGENT_EXECUTED_LEDGATO_GOVERNED`;
- `HUMAN_EXECUTED_OPERATOR_SESSION`.

Choose final enum spelling in the versioned evidence contract; do not conflate the two semantics.

If AgentOS can execute an exact bounded command after owner authorization, prefer the signed approval path instead of requiring the human to open a terminal.

## 20. Host Action input boundary

The mobile app must not independently discover local hosts, SSH credentials, tmux sessions, Herdr workspaces, or deferred AgentOS tasks.

If Host Actions are added later, AgentOS supplies a canonical durable object containing at least:

- host action ID;
- work/task ID;
- host identity;
- repository/workspace;
- reason human intervention is required;
- bounded command or interaction description where safe;
- sudo/root/interactive flags;
- verification expectation;
- optional session reference / documented operator-access URI.

AgentOS remains canonical for the Host Action lifecycle.

## 21. Verification independence

The implementation author cannot provide the only terminal security verdict for the security-critical kernel.

Require an independently eligible verifier for:

- trusted-device enrollment;
- device-bound key behavior;
- attestation;
- challenge construction;
- what-you-see-is-what-you-sign;
- signature verification;
- nonce/replay/expiry;
- atomic decision consumption;
- approval → permit/resume binding;
- execution/evidence binding.

The verifier should receive canonical acceptance requirements and immutable evidence, not rely solely on the implementation author's explanation.

## 22. Explicit non-goals

Do not:

- rename LEDGATo to khrystal;
- redesign the entire product;
- rewrite the existing web frontend;
- create a second authorization engine;
- turn Supabase into policy authority;
- use Expo Push receipt as authority;
- treat biometrics as server authentication;
- build a new SSH service;
- rebuild Moshi;
- add MCP/A2A implementation merely because it is strategic;
- add Android to the first proof;
- build organizations/teams/RBAC;
- add policy editing;
- add broad analytics;
- deploy production merely because tests pass;
- interpret access to a host/credential/secret as authority to use it;
- trust an agent's self-authored security review as terminal evidence.

## 23. First-slice completion criteria

The first mobile vertical slice is complete only when all are evidenced on a physical iPhone:

1. one trusted device can be enrolled without exporting its private approval key;
2. one real bounded AgentOS action creates one durable LEDGATo approval;
3. APNs can notify the device without carrying executable authority;
4. the app refetches the authoritative challenge;
5. the operator sees the exact server-derived consequential request;
6. biometric ceremony gates the device signing operation;
7. LEDGATo verifies the signed exact challenge;
8. expired/revoked/superseded/replayed/mutated requests fail;
9. decision consumption is atomic;
10. the exact originating AgentOS workflow resumes at most once;
11. the protected action cannot bypass the tested LEDGATo path;
12. provider/resource evidence determines what actually happened;
13. a receipt is inspectable from the app;
14. the security-critical path receives independent verification;
15. no deferred feature is required to make the proof pass.

Anything less remains implemented/tested/previewed as appropriate, not "mobile approval proven."
