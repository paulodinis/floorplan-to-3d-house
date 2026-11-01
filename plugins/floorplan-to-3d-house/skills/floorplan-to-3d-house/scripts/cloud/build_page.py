"""Build the interactive 3D page from project.json + site.json + layout.json.

Usage (from the project work dir, which holds site3d/):
    python3 build_page.py project.json            -> site3d/page.html (local tests) + site3d/publish.html (publish this)
    python3 build_page.py project.json --export   -> site3d/export.html (UI hidden, GLB/renders exporter included)

The page loads textures from tex/ next to it (publish the files in site3d/tex/ with it).
"""
import html, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.normpath(os.path.join(HERE, '..', 'web'))
proj_path = sys.argv[1]
export = '--export' in sys.argv
P = json.load(open(proj_path, encoding='utf-8'))
site = json.load(open('site3d/site.json', encoding='utf-8'))
lay = json.load(open('site3d/layout.json', encoding='utf-8'))
I18N = json.load(open(os.path.join(WEB, 'i18n.json'), encoding='utf-8'))
lang = P.get('lang', 'en')
S = dict(I18N['en']); S.update(I18N.get(lang, {})); S.update(P.get('ui', {}))
esc = html.escape


def num(v, d=2):
    s = f'{v:,.{d}f}'.replace(',', ' ')
    return s.replace('.', S['decimal']) if S['decimal'] != '.' else s


lat = P.get('location', {}).get('lat', 40.0)
north = P.get('north_deg', site['meta'].get('north_deg', 0))
limit = P.get('area_limit') or lay.get('meta', {}).get('area_limit')
title = P.get('name', 'House')
sub = [esc(P.get('subtitle', ''))]
if P.get('show_address_on_page') and P.get('location', {}).get('address'):
    sub.append(esc(P['location']['address']))      # off by default: the page can be shared
rows = []
blocks = lay['blocks']
for b in blocks.values():
    rows.append(f'      <tr><td class="v">{num(b["area"])} {S["m2"]}</td><td>{esc(b["name"])}</td></tr>')
total = sum(b['area'] for b in blocks.values())
rows.append(f'      <tr><td class="v"><b>{num(total)} {S["m2"]}</b></td><td><b>{esc(S["total"])}</b></td></tr>')
if lay.get('meta', {}).get('plot_area'):
    rows.append(f'      <tr><td class="v">{num(lay["meta"]["plot_area"], 0)} {S["m2"]}</td><td>{esc(S["plot"])}</td></tr>')
levels = {}
for b in blocks.values():
    if 'level' in b: levels.setdefault(b['level'], []).append(b['name'])
for lv in sorted(levels, reverse=True):
    rows.append(f'      <tr><td class="v">{num(lv)}</td><td>{esc(S["level"])}: {esc(", ".join(levels[lv]))}</td></tr>')
notes = P.get('notes', [])
notes_html = '      <ul>\n' + '\n'.join(
    f'        <li><b>{esc(n[0])}</b> {esc(n[1])}</li>' if isinstance(n, list) else f'        <li>{esc(n)}</li>' for n in notes) + '\n      </ul>' if notes else ''
fill = dict(S)
fill.update(
    page_title=S['page_title'].format(title=esc(title)), title=esc(title), eyebrow=esc(P.get('eyebrow', S['badge'])),
    subtitle_html='<br>'.join(x for x in sub if x),
    sun_label=S['sun_label'].format(lat=f'{abs(lat):.0f}', ns='N' if lat >= 0 else 'S', north=f'{north:.0f}'),
    areas_label=S['areas_label'].format(limit=f'{limit:.0f}') if limit else S['areas_label_nolimit'],
    areas_rows='\n'.join(rows), notes_html=notes_html)
t = open(os.path.join(WEB, 'template.html'), encoding='utf-8').read()
for k, v in fill.items():
    t = t.replace('{{' + k + '}}', str(v))
assert '{{' not in t, 'unfilled placeholder: ' + t[t.index('{{'):t.index('{{') + 40]
eng = open(os.path.join(WEB, 'engine.js'), encoding='utf-8').read()
proj_js = dict(P); proj_js['ui'] = S                       # engine reads PROJ.ui.show / hide / load_fail
st = P.get('style')                                         # preset name (styles/<name>.json) or an inline style object
if isinstance(st, str):
    sp = os.path.normpath(os.path.join(HERE, '..', '..', 'styles', st + '.json'))
    proj_js['style_data'] = json.load(open(sp, encoding='utf-8')) if os.path.exists(sp) else {}
    if not os.path.exists(sp): print('warning: style preset not found:', st)
elif isinstance(st, dict):
    proj_js['style_data'] = st
proj_js.get('location', {}).pop('address', None)           # never embed the address in the page code
eng = (eng.replace('__SITE_JSON__', json.dumps(site, separators=(',', ':')))
          .replace('__LAYOUT_JSON__', json.dumps(lay, separators=(',', ':')))
          .replace('__PROJECT_JSON__', json.dumps(proj_js, separators=(',', ':'), ensure_ascii=False)))
extra = open(os.path.join(WEB, 'export_glb.js'), encoding='utf-8').read() if export else ''
frag = t + '<script type="module">\n' + eng + '\n' + extra + '\n</script>\n'
i = frag.index('</style>') + len('</style>')
hide = '<style>#panel,#hint,.compass,#nav-help,#crosshair,#joy,#drone-up,#drone-down,#toggle-panel{display:none!important}</style>' if export else ''
doc = ('<!DOCTYPE html>\n<html lang="%s">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' % esc(lang)
       + frag[:i] + '\n<style>body{margin:0}</style>\n' + hide + '\n</head>\n<body>' + frag[i:] + '\n</body>\n</html>\n')
out = 'site3d/export.html' if export else 'site3d/publish.html'
open(out, 'w', encoding='utf-8').write(doc)
if not export:
    open('site3d/page.html', 'w', encoding='utf-8').write(doc)
print('built', out, len(doc), 'bytes')
