import { readFile, writeFile } from "node:fs/promises";

const file = "dist/index.html";
let html = await readFile(file, "utf8");

const replacements = [
  [
    "If an agent shouldn&#x27;t be able to do it, Ledgato stops it.",
    "When a protected action is routed through Ledgato, DENY means the downstream action does not execute.",
  ],
  [
    "Interpose ALLOW / DENY / APPROVE at runtime. If an agent shouldn&#x27;t, Ledgato stops it.",
    "Interpose ALLOW / DENY / APPROVE before a protected downstream action is invoked.",
  ],
  [
    "No. The tamper-evident ledger is infrastructure, not the product. Ledgato is an authorization control plane — who can reach what, and who gets stopped when they shouldn&#x27;t.",
    "No. The tamper-evident ledger is infrastructure, not the product. Ledgato is an independent authorization and enforcement layer for consequential agent actions.",
  ],
  [
    "Tell us what your agents can reach today. We&#x27;ll map it, attack it, and show you exactly where it breaks.",
    "Tell us which agent workflow and consequential action you want to place behind a boundary. We'll map the route, test bypasses, and define what is actually enforced.",
  ],
];

for (const [from, to] of replacements) html = html.split(from).join(to);

// The immutable source deployment carries its own Vercel-toolbar injection.
// A new preview/production deployment receives its own toolbar behavior from Vercel;
// retaining the source deployment's injection would duplicate deployment tooling.
html = html.replace(/<script[^>]*data-deployment-id="dpl_C5wMNA4Xq8pV7jxYmCLeT5sAojbL"[^>]*><\/script>/g, "");

const forbidden = [
  "If an agent shouldn&#x27;t be able to do it, Ledgato stops it.",
  "If it can reach your stack, Ledgato can see it.",
  "Anything that escapes, drifts, or exfiltrates is caught and blocked before release.",
];
for (const phrase of forbidden) {
  if (html.includes(phrase)) throw new Error(`Unbounded SSR claim remains: ${phrase}`);
}

await writeFile(file, html);
