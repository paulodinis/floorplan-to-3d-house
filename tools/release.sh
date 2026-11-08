#!/usr/bin/env bash
# Bump the plugin version everywhere and build the installable package.
# usage: tools/release.sh 1.6.1   -> plugin.json, marketplace.json, every SKILL.md, README snippet; dist/floorplan-to-3d-house.plugin
set -euo pipefail
V="${1:?version, e.g. 1.6.1}"; R="$(cd "$(dirname "$0")/.." && pwd)"; P="$R/plugins/floorplan-to-3d-house"
python3 - "$V" "$R" <<'PY'
import json, re, sys, glob, os
v, r = sys.argv[1], sys.argv[2]; p = os.path.join(r, 'plugins', 'floorplan-to-3d-house')
for f in (os.path.join(r, '.claude-plugin', 'marketplace.json'), os.path.join(p, '.claude-plugin', 'plugin.json')):
    s = open(f).read(); s = re.sub(r'"version": "[0-9.]+"', f'"version": "{v}"', s); open(f, 'w').write(s); json.loads(s)
for f in glob.glob(os.path.join(p, 'skills', '*', 'SKILL.md')):
    s = open(f).read(); open(f, 'w').write(re.sub(r'version: "[0-9.]+"', f'version: "{v}"', s, count=1))
f = os.path.join(p, 'README.md'); s = open(f).read(); open(f, 'w').write(re.sub(r'"version": "[0-9.]+" }', f'"version": "{v}" }}', s))
c = open(os.path.join(p, 'CHANGELOG.md')).read()
if f'## {v} ' not in c: print(f'note: CHANGELOG.md has no "## {v}" entry yet')
PY
mkdir -p "$R/dist"; rm -f "$R/dist/floorplan-to-3d-house.plugin"
(cd "$P" && zip -qr "$R/dist/floorplan-to-3d-house.plugin" . -x "setup/*" -x "*.DS_Store")
grep -rn '"version"\|version: "' "$R/.claude-plugin/marketplace.json" "$P/.claude-plugin/plugin.json" "$P"/skills/*/SKILL.md | sed 's#^.*/\(plugins\|\.claude\)#\1#'
echo "package: dist/floorplan-to-3d-house.plugin ($(du -h "$R/dist/floorplan-to-3d-house.plugin" | cut -f1))"
