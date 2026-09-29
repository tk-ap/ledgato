#!/usr/bin/env bash
set -euo pipefail

SOURCE_WORKTREE="${AGENT_OS_SOURCE_WORKTREE:-/home/tk/Work/agent-os}"
UPSTREAM="https://github.com/tk-ap/agent-os.git"
TARGET="/var/lib/ledgato/agent-os-main.bundle"

fail() {
  echo "stage_agentos_source: $*" >&2
  exit 1
}

if [[ "${EUID}" -eq 0 ]]; then
  fail "run as the owner account, not root; the fetch must use the owner's existing GitHub authentication"
fi

[[ -d "${SOURCE_WORKTREE}/.git" || -f "${SOURCE_WORKTREE}/.git" ]] || fail "source worktree is not a git checkout: ${SOURCE_WORKTREE}"
[[ "$(git -C "${SOURCE_WORKTREE}" remote get-url origin)" == "${UPSTREAM}" ]] || fail "source worktree has unexpected origin"

# Fetch only the canonical branch. This may use the owner's existing GitHub
# credential helper; no credential is copied into the staged artifact.
git -C "${SOURCE_WORKTREE}" fetch --prune origin main
sha="$(git -C "${SOURCE_WORKTREE}" rev-parse refs/remotes/origin/main)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT
bare="${tmpdir}/repo.git"
bundle="${tmpdir}/agent-os-main.bundle"

git init --bare "${bare}" >/dev/null
git --git-dir="${bare}" fetch "${SOURCE_WORKTREE}" refs/remotes/origin/main >/dev/null
git --git-dir="${bare}" update-ref refs/heads/main FETCH_HEAD
git --git-dir="${bare}" bundle create "${bundle}" refs/heads/main

listed="$(git bundle list-heads "${bundle}" refs/heads/main)"
[[ "${listed}" == "${sha} refs/heads/main" ]] || fail "bundle main does not match fetched origin/main"

sudo install -d -o root -g root -m 0755 /var/lib/ledgato
sudo install -o root -g root -m 0644 "${bundle}" "${TARGET}"

echo "staged AgentOS canonical main bundle"
echo "sha=${sha}"
echo "target=${TARGET}"
