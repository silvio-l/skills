#!/bin/bash
# lan-computer-use: ensure the agent runs in the GUI session of the SSH user on a remote Mac (experimental).
# Called by cu.py over SSH; prints "STATE <json>" on success.
#   setup-<build>.sh <build> [idle-minutes] [version]
# The binary needs its own Accessibility + Screen Recording grants on that Mac (System Settings > Privacy).
set -u
h="${1:?build hash}"
idle="${2:-3}"
[ "$idle" -gt 5 ] 2>/dev/null && idle=5
ver="${3:-0}"
dir="$(cd "$(dirname "$0")" && pwd)"
state="$dir/state.json"
label="lan-computer-use.agent"
uid="$(id -u)"

alive() {
  [ -f "$state" ] || return 1
  pid="$(/usr/bin/plutil -extract pid raw -o - "$state" 2>/dev/null)" || return 1
  build="$(/usr/bin/plutil -extract build raw -o - "$state" 2>/dev/null)" || return 1
  kill -0 "$pid" 2>/dev/null && [ "$build" = "$h" ]
}

if alive; then echo "STATE $(tr -d '\n' < "$state")"; exit 0; fi

# never replace a newer agent with the one of an outdated skill copy (another machine or session)
if [ -f "$state" ]; then
  opid="$(/usr/bin/plutil -extract pid raw -o - "$state" 2>/dev/null)"
  over="$(/usr/bin/plutil -extract version raw -o - "$state" 2>/dev/null)"
  if [ -n "$opid" ] && kill -0 "$opid" 2>/dev/null && [ "${over:-0}" -gt "$ver" ] 2>/dev/null; then
    echo "OUTDATED: agent version $over runs here, this skill copy brings $ver"; exit 6
  fi
fi

if ! /bin/launchctl print "gui/$uid" >/dev/null 2>&1; then
  echo "NO-GUI: $USER has no GUI session on this Mac (log in at the screen first)"; exit 4
fi

bin="$dir/lcu-agent-$h"
if [ ! -x "$bin" ]; then
  find "$dir" -maxdepth 1 \( -name 'lcu-agent-*' -o -name 'agent-*.swift' -o -name 'setup-*.sh' \) \
    ! -name "*-$h*" -delete 2>/dev/null
  if ! out="$(/usr/bin/swiftc -O -swift-version 5 -o "$bin.tmp" "$dir/agent-$h.swift" 2>&1)"; then
    echo "COMPILE-ERROR"; echo "$out" | grep -i error | head -15; exit 3
  fi
  mv "$bin.tmp" "$bin"
fi

/bin/launchctl bootout "gui/$uid/$label" >/dev/null 2>&1
rm -f "$state"
plist="$dir/$label.plist"
cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key><array>
    <string>$bin</string><string>--idle</string><string>$idle</string>
    <string>--build</string><string>$h</string><string>--dir</string><string>$dir</string>
  </array>
  <key>LimitLoadToSessionType</key><string>Aqua</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><false/>
</dict></plist>
EOF
if ! /bin/launchctl bootstrap "gui/$uid" "$plist" 2>/dev/null; then
  /bin/launchctl kickstart -k "gui/$uid/$label" >/dev/null 2>&1
fi

for _ in $(seq 1 100); do
  if alive; then echo "STATE $(tr -d '\n' < "$state")"; exit 0; fi
  sleep 0.1
done
echo "START-TIMEOUT: agent did not report within 10 s"; exit 5
