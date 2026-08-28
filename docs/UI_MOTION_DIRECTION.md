# Ledgato UI motion direction

Scroll-triggered transitions are part of Ledgato's core product language. They explain how authority moves from an agent request to a policy decision, not merely decorate the page.

## Required behavior

- Major sections reveal when they enter the viewport and reset predictably when they leave.
- Repeated structures reveal sequentially so their order is understandable.
- The authority graph builds from agent to identity, tools, resources, actions, and consequence.
- Dangerous paths progress from neutral context to visible warning to blocked outcome.
- The control loop preserves the order Connect, Discover, Declare, Verify, Enforce, Prove.
- Real result states animate only after the service responds; animation must never imply a result before one exists.
- Direct navigation to an anchored section must reveal that section immediately.
- Interaction is never delayed while animation finishes.
- The interface remains complete when JavaScript is unavailable.
- `prefers-reduced-motion: reduce` removes movement and exposes the final state immediately.

## Acceptance standard

The current production interface at `ledgato.vercel.app` is the minimum motion-quality reference. A replacement must preserve its narrative pacing, sticky context, state transitions, and mobile legibility before it can be considered integrated.

## Motion restraint

Motion is justified only when it communicates sequence, causality, hierarchy, or state change. Decorative animation that competes with the authorization story should be removed.
