"""Turn target colours read from style photos into a style.json (tint multipliers on the default look).

Usage:  python3 style_from_colors.py out_style.json --name "My style" --roof terracotta|flat_dark \\
            --set render=#f1ede4 stone=#bfae93 slats=#8a5a36 frame=#ffffff roof=#2f3338 ...
Keys: render, stone, slats, garage, front, frame, soffit, roof, terrace, plinth, retain, oak.
Each target is compared with the default material colour (DEFAULTS, sRGB, measured on the default look) in linear
space; the multiplier is clamped to 0.25..6. Check the result by building the page with "style": <inline object>.
"""
import json, sys

DEFAULTS = {'render': '#f2efe8', 'stone': '#d9c7a5', 'slats': '#a8744a', 'garage': '#a8744a', 'front': '#5a3e2c', 'frame': '#2b2d30',
            'soffit': '#f4f2ee', 'roof': '#3d4249', 'terrace': '#d6d1c7', 'plinth': '#9c968c', 'retain': '#e0d6c4', 'oak': '#b5835a'}


def lin(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


args = sys.argv[1:]
out = args[0]
name = args[args.index('--name') + 1] if '--name' in args else 'Custom style'
roof = args[args.index('--roof') + 1] if '--roof' in args else 'flat_dark'
sets = args[args.index('--set') + 1:] if '--set' in args else []
tint = {}
for kv in sets:
    if kv.startswith('--'): break
    k, v = kv.split('=')
    if k not in DEFAULTS: sys.exit(f'unknown key {k}; use one of {sorted(DEFAULTS)}')
    d, t = lin(DEFAULTS[k]), lin(v)
    tint[k] = [round(min(6, max(0.25, ti / max(di, 1e-3))), 3) for di, ti in zip(d, t)]
style = dict(name=name, description='Derived from reference photos', roof_tile=roof, tint=tint)
json.dump(style, open(out, 'w'), indent=1)
print(json.dumps(style))
