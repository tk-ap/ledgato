#!/bin/sh
# Synthetic isolation probe. Looks ONLY for a fake sentinel this test created.
# Touches no real credential store.
S="FAKE-ghp-DUMMY-NEVER-REAL"
SECRET_DIR="$1"          # host path of the simulated gateway secret

env | grep -q "$S" && echo "env-vars|LEAKED" || echo "env-vars|blocked"

if head -c 200 "$SECRET_DIR/github_token" 2>/dev/null | grep -q "$S"; then
  echo "secret-file-by-path|LEAKED"
else
  echo "secret-file-by-path|blocked"
fi

[ -d "$SECRET_DIR" ] && echo "secret-dir-visible|LEAKED" || echo "secret-dir-visible|blocked"

leak=0
for p in /proc/[0-9]*; do
  grep -qa "$S" "$p/environ" 2>/dev/null && leak=1
done
[ "$leak" = 1 ] && echo "proc-environ|LEAKED" || echo "proc-environ|blocked"

echo "visible-pids|$(ls -d /proc/[0-9]* 2>/dev/null | wc -l)"
