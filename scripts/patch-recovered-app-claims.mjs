import { readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";

const replacements = [
  [
    "Real ALVIRA data — derived from the live engine and committed discovery. Every agent, its authority, and what Ledgato is enforcing right now.",
    "ALVIRA-connected data is shown only when the engine is reachable. This view distinguishes engine-derived state from unavailable or user-entered workspace data.",
  ],
  ["REAL · ALVIRA · ENGINE-DERIVED", "ALVIRA · CONNECTION STATUS"],
  ["Running real engine & discovery", "Checking engine & discovery"],
  [
    "Run locally / CI at port 3000 where Python exists to see the real ALVIRA metrics — nothing is fabricated.",
    "This hosted surface does not have the Python engine. Run in a supported local/CI host to view engine-derived ALVIRA metrics; unavailable data is not fabricated.",
  ],
  ["Start controlling your agents", "Start governing protected agent actions"],
  [
    "One workspace to see every agent's authority and block what it shouldn't reach.",
    "One workspace to inspect connected agent authority and govern protected actions.",
  ],
];

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...await walk(path));
    else if (entry.name.endsWith(".js") || entry.name.endsWith(".html")) out.push(path);
  }
  return out;
}

let changes = 0;
for (const file of await walk("dist")) {
  let text = await readFile(file, "utf8");
  const before = text;
  for (const [from, to] of replacements) {
    const n = text.split(from).length - 1;
    if (n) {
      text = text.split(from).join(to);
      changes += n;
    }
  }
  if (text !== before) await writeFile(file, text);
}

if (changes < 4) throw new Error(`Expected recovered app claim patches were not found; applied only ${changes}`);
console.log(`Applied ${changes} app-route claim corrections.`);
