import { useRef, useState } from "react";
import { attackBlock, attackChain } from "~/app/data";

/**
 * ATTACK / PROOF moment — the "it tried to escape" replay:
 *   prompt injection → retrieval → credential discovery → external request
 *   → LEDGATO POLICY · EXTERNAL EGRESS · DENIED → ATTACK BLOCKED
 * then an evidence strip: ATTACK BLOCKED · POLICY v17 · AGENT v2.4 ·
 * EVIDENCE GENERATED.
 *
 * Pure CSS + React timers, no animation library. Reduced-motion users get a
 * single-step reveal (all steps visible immediately).
 */

type Phase = "idle" | "running" | "blocked" | "proof";

export function AttackProof({
  auto,
  initReduced,
}: {
  auto?: boolean;
  initReduced?: boolean;
}) {
  const [phase, setPhase] = useState<Phase>(auto ? "blocked" : "idle");
  const timer = useRef<number | undefined>(undefined);

  const reduced = initReduced ?? false;
  const running = phase === "running";

  const replay = () => {
    if (timer.current) window.clearTimeout(timer.current);
    setPhase("running");
    if (reduced) {
      setPhase("blocked");
      setPhase("proof");
      return;
    }
    timer.current = window.setTimeout(() => setPhase("blocked"), 2600);
    timer.current = window.setTimeout(() => setPhase("proof"), 3600);
  };

  const stepVisible = () =>
    phase === "blocked" || phase === "proof" || phase === "running";

  return (
    <div className="flex h-full flex-col border border-white/10 bg-ink-2/40" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
        <h2 className="font-mono text-[12px] font-medium uppercase tracking-[0.2em] text-white/70">
          Replay {attackBlock.probe}
        </h2>
        <button
          type="button"
          onClick={replay}
          disabled={running}
          className="rounded border border-electric/50 bg-electric/10 px-3.5 py-1.5 font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-electric-soft transition-colors hover:bg-electric/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-electric disabled:cursor-not-allowed disabled:opacity-40"
          data-testid="attack-replay"
        >
          {running ? "Blocking…" : "Replay attack"}
        </button>
      </div>

      <div className="flex-1 px-5 py-5">
        <ol className="space-y-2 font-mono text-[11px]" data-testid="attack-chain">
          {attackChain.map((a) => (
            <li
              key={a}
              className={`rounded border px-3 py-2 transition-all ${
                stepVisible()
                  ? "border-white/12 bg-white/[0.03] text-white/80"
                  : "border-transparent text-white/25"
              }`}
            >
              {stepVisible() ? a : "•••• •••••••••"}
            </li>
          ))}
          <li
            className={`rounded border px-3 py-2 font-bold uppercase tracking-[0.14em] transition-all ${
              phase === "blocked" || phase === "proof"
                ? "border-blocked/50 bg-blocked/10 text-blocked"
                : "border-transparent text-white/25"
            }`}
            data-testid="attack-block"
          >
            ✕ {attackBlock.summary} — {attackBlock.outcome}
          </li>
        </ol>
      </div>

      {/* evidence strip */}
      <div className="mt-auto border-t border-white/10 px-5 py-4" data-testid="evidence">
        {(phase === "proof" || (reduced && phase !== "idle")) ? (
          <div
            className="ag-tag grid gap-2 rounded border border-mint/40 bg-mint/10 px-4 py-3 sm:grid-cols-4"
            role="status"
          >
            <span className="font-mono text-[11px] font-bold uppercase tracking-[0.16em] text-mint">
              {attackBlock.outcome}
            </span>
            {attackBlock.evidence.map((e) => (
              <span key={e} className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/70">
                {e}
              </span>
            ))}
          </div>
        ) : phase === "blocked" ? (
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/40">
            Generating tamper-evident evidence…
          </div>
        ) : (
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/40">
            Idle — replay an attack to see enforcement + evidence.
          </div>
        )}
      </div>
    </div>
  );
}
