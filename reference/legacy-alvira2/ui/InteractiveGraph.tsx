import { useId, useMemo, useState } from "react";
import type { AgentGraphConfig, AuthPath, GraphNode } from "~/app/data";
import { edgesFor } from "~/app/data";

/**
 * InteractiveGraph — the product's signature "Explore Authority" graph.
 * Renders an agent's layer graph (AGENT → IDENTITY → TOOLS → RESOURCES →
 * ACTIONS → DATA → NETWORK) and lets you explore it:
 *
 *  - Click / focus a NODE → it highlights, unrelated nodes dim, and the
 *    hover caption explains why it's reachable (details live in the panel).
 *  - Click a PATH (chip below or via the inspector) → that chain is traced
 *    through the graph and emphasized; everything outside it dims.
 *  - Risky edges (a risky node endpoint) render in the semantic blocked tone;
 *    DENY paths show a ⚠ DENIED tag.
 *
 * Pure inline SVG + CSS, no animation library. Keyboard/ARIA accessible:
 * every node is focusable with an aria-label and aria-pressed; nodes and path
 * chips are keyboard-operable; risk is conveyed by text, never colour alone.
 * Reduced-motion users get a static graph.
 */

const BW = 122;
const BH = 54;
const VIEW_W = 1040;
const VIEW_H = 600;

/** edgeKind: a pair touching a risky node is a risky (blocked-tone) edge */
function edgeIsRisk(a: GraphNode, b: GraphNode) {
  return Boolean(a.risk || b.risk);
}

interface Props {
  config: AgentGraphConfig;
  selectedPathId: string | null;
  selectedNodeId: string | null;
  onSelectPath: (id: string | null) => void;
  onSelectNode: (id: string | null) => void;
}

export function InteractiveGraph({
  config,
  selectedPathId,
  selectedNodeId,
  onSelectPath,
  onSelectNode,
}: Props) {
  const titleId = useId();
  const [hover, setHover] = useState<string | null>(null);

  const byId = useMemo(() => {
    const m = new Map<string, GraphNode>();
    config.nodes.forEach((n) => m.set(n.id, n));
    return m;
  }, [config.nodes]);

  const edges = useMemo(() => edgesFor(config), [config]);

  /* selected path's node set + edge set */
  const selectedPath = selectedPathId
    ? config.paths.find((p) => p.id === selectedPathId) ?? null
    : null;

  const pathNodeSet = useMemo(
    () => (selectedPath ? new Set(selectedPath.nodes) : null),
    [selectedPath],
  );
  const pathEdgeSet = useMemo(() => {
    if (!selectedPath) return null;
    const s = new Set<string>();
    for (let i = 0; i < selectedPath.nodes.length - 1; i++) {
      s.add(`${selectedPath.nodes[i]}:${selectedPath.nodes[i + 1]}`);
      s.add(`${selectedPath.nodes[i + 1]}:${selectedPath.nodes[i]}`);
    }
    return s;
  }, [selectedPath]);

  /* neighbourhood for a selected node (it + its direct neighbours) */
  const nodeNeighbours = useMemo(() => {
    if (!selectedNodeId) return null;
    const s = new Set<string>([selectedNodeId]);
    edges.forEach(([a, b]) => {
      if (a === selectedNodeId) s.add(b);
      if (b === selectedNodeId) s.add(a);
    });
    return s;
  }, [selectedNodeId, edges]);

  const activeSet = pathNodeSet ?? nodeNeighbours;
  const suppress = (id: string) =>
    activeSet ? !activeSet.has(id) : false;

  const activeEdge = (a: string, b: string) => {
    if (pathEdgeSet) return pathEdgeSet.has(`${a}:${b}`);
    // node selection: an edge is active if BOTH endpoints are active
    return nodeNeighbours ? nodeNeighbours.has(a) && nodeNeighbours.has(b) : true;
  };

  /* a node is "lit" if it's in the active set (or nothing selected) */
  const lit = (id: string) => (activeSet ? activeSet.has(id) : true);

  const focusNode = hover ?? selectedNodeId ?? null;

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        role="group"
        aria-labelledby={titleId}
        className="mx-auto w-full min-w-[640px] max-w-[1040px] select-none"
      >
        <title id={titleId}>
          {config.agentId} authority graph — agents to identity, tools, resources,
          actions, data and network
        </title>
        <desc>
          Select a node to inspect why it is reachable and who permits it. Select a
          path to trace exactly what an agent can do along that chain. Risky egress
          paths render in blocked red and show a DENIED tag.
        </desc>

        {/* ---- edges ---- */}
        {edges.map(([a, b]) => {
          const na = byId.get(a)!;
          const nb = byId.get(b)!;
          const risk = edgeIsRisk(na, nb);
          const on = activeEdge(a, b);
          const key = `${a}:${b}`;
          const stroke = risk ? "#ff6b6b" : selectedPath?.status === "APPROVE" ? "#f5a623" : "#2e7bff";
          const isSelectedEdge = pathEdgeSet ? pathEdgeSet.has(key) : false;
          return (
            <g key={key} opacity={on ? 1 : 0.12} style={{ transition: "opacity .3s" }}>
              <line
                x1={na.x}
                y1={na.y}
                x2={nb.x}
                y2={nb.y}
                stroke={stroke}
                strokeOpacity={risk ? 0.7 : selectedPath ? 1 : 0.5}
                strokeWidth={isSelectedEdge || selectedPath ? 2 : 1.4}
              />
              {selectedPath && (
                <line
                  x1={na.x}
                  y1={na.y}
                  x2={nb.x}
                  y2={nb.y}
                  className="ag-flow"
                  stroke={stroke}
                  strokeWidth={1.8}
                  strokeOpacity={0.9}
                />
              )}
            </g>
          );
        })}

        {/* ---- nodes ---- */}
        {config.nodes.map((d) => {
          const left = d.x - BW / 2;
          const top = d.y - BH / 2;
          const isActive = lit(d.id);
          const dimmed = suppress(d.id);
          const isFocused = focusNode === d.id;
          const isNodeSelected = selectedNodeId === d.id;
          const fill = d.risk ? "#2a0f13" : isFocused || isNodeSelected ? "#1f3a6b" : "#15161a";
          const stroke = d.risk ? "#ff6b6b" : isFocused || isNodeSelected ? "#2e7bff" : "#ffffff26";
          return (
            <g key={d.id} opacity={isActive && !dimmed ? 1 : 0.2} style={{ transition: "opacity .3s" }}>
              <g
                role="button"
                tabIndex={0}
                aria-pressed={isNodeSelected}
                aria-label={`${d.label} ${d.sub} — ${d.caption}`}
                onMouseEnter={() => setHover(d.id)}
                onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(d.id)}
                onBlur={() => setHover(null)}
                onClick={() => onSelectNode(d.id === selectedNodeId ? null : d.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelectNode(d.id === selectedNodeId ? null : d.id);
                  }
                }}
                className="cursor-pointer focus:outline-none focus-visible:[&>rect]:stroke-electric"
                style={{ transition: "opacity .3s" }}
              >
                <rect
                  x={left}
                  y={top}
                  width={BW}
                  height={BH}
                  rx="7"
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={isFocused || isNodeSelected || d.risk ? 1.6 : 1}
                />
                <rect
                  x={left}
                  y={top}
                  width={BW}
                  height={BH}
                  rx="7"
                  fill="none"
                  stroke="#7fb0ff"
                  strokeWidth="1"
                  strokeOpacity={isNodeSelected ? 0.7 : 0}
                />
                <text
                  x={d.x}
                  y={top + 22}
                  textAnchor="middle"
                  className="font-mono"
                  fontSize="11"
                  fontWeight="700"
                  letterSpacing="1.5"
                  fill="#fff"
                >
                  {d.label}
                </text>
                <text
                  x={d.x}
                  y={top + 38}
                  textAnchor="middle"
                  fontSize="10"
                  fill={d.risk ? "#ffb4b4" : "#9aa3b2"}
                >
                  {d.sub}
                </text>
              </g>

              {/* hover / focus caption */}
              {isFocused && (
                <g pointerEvents="none">
                  <rect
                    x={Math.max(8, Math.min(d.x - 130, VIEW_W - 260) )}
                    y={d.y < VIEW_H / 2 ? d.y - BH / 2 - 46 : d.y + BH / 2 + 10}
                    width={260}
                    height={36}
                    rx="6"
                    fill="#0a0a0a"
                    stroke="#2e7bff"
                    strokeOpacity="0.5"
                    strokeWidth="1"
                  />
                  <text
                    x={Math.max(8, Math.min(d.x - 130, VIEW_W - 260)) + 12}
                    y={d.y < VIEW_H / 2 ? d.y - BH / 2 - 46 + 22 : d.y + BH / 2 + 10 + 22}
                    fontSize="10.5"
                    fill="#dbe6ff"
                    className="font-mono"
                  >
                    {d.caption}
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {/* ---- risk legend caption (bottom-left) — derived from the real paths ---- */}
        <g style={{ pointerEvents: "none" }} className="font-mono">
          {(() => {
            const deny = config.paths.find((p) => p.status === "DENY");
            const approve = config.paths.find((p) => p.status === "APPROVE");
            const allow = config.paths.find((p) => p.status === "ALLOW");
            const primary = deny ?? approve ?? allow;
            const line1 = primary ? primary.name : "no paths";
            const line2 = deny
              ? `✕ ACTION DENIED — blocked by policy`
              : approve
                ? "■ approval required — paused for human"
                : "✓ within policy — allowed";
            return (
              <>
                <text x={20} y={VIEW_H - 30} fontSize="11" letterSpacing="1" fill="#7fb0ff">
                  {line1}
                </text>
                <text x={20} y={VIEW_H - 12} fontSize="10" letterSpacing="1" fill={deny ? "#ffb4b4" : approve ? "#ffd9a0" : "#9dffce"}>
                  {line2}
                </text>
              </>
            );
          })()}
        </g>

        {/* ---- DENIED tag on a selected DENY path / risky network ---- */}
        {selectedPath?.status === "DENY" && (
          <g pointerEvents="none">
            <rect x={VIEW_W - 250} y={20} width={232} height={28} rx="4" fill="#2a0f13" stroke="#ff6b6b" strokeWidth="1" />
            <text x={VIEW_W - 146} y={38} textAnchor="middle" className="font-mono" fontSize="11" fontWeight="700" letterSpacing="1" fill="#ff6b6b">
              ⚠ ACTION DENIED
            </text>
          </g>
        )}
      </svg>

      {/* ---- path chips (keyboard-accessible path selection) ---- */}
      <div
        role="listbox"
        aria-label="Selectable authority paths"
        className="mt-4 flex flex-wrap items-center gap-2"
      >
        {config.paths.map((p) => {
          const active = selectedPathId === p.id;
          const tone =
            p.status === "DENY"
              ? "border-blocked/50 text-blocked hover:border-blocked"
              : p.status === "APPROVE"
                ? "border-amber/50 text-amber hover:border-amber"
                : "border-electric/40 text-electric-soft hover:border-electric";
          const activeCls = active ? "bg-white/10 ring-1 ring-white/25" : "";
          return (
            <button
              key={p.id}
              role="option"
              aria-selected={active}
              type="button"
              onClick={() => onSelectPath(active ? null : p.id)}
              className={`inline-flex items-center gap-2 rounded-full border bg-ink-2/60 px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-electric ${tone} ${activeCls}`}
            >
              <span aria-hidden>{p.status === "DENY" ? "✕" : p.status === "APPROVE" ? "■" : "✓"}</span>
              {p.name}
              <span aria-hidden className="opacity-50">· {p.status}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Tiny helper to derive the ordered node labels for a path (used in the inspector). */
export function pathChain(config: AgentGraphConfig, path: AuthPath): string[] {
  const byId = new Map(config.nodes.map((n) => [n.id, n.label]));
  return path.nodes.map((n) => byId.get(n) ?? n);
}
