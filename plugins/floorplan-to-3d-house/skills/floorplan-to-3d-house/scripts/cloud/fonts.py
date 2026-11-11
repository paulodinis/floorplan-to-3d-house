"""Cross-platform font lookup for the PIL sheets (plans, elevations, sun report, path previews).

font(size, bold=False) never raises: a missing font changes the typeface, it never aborts a sheet.
Lookup order: FLOORPLAN_FONT / FLOORPLAN_FONT_BOLD (env, a .ttf/.otf/.ttc path), then the candidates below
(Linux, macOS, Windows). The first candidate that has every glyph in GLYPHS wins (the level mark ▽, drawn only in
the regular weight, is missing from Arial and Segoe UI); if none has them all, the first one that loads; if none loads, Pillow's bundled font.
"""
import os
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

GLYPHS = '▽²°·–—→≥çãõáéíóúàêÁÓ'      # non-ASCII characters drawn by the cloud scripts (pt-PT labels included)

_CANDIDATES = {
    False: ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',                 # Debian / Ubuntu
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',                          # Fedora
            '/usr/share/fonts/TTF/DejaVuSans.ttf',                             # Arch
            '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',            # macOS
            '/Library/Fonts/Arial Unicode.ttf',
            'C:/Windows/Fonts/seguisym.ttf',                                   # Windows (Segoe UI Symbol)
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
            '/System/Library/Fonts/Supplemental/Arial.ttf',
            '/Library/Fonts/Arial.ttf',
            '/System/Library/Fonts/Helvetica.ttc',
            'C:/Windows/Fonts/segoeui.ttf',
            'C:/Windows/Fonts/arial.ttf',
            'DejaVuSans.ttf', 'Arial.ttf', 'arial.ttf'],                       # FreeType's own search path
    True: ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
           '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
           '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
           '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
           '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
           '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
           '/Library/Fonts/Arial Bold.ttf',
           'C:/Windows/Fonts/segoeuib.ttf',
           'C:/Windows/Fonts/arialbd.ttf',
           'DejaVuSans-Bold.ttf', 'Arial Bold.ttf', 'arialbd.ttf'],
}


def _glyph(f, ch):
    im = Image.new('L', (64, 64)); ImageDraw.Draw(im).text((8, 8), ch, font=f, fill=255)
    return im.tobytes()


def _covers(f, glyphs):
    missing = _glyph(f, '\U0010FFFD')            # unassigned code point: renders as the font's .notdef glyph
    return all(_glyph(f, ch) != missing for ch in glyphs)


@lru_cache(maxsize=None)
def _path(bold):
    env = os.environ.get('FLOORPLAN_FONT_BOLD' if bold else 'FLOORPLAN_FONT')
    if env:
        try:
            ImageFont.truetype(env, 12)
            return env
        except OSError:
            pass
    first = None
    for p in _CANDIDATES[bold] + (_CANDIDATES[False] if bold else []):   # no bold face: use a regular one
        try:
            f = ImageFont.truetype(p, 24)
        except OSError:
            continue
        if _covers(f, GLYPHS.replace('▽', '') if bold else GLYPHS):     # ▽ is only drawn in the regular weight
            return p
        first = first or p
    return first


@lru_cache(maxsize=None)
def font(size, bold=False):
    size = int(size)
    p = _path(bool(bold))
    if p:
        return ImageFont.truetype(p, size)
    try:
        return ImageFont.load_default(size)      # Pillow >= 10.1: scalable bundled font
    except TypeError:
        return ImageFont.load_default()
