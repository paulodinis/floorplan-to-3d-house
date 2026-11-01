"""Vector PDF (single page) -> DXF, real-world metres at a given drawing scale."""
import sys, math
from collections import Counter, defaultdict
import pdfplumber
import ezdxf
from ezdxf import colors
from ezdxf.enums import TextEntityAlignment

src, dst, scale = sys.argv[1], sys.argv[2], float(sys.argv[3])  # scale: 200 for 1/200
K = 25.4 / 72.0 * scale / 1000.0  # pt -> metres

VALID_LW = [0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211]

def lw_of(pt):
    mm100 = pt * 25.4 / 72 * 100
    return min(VALID_LW, key=lambda v: abs(v - mm100))

def rgb_of(c):
    if c is None:
        return (0, 0, 0)
    if isinstance(c, (int, float)):
        c = (c, c, c)
    c = tuple(c)
    if len(c) == 1:
        c = (c[0],) * 3
    if len(c) == 4:  # CMYK
        C, M, Y, Kk = c
        c = ((1 - C) * (1 - Kk), (1 - M) * (1 - Kk), (1 - Y) * (1 - Kk))
    return tuple(int(round(max(0, min(1, v)) * 255)) for v in c[:3])

def hexc(rgb):
    return "%02X%02X%02X" % rgb

def P(x, y):
    return (x * K, y * K)

def bez(p0, p1, p2, p3, n=12):
    out = []
    for i in range(1, n + 1):
        t = i / n; u = 1 - t
        out.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                    u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
    return out

def subpaths(path):
    """original_path -> list of (points, closed)"""
    res, cur, closed = [], [], False
    for op in path:
        k = op[0]
        if k == 'm':
            if len(cur) > 1:
                res.append((cur, closed))
            cur, closed = [op[1]], False
        elif k == 'l':
            cur.append(op[1])
        elif k == 'c':
            p0 = cur[-1] if cur else op[1]
            cur.extend(bez(p0, op[1], op[2], op[3]))
        elif k in ('v', 'y'):
            p0 = cur[-1] if cur else op[1]
            if k == 'v':
                cur.extend(bez(p0, p0, op[1], op[2]))
            else:
                cur.extend(bez(p0, op[1], op[2], op[2]))
        elif k == 'h':
            closed = True
    if len(cur) > 1:
        res.append((cur, closed))
    return res

pdf = pdfplumber.open(src)
page = pdf.pages[0]
objs = page.layout._objs

doc = ezdxf.new("R2010", setup=True)
doc.units = ezdxf.units.M
doc.header["$MEASUREMENT"] = 1
doc.header["$LWDISPLAY"] = 1
msp = doc.modelspace()
doc.styles.new("PDF_ARIAL", dxfattribs={"font": "arial.ttf"})
doc.styles.new("PDF_ARIAL_COND", dxfattribs={"font": "arial.ttf", "width": 0.82})

layers = {}
def layer(prefix, rgb):
    name = f"{prefix}_{hexc(rgb)}"
    if name not in layers:
        l = doc.layers.add(name)
        l.rgb = rgb
        layers[name] = l
    return name

def attribs(lay, rgb, lw=None):
    a = {"layer": lay, "true_color": colors.rgb2int(rgb), "color": 256}
    if lw is not None:
        a["lineweight"] = lw
    return a

# --- font-size factor per font (size / |matrix scale|) from upright chars
fk = defaultdict(list)
for o in objs:
    if type(o).__name__ == "LTChar":
        a, b = o.matrix[0], o.matrix[1]
        if abs(b) < 1e-9 and a > 0:
            fk[o.fontname].append(o.size / a)
fk = {f: sorted(v)[len(v) // 2] for f, v in fk.items()}
fk_default = sorted(sum(([x] for v in fk.values() for x in [v]), []))[0] if fk else 1.0

stats = Counter()
text_buf = []  # pending run of chars

def flush_text():
    global text_buf
    if not text_buf:
        return
    while text_buf and not text_buf[0]["t"].strip():
        text_buf.pop(0)
    if not text_buf:
        return
    first = text_buf[0]
    s = "".join(c["t"] for c in text_buf).rstrip()
    if s.strip():
        rgb = first["rgb"]
        lay = layer("TXT", rgb)
        h = first["size"] * 0.72 * K
        style = "PDF_ARIAL_COND" if "Condensed" in first["font"] else "PDF_ARIAL"
        t = msp.add_text(s, height=h, rotation=first["ang"],
                         dxfattribs={**attribs(lay, rgb), "style": style})
        t.set_placement(P(*first["org"]), align=TextEntityAlignment.LEFT)
        stats["TEXT"] += 1
    text_buf = []

for o in objs:
    tn = type(o).__name__
    if tn == "LTChar":
        a, b, c, d, e, f = o.matrix
        ang = math.degrees(math.atan2(b, a))
        th = math.radians(ang); cs, sn = abs(math.cos(th)), abs(math.sin(th))
        L = abs(o.adv) * math.hypot(a, b)
        if cs >= 0.5:
            size = (o.height - L * sn) / cs
        else:
            size = (o.width - L * cs) / sn
        size = max(size, 0.1)
        rgb = rgb_of(o.graphicstate.ncolor)
        adv = o.adv * math.hypot(a, b) / (math.hypot(a, b) or 1)  # text-space adv
        disp = (o.adv * a, o.adv * b)
        ch = {"t": o.get_text(), "org": (e, f), "ang": ang, "size": size, "rgb": rgb,
              "font": o.fontname, "end": (e + disp[0], f + disp[1])}
        if text_buf:
            p = text_buf[-1]
            same = abs(p["ang"] - ang) < 0.5 and abs(p["size"] - size) < 0.05 * size and p["rgb"] == rgb
            ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            dx, dy = e - p["end"][0], f - p["end"][1]
            along, perp = dx * ux + dy * uy, -dx * uy + dy * ux
            if same and abs(perp) < 0.2 * size and -0.3 * size < along < 0.45 * size:
                if along > 0.22 * size and ch["t"] != " " and p["t"] != " ":
                    text_buf.append({**p, "t": " "})
                text_buf.append(ch)
                continue
            flush_text()
        text_buf.append(ch)
        continue
    flush_text()

    if not hasattr(o, "original_path"):
        continue
    stroke, fill = o.stroke, o.fill
    srgb = rgb_of(o.stroking_color)
    frgb = rgb_of(o.non_stroking_color)
    lw = lw_of(o.linewidth or 0)
    sps = subpaths(o.original_path) if o.original_path else [(list(o.pts), False)]

    if fill:
        lay = layer("FILL", frgb)
        hatch = msp.add_hatch(dxfattribs=attribs(lay, frgb))
        hatch.set_solid_fill(color=256, rgb=frgb)
        hatch.dxf.hatch_style = 0
        for pts, _ in sps:
            if len(pts) >= 3:
                hatch.paths.add_polyline_path([P(*q) for q in pts], is_closed=True)
        if not hatch.paths.paths:
            msp.delete_entity(hatch)
        else:
            stats["HATCH"] += 1
    if stroke:
        lay = layer("LIN", srgb)
        for pts, closed in sps:
            if tn == "LTLine" or (len(pts) == 2 and not closed):
                msp.add_line(P(*pts[0]), P(*pts[-1]), dxfattribs=attribs(lay, srgb, lw))
                stats["LINE"] += 1
            else:
                msp.add_lwpolyline([P(*q) for q in pts], close=closed,
                                   dxfattribs=attribs(lay, srgb, lw))
                stats["LWPOLYLINE"] += 1
flush_text()

doc.set_modelspace_vport(height=page.height * K, center=(page.width * K / 2, page.height * K / 2))
doc.saveas(dst)
print(dict(stats), "layers:", len(layers), "extent m:", round(page.width * K, 2), "x", round(page.height * K, 2))
