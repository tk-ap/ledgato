import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Eyebrow } from "~/components/app/ui";
import { runAlviraRuntime, type RuntimeRun } from "~/lib/runtime/engine";
import { DriftDemo } from "~/components/app/DriftDemo";
import { AttackProof } from "~/components/app/AttackProof";

/**
 * RUNTIME — REAL ALVIRA runtime enforcement.
 *
 * This is NOT sample data. It fires the real engine's runtime evaluator
 * (`python3 -m ledgato.cli runtime`) against ALVIRA's real discovered actions
 * and its committed runtime policy (`engine-data/alvira-runtime-*.yaml/json`,
 * grounded in ALVIRA's actual source). Each ALVIRA agent action gets a genuine
 * ALLOW / DENY / APPROVE verdict with the matching rule + reason, plus a
 * per-decision Ed25519 signature (evidence-backed decision log). When Python
 * isn't available (serverless Vercel), it shows the honest note and fabricates
 * nothing.
 *
 * The Drift + Attack sections below are the earlier product visuals and remain
 * explicitly labelled SAMPLE.
 */
export const Route = createFileRoute("/app/runtime")({
  component: RuntimeView,
});

const VERDICT_META = {
  ALLOW: {
    label: "ALLOW",
    cls: "text-mint",
    bg: "bg-mint",
    border: "border-mint/40",
    chip: "border-mint/40 bg-mint/10 text-mint",
  },
  DENY: {
    label: "DENY",
    cls: "text-blocked",
    bg: "bg-blocked",
    border: "border-blocked/40",
    chip: "border-blocked/40 bg-blocked/10 text-blocked",
  },
  APPROVE: {
    label: "APPROVAL REQUIRED",
    cls: "text-amber",
    bg: "bg-amber",
    border: "border-amber/40",
    chip: "border-amber/40 bg-amber/10 text-amber",
  },
} as const;

function VerdictChip({ decision }: { decision: "ALLOW" | "DENY" | "APPROVE" }) {
  const m = VERDICT_META[decision];
  return (
    <span className={`inline-flex items-center gap-2 rounded border px-3 py-1 font-mono text-[11px] font-bold uppercase tracking-[0.16em] ${m.chip}`}>
      <span aria-hidden className={`inline-block h-1.5 w-1.5 rounded-full ${m.bg}`} />
      {m.label}
    </span>
  );
}

function DecisionRow({ d }: { d: RuntimeRun["decisions"][number] }) {
  const denied = d.decision === "DENY";
  return (
    <li className={`border-b border-white/5 py-4 last:border-b-0 ${denied ? "bg-blocked/[0.04]" : ""}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <VerdictChip decision={d.decision} />
            <span className="font-mono text-[12px] font-bold text-white">{d.action}</span>
          </div>
          <p className="mt-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-white/45">
            {d.agent} · tool {d.tool ?? "—"}
            {d.network ? ` · network ${d.network}` : ""}
            {d.impact ? ` · impact ${d.impact}` : ""}
          </p>
        </div>
        <span className={`shrink-0 font-mono text-[10px] uppercase tracking-[0.12em] ${d.signature ? "text-white/35" : "text-white/25"}`}>
          {d.signature ? "SIGNED" : "unsigned"}
        </span>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-white/70">{d.reason}</p>
      {d.ruleText && (
        <p className="mt-1.5 font-mono text-[11px] text-electric-soft">rule: {d.ruleText}</p>
      )}
    </li>
  );
}

function RuntimeFeed({ run }: { run: RuntimeRun }) {
  if (run.mode === "serverless") {
    return (
      <div className="border border-amber/40 bg-amber/5 px-5 py-5" role="note">
        <p className="font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-amber">
          Live serverless environment — engine not available here
        </p>
        <p className="mt-2 text-sm leading-relaxed text-white/70">{run.note ?? run.error}</p>
        <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.14em] text-white/45">
          Run locally / in CI to get real ALLOW / DENY / APPROVE decisions.
        </p>
      </div>
    );
  }
  if (run.error) {
    return (
      <div className="border border-blocked/40 bg-blocked/5 px-5 py-5" role="alert">
        <p className="font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-blocked">✕ Runtime engine error</p>
        <p className="mt-2 text-sm leading-relaxed text-white/70">{run.error}</p>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      {/* summary */}
      <div className="grid gap-3 sm:grid-cols-3">
        {(["ALLOW", "DENY", "APPROVE"] as const).map((k) => (
          <div key={k} className={`border px-4 py-4 ${VERDICT_META[k].border}`}>
            <div className={`font-display text-2xl font-bold ${VERDICT_META[k].cls}`}>{run.summary[k]}</div>
            <div className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.18em] text-white/45">{VERDICT_META[k].label}</div>
          </div>
        ))}
      </div>

      <ul className="border border-white/10 bg-ink-2/40 px-5" data-testid="runtime-decisions">
        {run.decisions.map((d, i) => (
          <DecisionRow key={i} d={d} />
        ))}
      </ul>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 border border-white/10 bg-ink-2/40 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.14em] text-white/40">
        <span>policy {run.policy}</span>
        <span>signer {run.signer ? run.signer.slice(0, 14) + "…" : "—"}</span>
        <span>decisions signed · evidence decision log</span>
      </div>
    </div>
  );
}

function RuntimeView() {
  const [run, setRun] = useState<RuntimeRun | null>(null);
  const [running, setRunning] = useState(false);

  async function runNow() {
    if (running) return;
    setRunning(true);
    try {
      const res = await runAlviraRuntime({ data: { run: true } });
      setRun(res);
    } finally {
      setRunning(false);
    }
  }

  return (
    <section>
      <Eyebrow>Runtime enforcement</Eyebrow>
      <h1 className="mt-3 font-display text-4xl font-bold tracking-[-0.02em] sm:text-5xl">Runtime</h1>
      <p className="mt-3 max-w-2xl text-base leading-relaxed text-white/55">
        What happens when an agent actually tries. Ledgato interposes between the
        agent and the tool — inside scope runs, out of scope stops, and anything
        ambiguous pauses for a human. Below is the real engine evaluating ALVIRA's
        real runtime actions.
      </p>

      <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-electric/40 bg-electric/10 px-4 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-electric-soft">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-electric" aria-hidden />
        REAL · ALVIRA · RUNTIME ENFORCEMENT
      </div>

      {/* REAL decision surface */}
      <div className="mt-9">
        <div className="mb-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-electric-soft">01 · LIVE ENFORCEMENT</p>
          <h2 className="mt-1.5 font-display text-2xl font-bold tracking-[-0.01em] sm:text-3xl">
            ALVIRA runtime · real ALLOW / DENY / APPROVE
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-white/50">
            Runs the real engine (<span className="font-mono">python3 -m ledgato.cli runtime</span>) over
            ALVIRA's discovered actions against its runtime policy. Every verdict is a real decision
            from the engine — the matching rule, the reason, and a signed evidence record.
          </p>
        </div>

        <div className="border border-white/10 bg-ink-2/40 px-5 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-mono text-[12px] font-medium uppercase tracking-[0.2em] text-white/70">
                ALVIRA agent · runtime path
              </h3>
              <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.12em] text-white/40">
                {run ? `policy ${run.policy}` : "policy alvira-runtime · 8 actions"} · max_impact write
              </p>
            </div>
            <button
              type="button"
              onClick={runNow}
              disabled={running}
              className="inline-flex items-center gap-2 rounded bg-electric px-4 py-2.5 font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-white transition-colors hover:bg-electric-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-electric disabled:opacity-60"
            >
              {running ? (
                <>
                  <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" aria-hidden />
                  Running real engine…
                </>
              ) : run ? (
                "Run ALVIRA runtime again"
              ) : (
                "Run ALVIRA runtime"
              )}
            </button>
          </div>

          <div className="mt-5">
            {run ? (
              <RuntimeFeed run={run} />
            ) : running ? (
              <div className="space-y-2">
                <div className="h-3 w-1/3 animate-pulse rounded bg-white/10" />
                <div className="h-6 w-2/3 animate-pulse rounded bg-white/10" />
                <div className="h-3 w-1/2 animate-pulse rounded bg-white/10" />
              </div>
            ) : (
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">
                Press "Run ALVIRA runtime" to evaluate ALVIRA's real agent actions against policy.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* SAMPLE product visuals — labelled */}
      <div className="mt-12">
        <div className="mb-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40">02 · DRIFT</p>
          <span className="mt-1 inline-block rounded border border-white/15 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-white/40">SAMPLE</span>
          <h2 className="mt-1.5 font-display text-2xl font-bold tracking-[-0.01em] sm:text-3xl">Drift before / after</h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-white/50">
            Product visual — demonstration data, not live usage.
          </p>
        </div>
        <div className="border border-white/10 bg-ink-2/40 p-4">
          <DriftDemo />
        </div>
      </div>

      <div className="mt-12">
        <div className="mb-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40">03 · ATTACK &amp; PROOF</p>
          <span className="mt-1 inline-block rounded border border-white/15 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-white/40">SAMPLE</span>
          <h2 className="mt-1.5 font-display text-2xl font-bold tracking-[-0.01em] sm:text-3xl">Attack replay</h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-white/50">
            Product visual — demonstration data, not live usage.
          </p>
        </div>
        <div className="border border-white/10 bg-ink-2/40 p-4">
          <AttackProof auto />
        </div>
      </div>
    </section>
  );
}
