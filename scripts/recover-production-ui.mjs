import { mkdir, rm, writeFile } from "node:fs/promises";
import { dirname, extname, join } from "node:path";
import { createHash } from "node:crypto";

// The live UI was deployed from local prebuilt output, not current GitHub source.
// Until that source is recovered, use the immutable READY deployment as the exact
// visual/route source and patch text only. CSS, geometry, motion and assets stay intact.
const SOURCE = "https://ledgato-47k586kdi-alvira2.vercel.app";
const OUT = "dist";

const replacements = [
  ["LIVE · ENFORCING POLICY", "DEMO · SAMPLE ENVIRONMENT"],
  ["Ledgato continuously maps agent permissions, attacks dangerous paths, and blocks actions that violate policy.", "Ledgato independently authorizes consequential agent actions at protected boundaries, then verifies and records what happened."],
  ["If an agent shouldn't be able to do it, Ledgato stops it.", "When a protected action is routed through Ledgato, DENY means the downstream action does not execute."],
  ["A live graph from agent to identity to tools to resources to actions to data to network. Risky paths are highlighted (CRM.read → Customer.email → HTTP POST → external-site ⚠ EXFILTRATION); dangerous actions are denied.", "An example graph from agent to identity to tools to resources to actions to data to network. It illustrates a protected route where external egress is denied before execution."],
  ["A live graph from agent to identity and tools, to resources, to actions, to data, to network. The path CRM.read to Customer.email to HTTP POST to external-site is flagged as a possible exfiltration and denied.", "An example graph from agent to identity and tools, to resources, to actions, to data, to network. The illustrated external-egress path is denied at the protected boundary."],
  ["● LIVE · ENFORCING", "● DEMO · SAMPLE ENVIRONMENT"],
  ["Wire up every agent, tool, API and identity. If it can reach your stack, Ledgato can see it.", "Connect the agents, tools, identities, and protected actions you want Ledgato to govern."],
  ["Map what each agent can actually read, write, call and exfiltrate — not what the docs claim.", "Within connected integrations, compare what an agent can reach with the authority it was actually given."],
  ["Attack and regression-test the boundary. Probes try to escape; drift stops before it ships.", "Attack and regression-test connected boundaries. Failed or drifted checks can gate the protected workflow before release."],
  ["Interpose ALLOW / DENY / APPROVE at runtime. If an agent shouldn't, Ledgato stops it.", "Interpose ALLOW / DENY / APPROVE before a protected downstream action is invoked."],
  ["Adversarial and regression probes attack the declared scope. Anything that escapes, drifts, or exfiltrates is caught and blocked before release.", "Adversarial and regression probes test declared boundaries. Failed or drifted checks can gate the protected workflow before release."],
  ["Ledgato interposes between the agent and the tool. Inside scope runs; out of scope is stopped — or waits for a human.", "For actions routed through its gateway, Ledgato returns ALLOW / DENY / APPROVE before the downstream tool is invoked."],
  ["RUNTIME · decision interposed", "INTERACTIVE DEMO · NO EXTERNAL ACTION"],
  ["#1837 — it tried to escape.", "Real GitHub denial proof."],
  ["Attack paths are replayed against the live agent. Prompt injection, retrieval, credential discovery, external egress — the boundary holds.", "A real merge request was routed through Ledgato in CI. Policy returned DENY; GitHub's merge endpoint was not called; readback confirmed the pull request remained open."],
  ["ledgato probe --replay #1837", "verified proof · github.pull.merge"],
  ["prompt injection :: system override", "protected credential :: held by Ledgato gateway"],
  ["→ retrieval :: customer records", "→ request :: github.pull.merge"],
  ["→ credential discovery :: svc-support", "→ policy :: DENY"],
  ["→ external request :: media-cdn.example", "→ GitHub readback :: pull request remained open"],
  ["✕ LEDGATO POLICY · EXTERNAL EGRESS · DENIED — ATTACK BLOCKED", "✓ VERIFIED REAL ENFORCEMENT PROOF · TESTED GITHUB BOUNDARY"],
  ["REPLAY ATTACK", "REPLAY PROOF"],
  ["No. The tamper-evident ledger is infrastructure, not the product. Ledgato is an authorization control plane — who can reach what, and who gets stopped when they shouldn't.", "No. The tamper-evident ledger is infrastructure, not the product. Ledgato is an independent authorization and enforcement layer for consequential agent actions."],
  ["No. Ledgato verifies boundaries, gates releases, and at runtime interposes ALLOW / DENY / APPROVE between an agent and the tools it calls — with defensible proof your controls are containing it.", "No. Ledgato complements runtime controls. Where a consequential action is routed through its enforcement gateway, it can return ALLOW / DENY / APPROVE before execution and record independent evidence afterward."],
  ["Yes. Run ledgato check and attestation as a gate step. A drifted or failed run returns GATED and blocks the build; a clean run returns APPROVED with signed evidence.", "Yes. Configure Ledgato as a required gate in CI/CD. A failed or drifted check can block the protected workflow; a clean run can attach signed evidence."],
  ["Tell us what your agents can reach today. We'll map it, attack it, and show you exactly where it breaks.", "Tell us which agent workflow and consequential action you want to place behind a boundary. We'll map the route, test bypasses, and define what is actually enforced."],
  ["The authorization and security control plane for AI agents.", "Independent authorization and enforcement for consequential AI actions."],
  ["Ledgato — Know exactly what your AI agents can do.", "Ledgato — Independent authorization for consequential AI actions."],
  ["Ledgato — the AI-agent authorization control plane", "Ledgato — independent authorization and enforcement for AI agents"],
  ["Discover, declare, verify, enforce and prove what your AI agents can reach.", "Authorize protected agent actions before execution and verify what happened afterward."],
];

const required = [
  replacements[0][0],
  replacements[2][0],
  replacements[6][0],
  replacements[10][0],
  replacements[5][0],
  replacements[13][0],
];

const fetched = new Map();
const queue = ["/"];
const queued = new Set(queue);

function isText(path, type = "") {
  return /(?:text|javascript|json|svg|css|html)/i.test(type) || [".js", ".css", ".html", ".svg", ".json", ".map"].includes(extname(path));
}
function target(path) { return path === "/" ? join(OUT, "index.html") : join(OUT, path.replace(/^\//, "")); }
function resolveRef(ref, from) {
  if (!ref || ref.startsWith("data:") || ref.startsWith("mailto:") || ref.startsWith("#") || /[${}]/.test(ref)) return null;
  try {
    const u = new URL(ref, from);
    if (u.origin !== new URL(SOURCE).origin) return null;
    return u.pathname === "/" || u.pathname === "/favicon.svg" || u.pathname.startsWith("/assets/") ? u.pathname : null;
  } catch { return null; }
}
function discover(text, from) {
  const refs = new Set();
  const patterns = [
    /(?:src|href)=["']([^"']+)["']/g,
    /["'`](\.\.?\/[^"'`]+\.(?:js|css|svg|woff2?|png|jpe?g|webp|ico))["'`]/g,
    /["'`](\/assets\/[^"'`]+)["'`]/g,
    /url\((?:["']?)([^)"']+)(?:["']?)\)/g,
  ];
  for (const re of patterns) for (const m of text.matchAll(re)) {
    const path = resolveRef(m[1], from);
    if (path) refs.add(path);
  }
  return refs;
}
function patch(text, counts) {
  let out = text;
  for (const [from, to] of replacements) {
    const n = out.split(from).length - 1;
    if (n) { counts.set(from, (counts.get(from) || 0) + n); out = out.split(from).join(to); }
  }
  return out;
}

await rm(OUT, { recursive: true, force: true });
await mkdir(OUT, { recursive: true });
while (queue.length) {
  const path = queue.shift();
  const url = new URL(path, SOURCE).href;
  const response = await fetch(url, { redirect: "follow" });
  if (!response.ok) throw new Error(`Failed to recover ${url}: ${response.status}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  const type = response.headers.get("content-type") || "";
  fetched.set(path, { bytes, type, url });
  if (isText(path, type)) for (const child of discover(bytes.toString("utf8"), url)) {
    if (!queued.has(child)) { queued.add(child); queue.push(child); }
  }
}

const counts = new Map();
const manifest = [];
for (const [path, item] of fetched) {
  const bytes = isText(path, item.type) ? Buffer.from(patch(item.bytes.toString("utf8"), counts)) : item.bytes;
  const file = target(path);
  await mkdir(dirname(file), { recursive: true });
  await writeFile(file, bytes);
  manifest.push({ path, bytes: bytes.length, sha256: createHash("sha256").update(bytes).digest("hex") });
}
for (const needle of required) if (!counts.get(needle)) throw new Error(`Required production claim not found: ${needle}`);
await writeFile(join(OUT, "production-ui-recovery.json"), JSON.stringify({ source: SOURCE, recoveredAt: new Date().toISOString(), files: manifest, replacements: Object.fromEntries(counts) }, null, 2));
console.log(`Recovered ${manifest.length} production files; applied ${[...counts.values()].reduce((a,b)=>a+b,0)} truth-label replacements.`);
