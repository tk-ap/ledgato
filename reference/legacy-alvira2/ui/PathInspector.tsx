import { useState } from "react";
import type { AgentGraphConfig, AuthPath, GraphNode, PathStatus } from "~/app/data";
import { pathChain } from "./InteractiveGraph";

/**
 * Path Inspector — the "Explore Authority" detail panel.
 *
 * Given a selected PATH it shows WHY it's reachable / which IDENTITY enables it /
 * which POLICY permits it / what ACTION is possible / what DATA is exposed /
 * what RISK / whether Ledgato ALLOWS it — with three actions per path:
 *   Test this path · Explain access · Block path.
 *
 * Given a selected NODE it shows a compact detail plus the paths that run through
 * it (click one to inspect the full chain).
 *
 * The actions run against SAMPLE data and report SAMPLE outcomes — this is the
 * product visual, not a live enforcement backend.
 */

const STATUS_META: Record<PathStatus, { label: string; cls: string; dot: string }> = {
  ALLOW: { label: "ALLOW", cls: "text-mint", dot: "bg-mint" },
  DENY: { label: "DENY", cls: "text-blocked", dot: "bg-blocked" },
  APPROVE: { label: "APPROVE", cls: "text-amber", dot: "bg-amber" },
};

const RISK_META = {
  low: { label: "LOW", cls: "text-mint" },
  medium: { label: "MEDIUM", cls: "text-amber" },
  high: { label: "HIGH", cls: "text-blocked" },
} as const;

function Field({ k, v }: { k: string; v: string }) {
  return (
    <div className="border-b border-white/5 py-3 last:border-b-0">
      <dt className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40">{k}</dt>
      <dd className="mt-1 text-sm leading-relaxed text-white/80">{v}</dd>
    </div>
  );
}

/** Simulated result text per status — SAMPLE probe outcomes. */
function probeResult(status: PathStatus): { label: string; cls: string; detail: string } {
  if (status === "DENY")
    return {
      label: "ATTACK BLOCKED",
      cls: "text-blocked",
      detail: "Probe ATTACK #1837 — stopped at EXTERNAL EGRESS. Egress action refused; attack prevented.",
    };
  if (status === "APPROVE")
    return {
      label: "APPROVAL REQUIRED",
      cls: "text-amber",
      detail: "Action above the autonomous threshold — paused for a human decision.",
    };
  return {
    label: "PASS · ALLOWED",
    cls: "text-mint",
    detail: "Within policy — no egress, no PII leaves the boundary. Control verified.",
  };
}

interface Props {
  config: AgentGraphConfig;
  selectedPath: AuthPath | null;
  selectedNode: GraphNode | null;
  onSelectPath: (id: string | null) => void;
  agentName?: string;
}

export function PathInspector({ config, selectedPath, selectedNode, onSelectPath, agentName }: Props) {
  const [testing, setTesting] = useState<string | null>(null);
  const [ranPaths, setRanPaths] = useState<Record<string, PathStatus>>({});
  const [explainOpen, setExplainOpen] = useState<string | null>(null);
  const [blockedPaths, setBlockedPaths] = useState<Set<string>>(new Set());
  const [blockPending, setBlockPending] = useState(false);

  const chain = selectedPath ? pathChain(config, selectedPath) : [];

  const runTest = (p: AuthPath) => {
    setTesting(p.id);
    setExplainOpen(null);
    setBlockPending(false);
    window.setTimeout(() => {
      setRanPaths((r) => ({ ...r, [p.id]: p.status }));
      setTesting(null);
    }, 900);
  };

  const confirmBlock = (p: AuthPath) => {
    if (blockPending) {
      setBlockedPaths((s) => new Set(s).add(p.id));
      setBlockPending(false);
    } else {
      setBlockPending(true);
    }
  };

  /* ---- NODE selected (compact) ---- */
  if (selectedNode && !selectedPath) {
    const touching = config.paths.filter((p) => p.nodes.includes(selectedNode.id));
    return (
      <Panel title="Node inspected" sub={selectedNode.label}>
        <div className="px-5 py-4">
          <p className="text-sm leading-relaxed text-white/80">{selectedNode.caption}</p>
          <dl className="mt-4">
            <Field k="Layer" v={selectedNode.label} />
            <Field k="Value" v={selectedNode.sub} />
          </dl>
          {touching.length > 0 && (
            <div className="mt-5">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40">
                Paths through this node
              </div>
              <ul className="mt-2 space-y-2">
                {touching.map((p) => {
                  const meta = STATUS_META[p.status];
                  return (
                    <li key={p.id}>
                      <button
                        type="button"
                        onClick={() => onSelectPath(p.id)}
                        className="flex w-full items-center justify-between gap-3 border border-white/10 bg-ink-2/60 px-3 py-2 text-left font-mono text-[11px] uppercase tracking-[0.12em] text-white/75 transition-colors hover:border-white/30 focus:outline-none focus-visible:ring-2 focus-visible:ring-electric"
                      >
                        {p.name}
                        <span className={`inline-flex items-center gap-1.5 ${meta.cls}`}>
                          <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
                          {meta.label}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      </Panel>
    );
  }

  /* ---- PATH selected (full inspector) ---- */
  if (selectedPath) {
    const p = selectedPath;
    const meta = STATUS_META[p.status];
    const risk = RISK_META[p.risk];
    const blocked = blockedPaths.has(p.id);
    const result = ranPaths[p.id];
    return (
      <Panel title="Path inspector" sub={agentName ?? config.agentId}>
        <div className="px-5 py-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-display text-lg font-bold leading-tight text-white">{p.name}</h3>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 font-mono text-[11px] uppercase tracking-[0.16em]">
            <span className={`inline-flex items-center gap-1.5 ${meta.cls}`}>
              <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
              {meta.label}
            </span>
            <span aria-hidden className="text-white/25">·</span>
            <span className={risk.cls}>RISK {risk.label}</span>
            {blocked && (
              <span className="rounded border border-blocked/50 bg-blocked/10 px-2 py-0.5 text-blocked">
                BLOCKED
              </span>
            )}
          </div>

          {/* chain traces through the graph */}
          <div className="mt-4 flex flex-wrap items-center gap-1.5 font-mono text-[10px] tracking-[0.12em] text-white/60">
            {chain.map((c, i) => (
              <span key={i} className="flex items-center gap-1.5">
                <span className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5">{c}</span>
                {i < chain.length - 1 && <span aria-hidden className="text-white/30">→</span>}
              </span>
            ))}
          </div>

          <dl className="mt-4">
            <Field k="Why reachable" v={p.inspector.why} />
            <Field k="Identity enables" v={p.inspector.identity} />
            <Field k="Policy" v={p.inspector.policy} />
            <Field k="Action possible" v={p.inspector.action} />
            <Field k="Data exposed" v={p.inspector.data} />
            <Field k="Risk" v={p.inspector.riskLabel} />
          </dl>

          {/* Explain access */}
          <button
            type="button"
            onClick={() => setExplainOpen(explainOpen === p.id ? null : p.id)}
            className="mt-1 w-full border border-white/10 bg-ink-2/60 px-4 py-2.5 text-left font-mono text-[11px] uppercase tracking-[0.14em] text-electric-soft transition-colors hover:border-electric/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-electric"
            aria-expanded={explainOpen === p.id}
          >
            {explainOpen === p.id ? "Hide explanation" : "Explain access"}
          </button>
          {explainOpen === p.id && (
            <p className="mt-2 rounded border border-white/10 bg-ink-2/40 px-4 py-3 text-sm leading-relaxed text-white/70">
              This path is{" "}
              {blocked
                ? "now denied by a newly added rule."
                : p.status === "ALLOW"
                  ? "reachable because the identity's scoped grant maps 1:1 to an allowed action and no rule permits egress beyond it."
                  : p.status === "DENY"
                    ? "blocked because the egress action is not part of the identity's grant — Ledgato refuses the chain before data leaves the boundary."
                    : "reachable but above the autonomous threshold, so Ledgato pauses it for an explicit approval."}
            </p>
          )}

          {/* Actions */}
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <ActionBtn
              onClick={() => runTest(p)}
              disabled={!!testing}
              className="border-white/20 text-white hover:border-white/45"
            >
              {testing === p.id ? "Testing…" : "Test this path"}
            </ActionBtn>
            <ActionBtn
              onClick={() => setExplainOpen(explainOpen === p.id ? null : p.id)}
              className="border-electric/40 text-electric-soft hover:border-electric"
            >
              Explain access
            </ActionBtn>
            <ActionBtn
              onClick={() => confirmBlock(p)}
              disabled={p.status === "DENY" || blocked}
              className={
                blocked
                  ? "border-blocked/60 text-blocked"
                  : "border-blocked/40 text-blocked hover:border-blocked"
              }
            >
              {blocked ? "Blocked ✓" : blockPending ? "Confirm block — add rule" : "Block path"}
            </ActionBtn>
          </div>

          {/* result / block confirmation */}
          {blockPending && (
            <p className="mt-3 rounded border border-amber/40 bg-amber/10 px-3 py-2 text-sm text-amber">
              Add a rule to fence.yaml denying this path? This requires review before it enforces.
            </p>
          )}
          {blocked && (
            <p className="mt-3 rounded border border-blocked/40 bg-blocked/10 px-3 py-2 text-sm text-blocked">
              Rule staged — this path is now DENIED for {agentName ?? config.agentId}. Pending gate approval.
            </p>
          )}
          {result && testing !== p.id && (
            <div className="mt-3 rounded border border-white/10 bg-ink-2/60 px-4 py-3">
              <div className={`font-mono text-[11px] font-bold uppercase tracking-[0.18em] ${probeResult(result).cls}`}>
                {probeResult(result).label}
              </div>
              <p className="mt-1 text-sm leading-relaxed text-white/70">{probeResult(result).detail}</p>
            </div>
          )}
        </div>
      </Panel>
    );
  }

  /* ---- nothing selected ---- */
  return (
    <Panel title="Explore authority" sub={agentName ?? "environment"}>
      <div className="px-5 py-4">
        <p className="text-sm leading-relaxed text-white/70">
          Select a <span className="text-electric-soft">node</span> in the graph to inspect why it is
          reachable and who permits it — or pick a{" "}
          <span className="text-electric-soft">path</span> from the chips below the graph to trace what
          the agent can actually do along that chain.
        </p>
        <ul className="mt-4 space-y-2 text-sm text-white/60">
          {config.paths.map((p) => (
            <li key={p.id} className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.14em]">
              <span
                aria-hidden
                className={`h-1.5 w-1.5 rounded-full ${STATUS_META[p.status].dot}`}
              />
              {p.name}
              <span className={STATUS_META[p.status].cls}>{STATUS_META[p.status].label}</span>
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}

function Panel({ title, sub, children }: { title: string; sub: string; children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col border border-white/10 bg-ink-2/40">
      <div className="flex items-baseline justify-between gap-3 border-b border-white/10 px-5 py-4">
        <h2 className="font-mono text-[12px] font-medium uppercase tracking-[0.2em] text-white/70">{title}</h2>
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/35">{sub}</span>
      </div>
      <div className="flex-1">{children}</div>
    </div>
  );
}

function ActionBtn({
  onClick,
  disabled,
  className = "",
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`rounded border bg-ink-2/60 px-3 py-2 text-center font-mono text-[11px] uppercase tracking-[0.12em] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-electric disabled:cursor-not-allowed disabled:opacity-40 ${className}`}
    >
      {children}
    </button>
  );
}
