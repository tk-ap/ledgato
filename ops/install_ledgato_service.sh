#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  systemctl --user disable --now ledgato-agentos     # as the owner, first
  sudo /var/lib/ledgato/source/ops/install_ledgato_service.sh --owner <user>

Moves the Ledgato gateway out of the owner account, which every agent on this
host runs as, into a `ledgato` system user:
  - state (ledger, signing keys, approvals, grants) -> /var/lib/ledgato/state, 0700 ledgato
  - server secrets (principals, API key, GitHub, host-op, x402) -> /etc/ledgato/gateway.env, 0640 root:ledgato
  - approver credentials are removed from the owner's env file (they belong to Milchik)
  - passwordless host-op sudo moves from the owner to `ledgato`
  - the gateway runs as ledgato.service on the same 127.0.0.1:8000

Order matters. Nothing the owner's old service needs (its env file, its
state, its host-op sudo) is changed until ledgato.service is running and
healthy. If it doesn't come up, the installer stops it and says how to go
back: `systemctl --user enable --now ledgato-agentos`. Safe to re-run.
Values are never printed; originals are kept root-only under
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
SOURCE="/var/lib/ledgato/source"
STATE="/var/lib/ledgato/state"
GATEWAY_ENV="/etc/ledgato/gateway.env"
VENV="/opt/ledgato/venv"
UNIT="/etc/systemd/system/ledgato.service"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE="/var/lib/ledgato/migrated-${STAMP}"
STATE_ITEMS=(agentos-workspace-ledger.jsonl agentos-workspace-keys approvals.json authority.json idempotency.json)
SERVER_RE='^(export[[:space:]]+)?(LEDGATO_PRINCIPALS|LEDGATO_API_KEY|LEDGATO_GITHUB_[A-Z0-9_]+|LEDGATO_HOST_OP_[A-Z0-9_]+|LEDGATO_X402_[A-Z0-9_]+)='
APPROVER_RE='^(export[[:space:]]+)?(AGENT_OS_LEDGATO_APPROVER_[A-Z0-9_]+|LEDGATO_APPROVER_[A-Z0-9_]+)='

# 0. The code ledgato.service runs is $SOURCE/engine: verify that tree, not
#    just wherever this script happens to sit.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
[[ "$(git -C "${SCRIPT_DIR}/.." rev-parse --show-toplevel)" == "${SOURCE}" ]] \
  || { echo "run this from ${SOURCE}/ops, the checkout the service executes" >&2; exit 1; }
[[ "$(stat -c '%u' "${SOURCE}")" -eq 0 ]] || { echo "${SOURCE} must be root-owned" >&2; exit 1; }
[[ "$(git -C "${SOURCE}" remote get-url origin)" == "https://github.com/tk-ap/ledgato.git" ]] \
  || { echo "${SOURCE} has an unexpected origin" >&2; exit 1; }
[[ "$(git -C "${SOURCE}" branch --show-current)" == "main" ]] || { echo "${SOURCE} must be on main" >&2; exit 1; }
[[ -z "$(git -C "${SOURCE}" status --porcelain)" ]] || { echo "${SOURCE} must be clean" >&2; exit 1; }
git -C "${SOURCE}" fetch --quiet --prune origin main
[[ "$(git -C "${SOURCE}" rev-parse HEAD)" == "$(git -C "${SOURCE}" rev-parse origin/main)" ]] \
  || { echo "${SOURCE} is not at origin/main; pull --ff-only first" >&2; exit 1; }
writable="$(find "${SOURCE}" -path "${SOURCE}/.git" -prune -o \( ! -user root -o -perm /022 \) -print -quit)"
[[ -z "${writable}" ]] || { echo "not root-only-writable: ${writable}" >&2; exit 1; }
echo "code: ${SOURCE} at $(git -C "${SOURCE}" rev-parse --short HEAD), root-owned, clean, origin/main"

if ss -ltnH 'sport = :8000' | grep -q .; then
  echo "something is still listening on 127.0.0.1:8000." >&2
  echo "as ${OWNER}, run: systemctl --user disable --now ledgato-agentos   then re-run this." >&2
  exit 1
fi

# 1. The account and a root-owned venv.
if ! id ledgato >/dev/null 2>&1; then
  useradd --system --user-group --home-dir "${STATE}" --no-create-home --shell /usr/sbin/nologin ledgato
fi
[[ "$(id -u ledgato)" -ne 0 ]] || { echo "refusing: ledgato is uid 0" >&2; exit 1; }
if [[ ! -x "${VENV}/bin/python" ]]; then
  install -d -o root -g root -m 0755 /opt/ledgato
  python3 -m venv "${VENV}"
fi
"${VENV}/bin/python" -m pip install --quiet --disable-pip-version-check -r "${SOURCE}/engine/requirements.txt"
chown -R root:root /opt/ledgato
chmod -R go-w /opt/ledgato
install -d -o root -g root -m 0700 "${ARCHIVE}"

same_state() {  # same_state A B: every state item identical in both
  local item
  for item in "${STATE_ITEMS[@]}"; do
    if [[ -e "$1/${item}" || -e "$2/${item}" ]]; then
      diff -r "$1/${item}" "$2/${item}" >/dev/null 2>&1 || return 1
    fi
  done
}

# 2. State: copy into a fresh staging dir, verify every item, then rename into
#    place. The owner's copy is untouched until step 5. A re-run never trusts a
#    partial earlier copy.
if [[ -d "${OLD_STATE}" ]]; then
  STAGE="$(mktemp -d /var/lib/ledgato/state.staging.XXXXXX)"
  for item in "${STATE_ITEMS[@]}"; do
    [[ -e "${OLD_STATE}/${item}" ]] && cp -a "${OLD_STATE}/${item}" "${STAGE}/"
  done
  same_state "${OLD_STATE}" "${STAGE}" || { rm -rf -- "${STAGE}"; echo "state copy does not match; nothing changed" >&2; exit 1; }
  if [[ -d "${STATE}" && -n "$(ls -A "${STATE}")" ]]; then
    same_state "${OLD_STATE}" "${STATE}" || { rm -rf -- "${STAGE}"; echo "${STATE} exists and differs from the owner's state; resolve by hand" >&2; exit 1; }
    rm -rf -- "${STAGE}"
  else
    rmdir "${STATE}" 2>/dev/null || true
    mv -T "${STAGE}" "${STATE}"
  fi
  chown -R ledgato:ledgato "${STATE}"
  chmod 0700 "${STATE}"
  chmod -R go-rwx "${STATE}"
  same_state "${OLD_STATE}" "${STATE}" || { echo "state in ${STATE} does not match after install" >&2; exit 1; }
elif [[ ! -d "${STATE}" ]]; then
  echo "no owner state at ${OLD_STATE} and none in ${STATE}" >&2; exit 1
fi
# Branch bundles from agents: anyone may drop a file, nobody may list or
# remove another's (sticky, no read for others); the gateway owns it.
install -d -o ledgato -g ledgato -m 1733 /var/lib/ledgato/inbox

# 3. Server secrets, by name, as plain KEY=value lines systemd reads; values
#    never printed. The owner's file is not changed yet.
install -d -o root -g ledgato -m 0750 /etc/ledgato
if [[ ! -s "${GATEWAY_ENV}" ]]; then
  [[ -f "${OLD_ENV}" ]] || { echo "missing ${OLD_ENV}" >&2; exit 1; }
  NEW_ENV="$(mktemp /etc/ledgato/.gateway.env.XXXXXX)"
  grep -E "${SERVER_RE}" "${OLD_ENV}" | sed -E 's/^export[[:space:]]+//' > "${NEW_ENV}" || true
  chown root:ledgato "${NEW_ENV}"
  chmod 0640 "${NEW_ENV}"
  mv -T "${NEW_ENV}" "${GATEWAY_ENV}"
fi
grep -Eq '^LEDGATO_PRINCIPALS=' "${GATEWAY_ENV}" \
  || { echo "no LEDGATO_PRINCIPALS for the gateway in ${GATEWAY_ENV}" >&2; exit 1; }
echo "gateway secrets in ${GATEWAY_ENV}:"
grep -oE '^[A-Z0-9_]+' "${GATEWAY_ENV}" | sed 's/^/  /'

# 4. Start it and prove it healthy before cutting anything over.
install -o root -g root -m 0644 "${SOURCE}/ops/systemd/ledgato.service" "${UNIT}"
systemctl daemon-reload
systemctl enable --now ledgato.service
healthy=0
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then healthy=1; break; fi
  sleep 1
done
if [[ "${healthy}" -ne 1 ]]; then
  systemctl disable --now ledgato.service || true
  echo "ledgato.service did not become healthy (journalctl -u ledgato)." >&2
  echo "Nothing of ${OWNER}'s was changed. To go back: as ${OWNER}, systemctl --user enable --now ledgato-agentos" >&2
  exit 1
fi
echo "ledgato.service is healthy as ledgato"

# 5. Cut over, now that the new gateway works.
"${SOURCE}/ops/install_ledgato_host_op.sh" --service-user ledgato
install -o root -g root -m 0600 "${OLD_ENV}" "${ARCHIVE}/owner-ledgato.env" 2>/dev/null || true
if [[ -f "${OLD_ENV}" ]]; then
  CLIENT="$(mktemp)"
  grep -vE "${SERVER_RE}|${APPROVER_RE}" "${OLD_ENV}" > "${CLIENT}" || true
  install -o "${OWNER}" -g "$(id -gn "${OWNER}")" -m 0600 "${CLIENT}" "${OLD_ENV}"
  rm -f "${CLIENT}"
fi
if [[ -d "${OLD_STATE}" ]]; then
  tar -C "$(dirname "${OLD_STATE}")" -cf "${ARCHIVE}/owner-state.tar" "$(basename "${OLD_STATE}")"
  chmod 0600 "${ARCHIVE}/owner-state.tar"
  rm -rf -- "${OLD_STATE}"
fi

# 6. Prove the owner account (and so every agent) is outside it now.
failed=0
sudo -u "${OWNER}" test -r "${GATEWAY_ENV}" && { echo "FAIL: ${OWNER} can read ${GATEWAY_ENV}"; failed=1; }
sudo -u "${OWNER}" test -r "${STATE}/agentos-workspace-ledger.jsonl" && { echo "FAIL: ${OWNER} can read the ledger"; failed=1; }
[[ -e "${OLD_STATE}" ]] && { echo "FAIL: ${OLD_STATE} still exists"; failed=1; }
grep -Eq "${SERVER_RE}|${APPROVER_RE}" "${OLD_ENV}" 2>/dev/null && { echo "FAIL: ${OLD_ENV} still holds gateway or approver secrets"; failed=1; }
sudo -l -U "${OWNER}" 2>/dev/null | grep -q ledgato-host-op && { echo "FAIL: ${OWNER} still has host-op sudo"; failed=1; }
[[ "${failed}" -eq 0 ]] || exit 1

echo
echo "ledgato.service runs as ledgato on 127.0.0.1:8000; ${OWNER} can no longer read its"
echo "secrets, ledger or keys, or run host-op without it."
echo
echo "Next, because these secrets were readable by every agent until now: rotate them."
echo "  - the principals' tokens in ${GATEWAY_ENV} (and the matching client/Milchik settings)"
echo "  - LEDGATO_GITHUB_TOKEN: replace with a fine-grained token for the one repository"
echo "Originals: ${ARCHIVE} (root-only). Delete it once the rotation is done."
