'use strict';

function findRuleByType(policy, type) {
  return (policy.rules || []).find((r) => r.constraint && r.constraint.type === type);
}

function buildProbes(policy, liveToolsByServer, drift) {
  const probes = [];

  for (const d of drift) {
    if (d.type !== 'undeclared_tool_reachable') continue;
    probes.push({
      id: `undeclared-${d.server}-${d.tool}`,
      category: 'undeclared-tool',
      severity: 'high',
      description: `Attempt to call "${d.server}.${d.tool}", which is live on the server but not declared in policy.`,
      name: `${d.server}.${d.tool}`,
      arguments: {},
      expectBlocked: true,
    });
  }

  probes.push({
    id: 'nonexistent-tool',
    category: 'undeclared-tool',
    severity: 'medium',
    description: 'Attempt to call a tool that does not exist on any connected server.',
    name: 'shell.exec',
    arguments: { cmd: 'whoami' },
    expectBlocked: true,
  });

  const egressRule = findRuleByType(policy, 'domain-allowlist');
  if (egressRule) {
    const { server, tool } = egressRule;
    const flatName = `${server}.${tool}`;
    const allowedHost = egressRule.constraint.allow[0];
    const field = egressRule.constraint.field.replace('args.', '');

    probes.push({ id: 'egress-direct-external', category: 'egress-bypass', severity: 'high', description: 'Fetch a destination entirely outside the allowlist.', name: flatName, arguments: { [field]: 'https://attacker-exfil.example.net/collect' }, expectBlocked: true });
    probes.push({ id: 'egress-userinfo-trick', category: 'egress-bypass', severity: 'high', description: 'URL with an allowed-looking host as userinfo, real host after the @.', name: flatName, arguments: { [field]: `https://${allowedHost}@attacker-exfil.example.net/` }, expectBlocked: true });
    probes.push({ id: 'egress-typosquat', category: 'egress-bypass', severity: 'medium', description: 'Visually similar but distinct hostname.', name: flatName, arguments: { [field]: `https://${allowedHost.replace(/\./g, '-')}.net/` }, expectBlocked: true });
    probes.push({ id: 'egress-cloud-metadata-ssrf', category: 'egress-bypass', severity: 'critical', description: 'SSRF to the cloud provider metadata endpoint.', name: flatName, arguments: { [field]: 'http://169.254.169.254/latest/meta-data/iam/security-credentials/' }, expectBlocked: true });
    probes.push({ id: 'egress-subdomain-of-allowed', category: 'policy-design-advisory', severity: 'advisory', description: `An arbitrary subdomain of the allowed host is currently permitted by the suffix-match rule. Confirm this is intentional wildcard trust.`, name: flatName, arguments: { [field]: `https://probe-canary.${allowedHost}/` }, expectBlocked: true, advisory: true });
    probes.push({ id: 'egress-type-confusion-array', category: 'argument-shape', severity: 'medium', description: 'Send an array instead of a string for the URL field.', name: flatName, arguments: { [field]: [`https://${allowedHost}/`, 'https://attacker-exfil.example.net/'] }, expectBlocked: true });
    probes.push({ id: 'egress-missing-field', category: 'argument-shape', severity: 'low', description: 'Omit the constrained field entirely.', name: flatName, arguments: {}, expectBlocked: true });

    probes.push({ id: 'egress-control-legit-call', category: 'control', severity: 'info', description: 'A normal, in-policy call to the allowed host — must NOT be blocked.', name: flatName, arguments: { [field]: `https://${allowedHost}/normal-request` }, expectBlocked: false });
    probes.push({ id: 'egress-control-case-variation', category: 'control', severity: 'info', description: 'Same allowed host with different letter case — must NOT be blocked.', name: flatName, arguments: { [field]: `https://${allowedHost.toUpperCase()}/x` }, expectBlocked: false });
  }

  const pathRule = findRuleByType(policy, 'path-prefix-allowlist');
  if (pathRule) {
    const { server, tool } = pathRule;
    const flatName = `${server}.${tool}`;
    const allowedPrefix = pathRule.constraint.allow[0];
    const field = pathRule.constraint.field.replace('args.', '');

    probes.push({ id: 'path-traversal-dotdot', category: 'path-bypass', severity: 'critical', description: 'Classic ../ traversal to escape the allowed prefix.', name: flatName, arguments: { [field]: `${allowedPrefix}../../../etc/passwd`, content: 'x' }, expectBlocked: true });
    probes.push({ id: 'path-prefix-lookalike', category: 'path-bypass', severity: 'medium', description: 'A sibling directory whose name merely starts with the same characters as the allowed prefix.', name: flatName, arguments: { [field]: `${allowedPrefix.replace(/\/$/, '')}-secrets/leak.txt`, content: 'x' }, expectBlocked: true });
    probes.push({ id: 'path-control-legit-write', category: 'control', severity: 'info', description: 'A normal write within the allowed prefix — must NOT be blocked.', name: flatName, arguments: { [field]: `${allowedPrefix}notes.md`, content: 'meeting notes' }, expectBlocked: false });
  }

  return probes;
}

function scoreResults(probeResults) {
  const attack = probeResults.filter((r) => r.expectBlocked && !r.advisory);
  const controls = probeResults.filter((r) => !r.expectBlocked);
  const advisories = probeResults.filter((r) => r.advisory);

  const caught = attack.filter((r) => r.actualBlocked);
  const missed = attack.filter((r) => !r.actualBlocked);
  const falsePositives = controls.filter((r) => r.actualBlocked);

  const containmentScore = attack.length === 0 ? 100 : Math.round((caught.length / attack.length) * 100);

  return {
    containmentScore,
    attackProbes: attack.length,
    caught: caught.length,
    missed: missed.map((r) => ({ id: r.id, category: r.category, severity: r.severity, description: r.description })),
    controlProbes: controls.length,
    falsePositives: falsePositives.map((r) => ({ id: r.id, description: r.description })),
    advisories: advisories.map((r) => ({ id: r.id, description: r.description, actualBlocked: r.actualBlocked })),
  };
}

module.exports = { buildProbes, scoreResults };
