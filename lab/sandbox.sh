#!/bin/sh
# Vetted agent-sandbox launcher for the enforcement stress test.
#
# Usage: lab/sandbox.sh <agent-work-dir> <command> [args...]
#
# CRITICAL — read before changing:
#
# The Ledgato-held provider credential must NOT be present in the environment
# of the process that runs this script. `bwrap --clearenv` clears the
# environment of the sandboxed child, but bwrap's own supervisor becomes PID 1
# *inside* the sandbox's PID namespace and retains the launching environment.
# /proc/1/environ is then readable by the confined agent.
#
# This was found by lab/probe.sh, not assumed:
#
#     LEDGATO_GITHUB_TOKEN=<secret> bwrap --clearenv ... -> proc-environ|LEAKED
#     env -u LEDGATO_GITHUB_TOKEN   bwrap --clearenv ... -> proc-environ|blocked
#
# So the gateway holds the credential in a separate process that is not an
# ancestor of the sandbox. The agent reaches the gateway over the network only.
#
# Known limitations of this sandbox (document them, do not paper over them):
#   * same-UID rootless namespaces, not a microVM — weaker than the directive's
#     preferred isolation;
#   * --share-net means the agent shares the host network namespace, so it can
#     reach localhost services. That is required for it to call the gateway,
#     and it means network-level isolation is NOT provided here.
set -eu

WORK="${1:?usage: sandbox.sh <agent-work-dir> <command> [args...]}"
shift

for leak in LEDGATO_GITHUB_TOKEN GITHUB_TOKEN GH_TOKEN LEDGATO_API_KEY LEDGATO_PRINCIPALS; do
    if [ -n "$(eval "printf '%s' \"\${$leak:-}\"")" ]; then
        echo "refusing to launch: $leak is set in the launching environment;" >&2
        echo "it would be readable from /proc/1/environ inside the sandbox." >&2
        exit 1
    fi
done

exec bwrap \
    --unshare-all --share-net --unshare-pid --die-with-parent --new-session \
    --clearenv --setenv PATH /usr/bin:/bin --setenv HOME /home/agent \
    --ro-bind /usr /usr --ro-bind /etc /etc \
    --symlink usr/lib /lib --symlink usr/lib64 /lib64 \
    --symlink usr/bin /bin --symlink usr/sbin /sbin \
    --proc /proc --dev /dev --tmpfs /tmp --tmpfs /home --dir /home/agent \
    --bind "$WORK" /home/agent/work \
    "$@"
