#!/usr/bin/env python3
"""Generates every branded image Loophole ships (stable channel) from ONE vector mark.

    python3 icons/loophole/build_icons.py            # regenerate all icons from icons/loophole/mark-path.txt
    python3 icons/loophole/build_icons.py --retrace icons/loophole/source-logo.png
                                                      # re-trace the mark from a new white-on-dark logo first
Needs: Pillow (and `potracer numpy` only for --retrace). Also needs the `vscode/` checkout (run dev/verify-patches.sh
or get_repo.sh first), because the Windows/macOS *file-type* icons are the original document icons with our logo drawn
over the old badge.

To change the logo: replace source-logo.png (white mark on a dark square, ideally >=1024px) and run with --retrace.
"""
import argparse, io, json, os, re, struct, subprocess, sys
from PIL import Image, ImageChops, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, 'src', 'stable', 'resources')
BG = (11, 11, 12, 255)          # icon background (matches the current Loophole icon)
FG = (255, 255, 255, 255)
SRC_SIZE = 512.0                # mark-path.txt coordinates live in this 512x512 canvas
SS = 4                          # supersampling factor for anti-aliasing


# ---------- vector mark ----------
def retrace(png):
    import numpy as np, potrace
    a = np.array(Image.open(png).convert('L'))
    scale = SRC_SIZE / a.shape[0]
    pl = potrace.Bitmap(a <= 128).trace(turdsize=50, turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
                                        alphamax=1.0, opticurve=True, opttolerance=0.4)
    d = []
    f = lambda p: f"{p.x * scale:.2f},{p.y * scale:.2f}"
    for c in pl:
        d.append('M' + f(c.start_point))
        for s in c.segments:
            d.append(f"L{f(s.c)}L{f(s.end_point)}" if s.is_corner else f"C{f(s.c1)},{f(s.c2)},{f(s.end_point)}")
        d.append('Z')
    open(os.path.join(HERE, 'mark-path.txt'), 'w').write(''.join(d))
    print('retraced', len(pl), 'path(s)')


def load_path():
    return open(os.path.join(HERE, 'mark-path.txt')).read().strip()


def contours(path):
    """Flatten the M/L/C/Z path we generate into polygons (512-space)."""
    polys, cur, pos = [], [], (0, 0)
    for cmd, args in re.findall(r'([MLCZ])([^MLCZ]*)', path):
        n = [float(x) for x in re.findall(r'-?\d+\.?\d*', args)]
        if cmd == 'M':
            cur = [(n[0], n[1])]; pos = cur[0]
        elif cmd == 'L':
            for i in range(0, len(n), 2):
                pos = (n[i], n[i + 1]); cur.append(pos)
        elif cmd == 'C':
            for i in range(0, len(n), 6):
                x0, y0 = pos; x1, y1, x2, y2, x3, y3 = n[i:i + 6]
                for k in range(1, 25):
                    t = k / 24; u = 1 - t
                    cur.append((u**3*x0 + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*x3,
                                u**3*y0 + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*y3))
                pos = (x3, y3)
        elif cmd == 'Z':
            polys.append(cur); cur = []
    return polys


PATH = load_path()
POLYS = contours(PATH)
_xs = [p[0] for poly in POLYS for p in poly]; _ys = [p[1] for poly in POLYS for p in poly]
BBOX = (min(_xs), min(_ys), max(_xs), max(_ys))


def mark_mask(size_px, origin, scale):
    """L-mode mask (supersampled by caller) of the mark. origin/scale map 512-space -> pixels."""
    m = Image.new('L', size_px, 0)
    for poly in POLYS:
        layer = Image.new('L', size_px, 0)
        ImageDraw.Draw(layer).polygon([(origin[0] + x * scale, origin[1] + y * scale) for x, y in poly], fill=255)
        m = ImageChops.difference(m, layer)          # even-odd fill
    return m


# ---------- raster icon ----------
def icon(size, margin=0.0, radius=0.2237, bg=BG):
    """Rounded square with the mark. `margin` = transparent border as a fraction of size (macOS uses ~0.0977)."""
    S = size * SS
    body = S * (1 - 2 * margin); off = S * margin
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    plate = Image.new('L', (S, S), 0)
    ImageDraw.Draw(plate).rounded_rectangle([off, off, off + body - 1, off + body - 1], radius=body * radius, fill=255)
    img.paste(Image.new('RGBA', (S, S), bg), (0, 0), plate)
    k = body / SRC_SIZE
    fg = Image.new('RGBA', (S, S), FG)
    img.paste(fg, (0, 0), mark_mask((S, S), (off, off), k))
    return img.resize((size, size), Image.LANCZOS)


def on_color(im, color):
    base = Image.new('RGBA', im.size, color); base.alpha_composite(im); return base


def save(img, rel, **kw):
    p = os.path.join(ROOT, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    img.save(p, **kw); print('wrote', rel)


# ---------- containers ----------
def build_icns(images):
    """Write an .icns from {pixel_size: RGBA image} using PNG payloads (ic07..ic14)."""
    types = {128: b'ic07', 256: b'ic08', 512: b'ic09', 1024: b'ic10'}
    out = b''
    for px, im in sorted(images.items()):
        if px not in types: continue
        b = io.BytesIO(); im.resize((px, px), Image.LANCZOS).save(b, 'PNG'); data = b.getvalue()
        out += types[px] + struct.pack('>I', len(data) + 8) + data
    return b'icns' + struct.pack('>I', len(out) + 8) + out


def ms_original(rel):
    commit = json.load(open(os.path.join(ROOT, 'upstream', 'stable.json')))['commit']
    return subprocess.check_output(['git', '-C', os.path.join(ROOT, 'vscode'), 'show', f'{commit}:{rel}'])


# ---------- SVG ----------
def svg_icon(margin=0.0, radius=0.2237):
    body = 512 * (1 - 2 * margin); off = 512 * margin
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 512 512">\n'
            f'  <rect x="{off:.2f}" y="{off:.2f}" width="{body:.2f}" height="{body:.2f}" rx="{body*radius:.2f}" fill="#0B0B0C"/>\n'
            f'  <g transform="translate({off:.2f} {off:.2f}) scale({body/512:.5f})"><path fill="#FFFFFF" fill-rule="evenodd" d="{PATH}"/></g>\n</svg>\n')


def svg_letterpress(fill, opacity=None):
    h = 28.0; k = h / (BBOX[3] - BBOX[1]); cx = (BBOX[0] + BBOX[2]) / 2; cy = (BBOX[1] + BBOX[3]) / 2
    op = f' opacity="{opacity}"' if opacity else ''
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">\n'
            f'  <path transform="translate({20 - cx*k:.3f} {20 - cy*k:.3f}) scale({k:.5f})" fill="{fill}"{op} fill-rule="evenodd" d="{PATH}"/>\n</svg>\n')


def write_text(rel, text):
    p = os.path.join(ROOT, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w').write(text); print('wrote', rel)


# ---------- build everything ----------
def build():
    # Linux
    big = icon(1024, margin=0.04)
    save(big, 'src/stable/resources/linux/code.png')
    write_text('src/stable/resources/linux/code.svg', svg_icon(0.04))
    tmp = os.path.join(ROOT, 'src/stable/resources/linux/rpm/code.xpm'); os.makedirs(os.path.dirname(tmp), exist_ok=True)
    icon(128, margin=0.04).save('/tmp/_loophole_xpm.png'); subprocess.check_call(['convert', '/tmp/_loophole_xpm.png', tmp]); print('wrote src/stable/resources/linux/rpm/code.xpm')
    # server / web
    save(icon(192, margin=0.04), 'src/stable/resources/server/code-192.png')
    save(icon(512, margin=0.04), 'src/stable/resources/server/code-512.png')
    ico_sizes = [(256, 256), (128, 128), (96, 96), (64, 64), (48, 48), (32, 32), (24, 24), (20, 20), (16, 16)]
    win = icon(256, margin=0.02)
    save(win, 'src/stable/resources/server/favicon.ico', sizes=ico_sizes)
    # editor-internal SVGs
    write_text('src/stable/src/vs/workbench/browser/media/code-icon.svg', svg_icon(0.0))
    for name, fill, op in [('dark', '#B2B2B2', '0.3'), ('hcDark', '#3C3C3C', None), ('hcLight', '#B2B2B2', None), ('light', '#B2B2B2', '0.1')]:
        write_text(f'src/stable/src/vs/workbench/browser/parts/editor/media/letterpress-{name}.svg', svg_letterpress(fill, op))
    # Windows app icon + tiles
    save(win, 'src/stable/resources/win32/code.ico', sizes=ico_sizes)
    for px, logo, where in [(70, 45, 'center'), (150, 64, (44, 25))]:
        c = Image.new('RGBA', (px, px), (0, 0, 0, 0)); l = icon(logo, margin=0.02)
        c.alpha_composite(l, ((px - logo) // 2, (px - logo) // 2) if where == 'center' else where)
        save(c, f'src/stable/resources/win32/code_{px}x{px}.png')
    # Windows installer images (Inno Setup + WiX): white canvas, logo placed like upstream
    def banner(rel, size, logo, where):
        c = Image.new('RGB', size, 'white'); l = icon(logo, margin=0.02)
        pos = ((size[0] - logo) // 2, (size[1] - logo) // 2) if where == 'center' else where
        c.paste(l, pos, l); save(c, rel)
    for dpi, (w, h, lg) in {'100': (164, 314, 126), '125': (192, 386, 147), '150': (246, 459, 190), '175': (273, 556, 211),
                            '200': (328, 604, 255), '225': (355, 700, 273), '250': (410, 797, 317)}.items():
        banner(f'src/stable/resources/win32/inno-big-{dpi}.bmp', (w, h), lg, 'center')
    for dpi, (w, h, lg) in {'100': (55, 55, 44), '125': (64, 68, 52), '150': (83, 80, 63), '175': (92, 97, 76),
                            '200': (110, 106, 86), '225': (119, 123, 103), '250': (138, 140, 116)}.items():
        banner(f'src/stable/resources/win32/inno-small-{dpi}.bmp', (w, h), lg, 'center')
    banner('build/windows/msi/resources/stable/wix-banner.bmp', (493, 58), 50, (438, 6))
    banner('build/windows/msi/resources/stable/wix-dialog.bmp', (493, 312), 120, (22, 152))
    # Windows file-type icons: Microsoft's original document icon, our logo drawn over the old badge
    badge = on_color(icon(64, margin=0.02), (0xF5, 0xF6, 0xF7, 255))
    for fn in sorted(os.listdir(os.path.join(RES, 'win32'))):
        if not fn.endswith('.ico') or fn == 'code.ico': continue
        ico = Image.open(io.BytesIO(ms_original(f'resources/win32/{fn}')))
        base = ico.ico.getimage((256, 256)).convert('RGBA') if hasattr(ico, 'ico') else ico.convert('RGBA').resize((256, 256))
        base.alpha_composite(badge, (150, 185)); save(base, f'src/stable/resources/win32/{fn}', sizes=ico_sizes)
    # macOS app icon (Apple grid: ~100px transparent margin at 1024) and file-type icons
    mac = icon(1024, margin=0.0977)
    open(os.path.join(RES, 'darwin', 'code.icns'), 'wb').write(build_icns({s: mac for s in (128, 256, 512, 1024)})); print('wrote src/stable/resources/darwin/code.icns')
    # Microsoft's badge in VS Code 1.140 occupies x 336-469, y 381-494 of the 512px icon (measured, see README);
    # our badge is drawn 144px at (332,366) so it fully covers it. Re-measure after big upstream icon changes.
    logo = icon(144, margin=0.0)
    for fn in sorted(os.listdir(os.path.join(RES, 'darwin'))):
        if not fn.endswith('.icns') or fn == 'code.icns': continue
        base = Image.open(io.BytesIO(ms_original(f'resources/darwin/{fn}'))).convert('RGBA').resize((512, 512))
        base.alpha_composite(logo, (332, 366))
        open(os.path.join(RES, 'darwin', fn), 'wb').write(build_icns({512: base, 256: base})); print('wrote src/stable/resources/darwin/' + fn)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--retrace', metavar='PNG'); a = ap.parse_args()
    if a.retrace: retrace(a.retrace)
    build()
