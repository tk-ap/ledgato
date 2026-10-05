# LEDGATo Identity and Product-Boundary Architecture

Status: canonical product/auth direction

## Core rule

LEDGATo is an independent governance/enforcement product.

It must remain usable:

- with AgentOS;
- with another execution runtime;
- with ALVIRA;
- with ailhat;
- with ASHWOOD;
- without any of those product surfaces.

No ecosystem product is the parent identity system for LEDGATo.

## Ecosystem topology

The canonical relationship is:

    LEDGATo
      independent enforcement / authorization plane
                  |
                  | governs configured consequential boundaries
                  v
               AgentOS
      shared execution / workforce plane
        /          |          \
    ALVIRA       ailhat      ASHWOOD
    context      product     workspace /
    surface      intelligence creative surface

This diagram is about the common ecosystem path, not an ownership hierarchy.

ALVIRA, ailhat, and ASHWOOD are independent product surfaces. They may originate
work, supply context, or present outcomes. AgentOS is the integrated execution
plane that carries governed work across them. LEDGATo evaluates/enforces only
the protected consequential boundaries configured to use it.

LEDGATo may also protect a non-AgentOS execution path.

## LEDGATo as both product surface and enforcement plane

AgentOS may build, test, maintain, and deploy the LEDGATo product/repository just as it does for other ecosystem products.

That does not collapse LEDGATo's enforcement role into AgentOS.

The valid loop is:

    AgentOS works on LEDGATo product code
            ↓
    proposed consequential LEDGATo change
            ↓
    independent protected boundary
            ↓
    LEDGATo / provider protections / human approval
            ↓
    exact execution + downstream verification

A self-modifying governance product needs an independent root of trust.

Therefore AgentOS' ability to edit or deploy LEDGATo must never, by itself, authorize changes that can weaken the enforcement boundary.

Enforcement-critical changes include, at minimum:

- policy evaluation logic;
- permit/signature verification;
- approval/decision semantics;
- provider or protected-resource credentials;
- signing keys / trust anchors;
- bypass-prevention configuration;
- protected adapter routing;
- production activation/deactivation;
- evidence integrity or verification paths.

Those changes must preserve independent controls appropriate to the boundary, such as provider-side branch protections, separately scoped credentials, independent review, exact-action approval, and provider/resource-side verification.

LEDGATo must not bootstrap trust solely from its own mutable application code.

## Authentication is not authority

Human authentication answers:

> Who is operating the LEDGATo console?

It does not answer:

> What may an agent execute?

Those are separate control planes.

A valid LEDGATo user session may allow the human to inspect or make an
authorization decision. It must not silently:

- grant standing agent authority;
- widen a task;
- widen a delegation;
- activate an enforcement boundary;
- make a product surface authoritative;
- make an external identity provider an enforcement authority.

## LEDGATo-owned identity/session boundary

Target architecture:

- LEDGATo owns its account/session/tenant membership model.
- LEDGATo issues and validates its own application sessions.
- External identity providers may authenticate or federate a human identity.
- Federation is optional and pluggable.
- No external product-specific session is a mandatory dependency for LEDGATo.
- Losing access to ALVIRA, ailhat, or ASHWOOD must not inherently disable an
  otherwise valid standalone LEDGATo account.
- External identity assertions are authentication evidence, not authority
  grants.

Suitable future identity methods may include passkeys, email/passwordless,
GitHub/Google/enterprise OIDC, or customer-managed SSO. The exact implementation
is separate from the invariant above.

## ALVIRA handoff status

The current ALVIRA owner handoff is a historical compatibility path.

During migration it may remain as an explicit optional federated identity method
for the existing owner account.

It must not be described as:

- the canonical LEDGATo identity source;
- a parent account required to use LEDGATo;
- the authority source for LEDGATo;
- the required onboarding model for future customers.

The compatibility path should be retired as a mandatory dependency once
standalone LEDGATo account authentication is implemented and verified.

## Product-surface relationship

### ALVIRA

Supplies context intelligence when relevant and permitted.

ALVIRA context may affect what LEDGATo explains or what assurance level policy
requires. Context does not grant authority.

### ailhat

Supplies portfolio/product intelligence and may propose work.

Recommendations do not grant authority.

### ASHWOOD

Provides workspace, portfolio, career/funding, evidence, and founder-facing
surfaces.

A UI status or workspace recommendation does not grant authority.

### AgentOS

AgentOS is the primary shared execution integration in this ecosystem.

It may carry:

- task/workflow state;
- active workstream relationships;
- runtime/worker state;
- requested consequential actions;
- provenance/evidence;
- execution results.

LEDGATo consumes the applicable inputs at configured enforcement boundaries and
returns deterministic governance/enforcement results.

AgentOS remains execution. LEDGATo remains enforcement.

## Console login UX

The LEDGATo login route must first render a LEDGATo-owned sign-in landing.

A user may then choose an available identity method.

The browser must not be automatically exported to another product simply because
that product is one available identity provider.

During migration, the existing ALVIRA handoff should be labeled as an optional
linked/federated compatibility method.

## Cross-product implementation guardrail

Do not introduce a cross-product auth dependency merely because two products
belong to the same ecosystem.

Shared AgentOS execution is intentional.

Shared identity is optional.

Shared context is explicit and least-privilege.

LEDGATo enforcement is boundary-specific and independent.
