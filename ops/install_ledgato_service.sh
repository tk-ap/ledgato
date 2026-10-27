#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  systemctl --user disable --now ledgato-agentos     # as the owner, first
  sudo ./ops/install_ledgato_service.sh --owner <user>

Moves the Ledgato gateway out of the owner account, which every agent on this
host runs as, into a `ledgato` system user:
  - state (ledger, signing keys, approvals, grants) -> /var/lib/ledgato/state, 0700 ledgato
  - server secrets (principals, API key, GitHub, host-op, x402) -> /etc/ledgato/gateway.env, 0640 root:ledgato
  - approver credentials are removed from the owner's env file (they belong to Milchik)
  - passwordless host-op sudo moves from the owner to `ledgato`
  - the gateway runs as ledgato.service on the same 127.0.0.1:8000

The owner's env file keeps only client settings (agent URL, agent token).
Values are never printed. The originals are kept root-only under
/var/lib/ledgato/migrated-<time>/ until you delete them.
USAGE
}

OWNER=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --owner) [[ $# -ge 2 ]] || { usage >&2; exit 64; }; OWNER="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 64 ;;
  esac
done

[[ "${EUID}" -eq 0 ]] || { echo "installer must run as root" >&2; exit 1; }
[[ -n "${OWNER}" ]] && id "${OWNER}" >/dev/null 2>&1 || { echo "--owner must name the owner account" >&2; exit 64; }
OWNER_HOME="$(getent passwd "${OWNER}" | cut -d: -f6)"
OLD_STATE="${OWNER_HOME}/.local/state/ledgato-agentos"
OLD_ENV="${OWNER_HOME}/.config/agent-os/ledgato.env"
STATE="/var/lib/ledgato/state"
GATEWAY_ENV="/etc/ledgato/gateway.env"
VENV="/opt/ledgato/venv"
UNIT="/etc/systemd/system/ledgato.service"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE="/var/lib/ledgato/migrated-${STAMP}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(git -C "${SCRIPT_DIR}/.." rev-parse --show-toplevel)"
# Same trust rule as install_ledgato_host_op.sh: never install from a mutable checkout.
[[ "$(stat -c '%u' "${REPO_ROOT}")" -eq 0 ]] || { echo "install source must be root-owned: ${REPO_ROOT}" >&2; exit 1; }
[[ -z "$(git -C "${REPO_ROOT}" status --porcelain)" ]] || { echo "install source must be clean" >&2; exit 1; }

if ss -ltnH 'sport = :8000' | grep -q .; then
  echo "something is still listening on 127.0.0.1:8000." >&2
  echo "as ${OWNER}, run: systemctl --user disable --now ledgato-agentos   then re-run this." >&2
  exit 1
fi
[[ -f "${OLD_ENV}" ]] || { echo "missing ${OLD_ENV}" >&2; exit 1; }

# 1. The account.
if ! id ledgato >/dev/null 2>&1; then
  useradd --system --user-group --home-dir "${STATE}" --no-create-home --shell /usr/sbin/nologin ledgato
fi
[[ "$(id -u ledgato)" -ne 0 ]] || { echo "refusing: ledgato is uid 0" >&2; exit 1; }

# 2. Code it runs: root-owned, so the gateway's own account can't change it either.
if [[ ! -x "${VENV}/bin/python" ]]; then
  install -d -o root -g root -m 0755 /opt/ledgato
  python3 -m venv "${VENV}"
fi
"${VENV}/bin/python" -m pip install --quiet --disable-pip-version-check \
  -r "${REPO_ROOT}/engine/requirements.txt"
chown -R root:root /opt/ledgato
chmod -R go-w /opt/ledgato

# 3. State, copied and verified before the owner's copy is archived away.
install -d -o root -g root -m 0700 "${ARCHIVE}"
install -d -o ledgato -g ledgato -m 0700 "${STATE}"
if [[ -z "$(ls -A "${STATE}")" && -d "${OLD_STATE}" ]]; then
  for item in agentos-workspace-ledger.jsonl agentos-workspace-keys approvals.json authority.json idempotency.json; do
    [[ -e "${OLD_STATE}/${item}" ]] && cp -a "${OLD_STATE}/${item}" "${STATE}/"
  done
  chown -R ledgato:ledgato "${STATE}"
  chmod -R go-rwx "${STATE}"
  for item in agentos-workspace-ledger.jsonl approvals.json authority.json; do
    if [[ -e "${OLD_STATE}/${item}" ]]; then
      cmp -s "${OLD_STATE}/${item}" "${STATE}/${item}" || { echo "copy of ${item} does not match; nothing archived" >&2; exit 1; }
    fi
  done
  diff -r "${OLD_STATE}/agentos-workspace-keys" "${STATE}/agentos-workspace-keys" >/dev/null \
    || { echo "copy of the signing keys does not match; nothing archived" >&2; exit 1; }
  tar -C "$(dirname "${OLD_STATE}")" -cf "${ARCHIVE}/owner-state.tar" "$(basename "${OLD_STATE}")"
  chmod 0600 "${ARCHIVE}/owner-state.tar"
  rm -rf -- "${OLD_STATE}"
  echo "moved gateway state to ${STATE}; owner copy archived root-only"
else
  echo "state already present in ${STATE}; left as is"
fi

# 4. Secrets: split by name only; values never printed.
SERVER_RE='^(export[[:space:]]+)?(LEDGATO_PRINCIPALS|LEDGATO_API_KEY|LEDGATO_GITHUB_[A-Z0-9_]+|LEDGATO_HOST_OP_[A-Z0-9_]+|LEDGATO_X402_[A-Z0-9_]+)='
APPROVER_RE='^(export[[:space:]]+)?(AGENT_OS_LEDGATO_APPROVER_[A-Z0-9_]+|LEDGATO_APPROVER_[A-Z0-9_]+)='
install -o root -g root -m 0600 "${OLD_ENV}" "${ARCHIVE}/owner-ledgato.env"
install -d -o root -g ledgato -m 0750 /etc/ledgato
if [[ ! -s "${GATEWAY_ENV}" ]]; then
  umask 077
  grep -E "${SERVER_RE}" "${ARCHIVE}/owner-ledgato.env" > "${GATEWAY_ENV}" || true
  chown root:ledgato "${GATEWAY_ENV}"
  chmod 0640 "${GATEWAY_ENV}"
fi
grep -Eq '^(export[[:space:]]+)?LEDGATO_PRINCIPALS=' "${GATEWAY_ENV}" \
  || { echo "no LEDGATO_PRINCIPALS found for the gateway; owner env left unchanged" >&2; exit 1; }
CLIENT="$(mktemp)"
grep -vE "${SERVER_RE}|${APPROVER_RE}" "${ARCHIVE}/owner-ledgato.env" > "${CLIENT}" || true
install -o "${OWNER}" -g "$(id -gn "${OWNER}")" -m 0600 "${CLIENT}" "${OLD_ENV}"
rm -f "${CLIENT}"
echo "gateway secrets: $(grep -cE "${SERVER_RE}" "${GATEWAY_ENV}") line(s) in ${GATEWAY_ENV}:"
grep -oE '^(export[[:space:]]+)?[A-Z0-9_]+' "${GATEWAY_ENV}" | sed 's/^export[[:space:]]*//; s/^/  /'
removed="$(grep -cE "${APPROVER_RE}" "${ARCHIVE}/owner-ledgato.env" || true)"
echo "approver credentials removed from the owner's env file: ${removed}"

# 5. Passwordless host-op sudo: the gateway's account, not the owner's.
"${REPO_ROOT}/ops/install_ledgato_host_op.sh" --service-user ledgato

# 6. The service.
install -o root -g root -m 0644 "${REPO_ROOT}/ops/systemd/ledgato.service" "${UNIT}"
systemctl daemon-reload
systemctl enable --now ledgato.service
for _ in $(seq 1 30); do
  curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS http://127.0.0.1:8000/health >/dev/null || { echo "ledgato.service did not become healthy; see journalctl -u ledgato" >&2; exit 1; }

# 7. Prove the owner account (and so every agent) is outside it now.
failed=0
sudo -u "${OWNER}" test -r "${GATEWAY_ENV}" && { echo "FAIL: ${OWNER} can read ${GATEWAY_ENV}"; failed=1; }
sudo -u "${OWNER}" test -r "${STATE}/agentos-workspace-ledger.jsonl" && { echo "FAIL: ${OWNER} can read the ledger"; failed=1; }
sudo -l -U "${OWNER}" 2>/dev/null | grep -q ledgato-host-op && { echo "FAIL: ${OWNER} still has host-op sudo"; failed=1; }
[[ "${failed}" -eq 0 ]] || exit 1

echo
echo "ledgato.service is running as ledgato on 127.0.0.1:8000."
echo "${OWNER} can no longer read its secrets, ledger or keys, or run host-op without it."
echo
echo "Next, because these secrets were readable by every agent until now: rotate them."
echo "  - the principals' tokens in ${GATEWAY_ENV} (and the matching client/Milchik settings)"
echo "  - LEDGATO_GITHUB_TOKEN: replace with a fine-grained token for the one repository"
echo "Originals: ${ARCHIVE} (root-only). Delete it once the rotation is done."
