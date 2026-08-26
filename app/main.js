const form = document.querySelector("#run-form");
const empty = document.querySelector("#empty");
const output = document.querySelector("#output");
const error = document.querySelector("#error");
const button = form.querySelector("button");

const setText = (id, value) => {
  document.querySelector(`#${id}`).textContent = value;
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  button.disabled = true;
  button.textContent = "Verifying boundary…";
  error.hidden = true;
  const values = Object.fromEntries(new FormData(form));

  try {
    const response = await fetch("/api/v1/demo/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        agent: values.agent,
        release: values.release,
        attempt: { tool: values.tool, domain: values.domain, impact: values.impact },
      }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);

    const blocked = !body.decision.allow;
    setText("verdict", blocked ? "ACTION BLOCKED" : "ACTION ALLOWED");
    setText("reason", body.decision.reason);
    setText("probes", `${body.probes.passed}/${body.probes.total} passed`);
    setText("gate", body.gate.verdict);
    setText("ledger", body.ledger.verified ? `${body.ledger.entries} entries · verified` : "verification failed");
    setText("evidence-id", body.decision_evidence.id);
    setText("hash", body.decision_evidence.hash.slice(0, 24) + "…");
    setText("raw", JSON.stringify(body, null, 2));
    document.querySelector("#verdict-dot").className = blocked ? "blocked" : "allowed";
    empty.hidden = true;
    output.hidden = false;
  } catch (cause) {
    output.hidden = true;
    empty.hidden = true;
    error.textContent = `The live engine did not respond: ${cause.message}`;
    error.hidden = false;
  } finally {
    button.disabled = false;
    button.innerHTML = "Run containment check <span>→</span>";
  }
});
