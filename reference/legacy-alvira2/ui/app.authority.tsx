import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Eyebrow, LoadingState } from "~/components/app/ui";
import { InteractiveGraph } from "~/components/app/InteractiveGraph";
import { PathInspector } from "~/components/app/PathInspector";
import { useRealData } from "~/lib/dashboard/real-data";

/**
 * Explore Authority — the signature product experience.
 * Fed entirely from REAL ALVIRA data: the interactive authority graph shows the
 * real product agent's genuine ALLOW / DENY / APPROVE decisions (from the real
 * engine runtime run) plus each fence agent's real declared scope, with a path
 * inspector that explains WHY each path is reachable and how Ledgato treats it.
 * When the engine isn't available (serverless), it shows an honest note instead
 * of fabricated paths.
 */
export const Route = createFileRoute("/app/authority")({
  component: AuthorityView,
});

function AuthorityView() {
  const { data, loading } = useRealData();
  const agents = data?.agents ?? [];
  const [agentId, setAgentId] = useState("alvira");
  const emptyCfg = { agentId, nodes: [], paths: [] };
  const config =
    agentId === "alvira" ? (data?.authorityConfig ?? emptyCfg) : (data?.graphConfigs?.[agentId] ?? data?.authorityConfig ?? emptyCfg);

  const [selectedPathId, setSelectedPathId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const selectedPath = config?.paths?.find((p) => p.id === selectedPathId) ?? null;
  const selectedNode = config?.nodes?.find((n) => n.id === selectedNodeId) ?? null;
  const firstPathId = config?.paths?.[0]?.id ?? null;
  useEffect(() => {
    if (firstPathId && !selectedPathId) setSelectedPathId(firstPathId);
  }, [firstPathId, selectedPathId]);

  const pickAgent = (id: string) => {
    setAgentId(id);
    setSelectedPathId(config?.paths?.[0]?.id ?? null);
    setSelectedNodeId(null);
  };

  return (
    <section>
      <Eyebrow>Explore authority</Eyebrow>
      <h1 className="mt-3 font-display text-4xl font-bold tracking-[-0.02em] sm:text-5xl">Authority</h1>
      <p className="mt-3 max-w-2xl text-base leading-relaxed text-white/55">
        Real ALVIRA authority — the genuine ALLOW / DENY / APPROVE decisions from the runtime engine
        and each fence agent's declared scope. Select a path to see why it's reachable and what Ledgato enforces.
      </p>

      {data?.mode === "serverless" && (
        <p className="mt-4 max-w-2xl font-mono text-[11px] leading-relaxed text-amber">
          {data.note} Run locally / CI at port 3000 to see the real authority graph — nothing is fabricated.
        </p>
      )}

      {loading ? (
        <div className="mt-8">
          <LoadingState label="Loading real authority" />
        </div>
      ) : agents.length === 0 && data?.mode !== "serverless" ? (
        <p className="mt-8 font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">
          No real authority data loaded yet.
        </p>
      ) : (
        <>
          {/* Agent selector */}
          <div className="mt-7 flex flex-wrap items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40">Agent</span>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Choose an agent">
              <button
                key="alvira"
                type="button"
                onClick={() => pickAgent("alvira")}
                aria-pressed={agentId === "alvira"}
                className={`rounded border px-3.5 py-2 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-electric ${
                  agentId === "alvira"
                    ? "border-electric bg-electric/15 text-electric-soft"
                    : "border-white/10 bg-ink-2/50 text-white/55 hover:border-white/30 hover:text-white"
                }`}
              >
                ALVIRA Product
                <span aria-hidden className="ml-2 opacity-50">· runtime agent</span>
              </button>
              {agents.map((a) => {
                const active = a.id === agentId;
                return (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => pickAgent(a.id)}
                    aria-pressed={active}
                    className={`rounded border px-3.5 py-2 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-electric ${
                      active
                        ? "border-electric bg-electric/15 text-electric-soft"
                        : "border-white/10 bg-ink-2/50 text-white/55 hover:border-white/30 hover:text-white"
                    }`}
                  >
                    {a.name}
                    <span aria-hidden className="ml-2 opacity-50">· {a.id}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Graph + inspector */}
          <div className="mt-6 grid gap-6 lg:grid-cols-5">
            <div className="border border-white/10 bg-ink-2/40 lg:col-span-3">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4 sm:px-6">
                <h2 className="font-mono text-[12px] font-medium uppercase tracking-[0.2em] text-white/70">
                  Authority map
                </h2>
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-electric-soft">
                  REAL · ALVIRA · {agentId === "alvira" ? "engine runtime" : "fence scope"}
                </span>
              </div>
              <div className="px-2 py-4 sm:px-4">
                <InteractiveGraph
                  config={config}
                  selectedPathId={selectedPathId}
                  selectedNodeId={selectedNodeId}
                  onSelectPath={(id) => {
                    setSelectedPathId(id);
                    if (id) setSelectedNodeId(null);
                  }}
                  onSelectNode={(id) => {
                    setSelectedNodeId(id);
                    if (id) setSelectedPathId(null);
                  }}
                />
              </div>
            </div>

            <div className="lg:col-span-2">
              <PathInspector
                config={config}
                selectedPath={selectedPath}
                selectedNode={selectedNode}
                onSelectPath={(id) => {
                  setSelectedPathId(id);
                  if (id) setSelectedNodeId(null);
                }}
                agentName={agentId === "alvira" ? "ALVIRA Product" : agents.find((a) => a.id === agentId)?.name}
              />
            </div>
          </div>

          {/* All real paths overview */}
          <div className="mt-8 border border-white/10 bg-ink-2/40">
            <div className="flex items-center justify-between gap-3 border-b border-white/10 px-5 py-4 sm:px-6">
              <h2 className="font-mono text-[12px] font-medium uppercase tracking-[0.2em] text-white/70">
                Capture & enforce · every real path
              </h2>
              <Link
                to="/app/agents"
                className="inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-[0.16em] text-electric-soft transition-colors hover:text-electric focus:outline-none focus-visible:ring-2 focus-visible:ring-electric"
              >
                Open agent inventory <span aria-hidden>→</span>
              </Link>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-left">
                <thead>
                  <tr className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/40">
                    <th className="px-5 py-3 font-medium sm:px-6">Scope</th>
                    <th className="px-4 py-3 font-medium">Path</th>
                    <th className="px-4 py-3 font-medium">Risk</th>
                    <th className="px-4 py-3 font-medium">Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {(config?.paths ?? []).map((p) => {
                    const tone = p.status === "DENY" ? "text-blocked" : p.status === "APPROVE" ? "text-amber" : "text-mint";
                    const riskTone =
                      p.risk === "high" ? "text-blocked" : p.risk === "medium" ? "text-amber" : "text-mint";
                    return (
                      <tr key={p.id} className="border-t border-white/5 transition-colors hover:bg-white/[0.03]">
                        <td className="px-5 py-3 font-mono text-[11px] uppercase tracking-[0.14em] text-white/60 sm:px-6">
                          {agentId === "alvira" ? "runtime" : agentId}
                        </td>
                        <td className="px-4 py-3 text-sm text-white/80">{p.name}</td>
                        <td className={`px-4 py-3 font-mono text-[11px] uppercase tracking-[0.14em] ${riskTone}`}>
                          {p.risk}
                        </td>
                        <td className={`px-4 py-3 font-mono text-[11px] font-bold uppercase tracking-[0.14em] ${tone}`}>
                          {p.status}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="border-t border-white/5 px-5 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-white/30 sm:px-6">
              REAL paths — derived from the committed ALVIRA fence and the real engine runtime decisions.
            </p>
          </div>
        </>
      )}
    </section>
  );
}
