#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  sudo ./ops/install_ledgato_host_op.sh --service-user <user>

Installs the fixed Ledgato host helper as root and grants only that service
account passwordless sudo for the two exact helper operations:
  - agentos-runtime-status
  - agentos-runtime-activate

The helper itself remains root-owned and non-writable by the service account.
EOF
}

SERVICE_USER=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --service-user)
      [[ $# -ge 2 ]] || { usage >&2; exit 64; }
      SERVICE_USER="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 64
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "installer must run as root" >&2
  exit 1
fi

if [[ -z "${SERVICE_USER}" || ! "${SERVICE_USER}" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]]; then
  echo "--service-user must name an existing local service account" >&2
  exit 64
fi
if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
  echo "service user does not exist: ${SERVICE_USER}" >&2
  exit 1
fi
if [[ "$(id -u "${SERVICE_USER}")" -eq 0 ]]; then
  echo "refusing to grant helper access to root itself" >&2
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(git -C "${SCRIPT_DIR}/.." rev-parse --show-toplevel)"
SOURCE="${SCRIPT_DIR}/ledgato_host_op.py"
TARGET="/usr/local/libexec/ledgato-host-op"
SUDOERS="/etc/sudoers.d/ledgato-host-op"
CANONICAL_REMOTE="https://github.com/tk-ap/ledgato.git"

# A root install must not execute helper code out of a mutable user/agent
# checkout. The bootstrap checkout is itself part of the privileged TCB.
if [[ "$(stat -c '%u' "${REPO_ROOT}")" -ne 0 ]]; then
  echo "Ledgato install source must be root-owned: ${REPO_ROOT}" >&2
  exit 1
fi
if [[ "$(git -C "${REPO_ROOT}" remote get-url origin)" != "${CANONICAL_REMOTE}" ]]; then
  echo "Ledgato install source has unexpected origin" >&2
  exit 1
fi
if [[ "$(git -C "${REPO_ROOT}" branch --show-current)" != "main" ]]; then
  echo "Ledgato install source must be on main" >&2
  exit 1
fi
if [[ -n "$(git -C "${REPO_ROOT}" status --porcelain)" ]]; then
  echo "Ledgato install source must be clean" >&2
  exit 1
fi
git -C "${REPO_ROOT}" fetch --prune origin main
if ! git -C "${REPO_ROOT}" merge-base --is-ancestor HEAD origin/main; then
  echo "Ledgato install source is not a fast-forward ancestor of origin/main" >&2
  exit 1
fi
git -C "${REPO_ROOT}" merge --ff-only origin/main >/dev/null
if [[ "$(git -C "${REPO_ROOT}" rev-parse HEAD)" != "$(git -C "${REPO_ROOT}" rev-parse origin/main)" ]]; then
  echo "Ledgato install source did not converge to canonical main" >&2
  exit 1
fi

if [[ ! -f "${SOURCE}" || -L "${SOURCE}" ]]; then
  echo "missing regular helper source: ${SOURCE}" >&2
  exit 1
fi

install -d -o root -g root -m 0755 /usr/local/libexec
install -o root -g root -m 0755 "${SOURCE}" "${TARGET}"
install -d -o root -g root -m 0755 /var/lib/ledgato

TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT
cat >"${TMP}" <<EOF
# Installed by Ledgato. Keep commands exact; do not add wildcards.
${SERVICE_USER} ALL=(root) NOPASSWD: ${TARGET} agentos-runtime-status
${SERVICE_USER} ALL=(root) NOPASSWD: ${TARGET} agentos-runtime-activate
EOF
chmod 0440 "${TMP}"
visudo -cf "${TMP}" >/dev/null
install -o root -g root -m 0440 "${TMP}" "${SUDOERS}"
visudo -cf "${SUDOERS}" >/dev/null

# The status operation is non-mutating and proves the sudo boundary is usable.
sudo -u "${SERVICE_USER}" sudo -n "${TARGET}" agentos-runtime-status >/dev/null || {
  echo "helper installed, but the service account cannot invoke the exact status operation" >&2
  exit 1
}

echo "installed ${TARGET}"
echo "installed ${SUDOERS}"
echo "service user: ${SERVICE_USER}"
echo "No host mutation has been executed; activation remains Ledgato approval-gated."
