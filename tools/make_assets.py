#!/usr/bin/env python3
"""Generates the showcase assets in assets/ (stdlib + ffmpeg with librsvg).

  python3 tools/make_assets.py

Everything is procedural SVG; PNG stills and MP4 loops are rasterized from
SVG frames with ffmpeg, so the demo never needs the network.
"""

from __future__ import annotations

import math
import pathlib
import random
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"


def write(name: str, svg: str) -> pathlib.Path:
  p = OUT / name
  p.write_text(svg)
  return p


def svg_doc(w: int, h: int, body: str, defs: str = "") -> str:
  return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
          f"<defs>{defs}</defs>{body}</svg>")


def ffmpeg(*args: str) -> None:
  subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def to_png(svg_path: pathlib.Path, png_name: str) -> None:
  ffmpeg("-i", str(svg_path), "-frames:v", "1", str(OUT / png_name))


def hexc(rgb) -> str:
  return "#%02x%02x%02x" % tuple(max(0, min(255, int(c * 255))) for c in rgb)


# --------------------------------------------------------------- render scene
def sphere(cx, cy, r, color, gid, light=(-0.35, -0.45)):
  base = color
  hi = tuple(min(1, c * 1.6 + 0.25) for c in base)
  lo = tuple(c * 0.18 for c in base)
  fx = 50 + light[0] * 60
  fy = 50 + light[1] * 60
  defs = (f'<radialGradient id="{gid}" cx="{fx}%" cy="{fy}%" r="75%" fx="{fx}%" fy="{fy}%">'
          f'<stop offset="0" stop-color="{hexc(hi)}"/><stop offset="0.35" stop-color="{hexc(base)}"/>'
          f'<stop offset="1" stop-color="{hexc(lo)}"/></radialGradient>')
  shadow = (f'<ellipse cx="{cx + r * 0.35}" cy="{cy + r * 0.95}" rx="{r * 1.05}" ry="{r * 0.22}" '
            f'fill="#000" opacity="0.45" filter="url(#blur)"/>')
  body = f'{shadow}<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{gid})"/>'
  return defs, body


def render_scene(w=640, h=360, t=0.0, noise=0.0) -> str:
  defs = ('<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
          '<stop offset="0" stop-color="#1d2b44"/><stop offset="0.55" stop-color="#6b7fa3"/>'
          '<stop offset="1" stop-color="#e8c7a0"/></linearGradient>'
          '<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">'
          '<stop offset="0" stop-color="#4a4a52"/><stop offset="1" stop-color="#17171b"/></linearGradient>'
          '<filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>'
          '<filter id="grain"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="1" seed="SEED"/>'
          '<feColorMatrix type="saturate" values="0"/></filter>').replace("SEED", str(int(t * 1000)))
  horizon = h * 0.58
  body = [f'<rect width="{w}" height="{h}" fill="url(#sky)"/>',
          f'<rect y="{horizon}" width="{w}" height="{h - horizon}" fill="url(#floor)"/>']
  # perspective floor grid
  for i in range(-12, 13):
    x2 = w / 2 + i * w * 0.16
    body.append(f'<line x1="{w / 2 + i * 6}" y1="{horizon}" x2="{x2}" y2="{h}" stroke="#ffffff" stroke-opacity="0.05"/>')
  for k in range(1, 9):
    y = horizon + (h - horizon) * (k / 8) ** 1.8
    body.append(f'<line x1="0" y1="{y}" x2="{w}" y2="{y}" stroke="#ffffff" stroke-opacity="0.05"/>')
  # sun glow
  body.append(f'<circle cx="{w * 0.78}" cy="{horizon - 18}" r="{h * 0.22}" fill="#ffd9a0" opacity="0.18" filter="url(#blur)"/>')
  objs = [((0.92, 0.38, 0.12), 0.0, 0.17), ((0.25, 0.55, 0.95), 2.1, 0.12), ((0.85, 0.85, 0.82), 4.2, 0.10)]
  placed = []
  for i, (col, ph, rr) in enumerate(objs):
    a = ph + t * 2 * math.pi
    depth = 0.5 + 0.5 * math.sin(a)
    x = w / 2 + math.cos(a) * w * 0.26
    r = h * rr * (0.75 + 0.45 * (1 - depth))
    y = horizon + (h - horizon) * (0.25 + 0.5 * (1 - depth)) - r
    placed.append((depth, x, y, r, col, i))
  placed.sort(key=lambda p: -p[0])
  for depth, x, y, r, col, i in placed:
    d, b = sphere(x, y, r, col, f"s{i}")
    defs += d
    body.append(b)
  # a cube
  cx, cy, s = w * 0.36, horizon + 6, h * 0.07
  body.append(f'<polygon points="{cx - s},{cy} {cx},{cy - s * 0.55} {cx + s},{cy} {cx},{cy + s * 0.55}" fill="#c9cdd6"/>')
  body.append(f'<polygon points="{cx - s},{cy} {cx},{cy + s * 0.55} {cx},{cy + s * 1.55} {cx - s},{cy + s}" fill="#7d828e"/>')
  body.append(f'<polygon points="{cx + s},{cy} {cx},{cy + s * 0.55} {cx},{cy + s * 1.55} {cx + s},{cy + s}" fill="#4f535c"/>')
  if noise > 0:
    body.append(f'<rect width="{w}" height="{h}" filter="url(#grain)" opacity="{noise:.3f}"/>')
  return svg_doc(w, h, "".join(body), defs)


def viewport(w=960, h=540) -> str:
  defs = ('<linearGradient id="vbg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3d3d3d"/>'
          '<stop offset="1" stop-color="#2b2b2b"/></linearGradient>')
  body = [f'<rect width="{w}" height="{h}" fill="url(#vbg)"/>']
  cx, cy = w / 2, h * 0.6
  for i in range(-20, 21):
    op = 0.18 if i % 5 else 0.3
    body.append(f'<line x1="{cx + i * 40 - 400}" y1="{cy - i * 10 - 100}" x2="{cx + i * 40 + 400}" y2="{cy - i * 10 + 100}" '
                f'stroke="#555" stroke-opacity="{op}"/>')
    body.append(f'<line x1="{cx + i * 40 - 400}" y1="{cy + i * 10 + 100}" x2="{cx + i * 40 + 400}" y2="{cy + i * 10 - 100}" '
                f'stroke="#555" stroke-opacity="{op}"/>')
  body.append(f'<line x1="0" y1="{cy + cx * 0.25}" x2="{w}" y2="{cy - cx * 0.25}" stroke="#ff3352" stroke-opacity="0.7" stroke-width="1.5"/>')
  body.append(f'<line x1="0" y1="{cy - cx * 0.25}" x2="{w}" y2="{cy + cx * 0.25}" stroke="#8bdc00" stroke-opacity="0.7" stroke-width="1.5"/>')
  s = 80
  top = f"{cx - s},{cy - s * 1.1} {cx},{cy - s * 1.6} {cx + s},{cy - s * 1.1} {cx},{cy - s * 0.6}"
  left = f"{cx - s},{cy - s * 1.1} {cx},{cy - s * 0.6} {cx},{cy + s * 0.4} {cx - s},{cy - s * 0.1}"
  right = f"{cx + s},{cy - s * 1.1} {cx},{cy - s * 0.6} {cx},{cy + s * 0.4} {cx + s},{cy - s * 0.1}"
  body += [f'<polygon points="{top}" fill="#bdbdbd"/>', f'<polygon points="{left}" fill="#8e8e8e"/>',
           f'<polygon points="{right}" fill="#6f6f6f"/>']
  outline = f"{cx - s},{cy - s * 1.1} {cx},{cy - s * 1.6} {cx + s},{cy - s * 1.1} {cx + s},{cy - s * 0.1} {cx},{cy + s * 0.4} {cx - s},{cy - s * 0.1}"
  body.append(f'<polygon points="{outline}" fill="none" stroke="#ffaa40" stroke-width="2.5"/>')
  body.append(f'<circle cx="{cx}" cy="{cy - s * 0.6}" r="4" fill="#ffaa40"/>')
  # light + camera gizmos
  body.append(f'<circle cx="{cx + 230}" cy="{cy - 230}" r="10" fill="none" stroke="#111" stroke-width="2"/>'
              f'<line x1="{cx + 230}" y1="{cy - 220}" x2="{cx + 230}" y2="{cy - 120}" stroke="#111" stroke-dasharray="4 4"/>')
  body.append(f'<polygon points="{cx - 300},{cy - 150} {cx - 220},{cy - 190} {cx - 220},{cy - 110}" fill="none" stroke="#111" stroke-width="2"/>'
              f'<polygon points="{cx - 220},{cy - 196} {cx - 206},{cy - 210} {cx - 192},{cy - 196}" fill="#111"/>')
  body.append('<text x="14" y="26" fill="#ddd" font-family="sans-serif" font-size="14">User Perspective</text>'
              '<text x="14" y="44" fill="#bbb" font-family="sans-serif" font-size="13">(1) Collection | Cube</text>')
  # navigation gizmo
  gx, gy = w - 60, 70
  for ang, col, lab in ((-20, "#ff3352", "X"), (200, "#8bdc00", "Y"), (-90, "#2890ff", "Z")):
    x2, y2 = gx + 32 * math.cos(math.radians(ang)), gy + 32 * math.sin(math.radians(ang))
    body.append(f'<line x1="{gx}" y1="{gy}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="2"/>'
                f'<circle cx="{x2}" cy="{y2}" r="9" fill="{col}"/>'
                f'<text x="{x2 - 4}" y="{y2 + 4}" font-family="sans-serif" font-size="11" font-weight="bold">{lab}</text>')
  return svg_doc(w, h, "".join(body), defs)


def material_ball(color, rough=0.5, metal=False, label=None, pattern=None, size=256, emissive=False) -> str:
  c = color
  hi = tuple(min(1, x * (2.2 if metal else 1.4) + (0.15 if rough > 0.6 else 0.4)) for x in c)
  lo = tuple(x * (0.05 if metal else 0.25) for x in c)
  if emissive:
    hi, lo = tuple(min(1, x + 0.5) for x in c), c
  spec = 0.85 - rough * 0.8
  defs = (f'<pattern id="chk" width="32" height="32" patternUnits="userSpaceOnUse">'
          f'<rect width="32" height="32" fill="#3a3a3a"/><rect width="16" height="16" fill="#4a4a4a"/>'
          f'<rect x="16" y="16" width="16" height="16" fill="#4a4a4a"/></pattern>'
          f'<radialGradient id="ball" cx="38%" cy="34%" r="70%"><stop offset="0" stop-color="{hexc(hi)}"/>'
          f'<stop offset="0.45" stop-color="{hexc(c)}"/><stop offset="1" stop-color="{hexc(lo)}"/></radialGradient>'
          f'<radialGradient id="spec" cx="36%" cy="30%" r="18%"><stop offset="0" stop-color="#fff" stop-opacity="{spec:.2f}"/>'
          f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
          '<filter id="glow"><feGaussianBlur stdDeviation="10"/></filter>'
          '<clipPath id="clip"><circle cx="128" cy="124" r="96"/></clipPath>')
  if pattern == "wood":
    defs += ('<filter id="pat"><feTurbulence type="fractalNoise" baseFrequency="0.01 0.18" numOctaves="3" seed="4"/>'
             '<feColorMatrix type="matrix" values="0 0 0 0 0.35  0 0 0 0 0.2  0 0 0 0 0.08  0 0 0 1.2 0"/></filter>')
  elif pattern == "noise":
    defs += ('<filter id="pat"><feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="4" seed="9"/>'
             '<feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1.1 -0.2"/></filter>')
  elif pattern == "brick":
    defs += ('<pattern id="brk" width="48" height="24" patternUnits="userSpaceOnUse">'
             '<rect width="48" height="24" fill="#d9d2c5"/><rect x="2" y="2" width="44" height="9" fill="#9b3f2c"/>'
             '<rect x="-22" y="14" width="44" height="9" fill="#a8482f"/><rect x="26" y="14" width="44" height="9" fill="#8f3a29"/></pattern>')
  body = ['<rect width="256" height="256" fill="url(#chk)"/>']
  if emissive:
    body.append(f'<circle cx="128" cy="124" r="110" fill="{hexc(c)}" opacity="0.6" filter="url(#glow)"/>')
  body.append('<ellipse cx="140" cy="226" rx="90" ry="14" fill="#000" opacity="0.4"/>')
  body.append('<circle cx="128" cy="124" r="96" fill="url(#ball)"/>')
  if pattern == "brick":
    body.append('<circle cx="128" cy="124" r="96" fill="url(#brk)" opacity="0.85"/>'
                '<circle cx="128" cy="124" r="96" fill="url(#ball)" opacity="0.45"/>')
  elif pattern:
    body.append('<rect width="256" height="256" filter="url(#pat)" clip-path="url(#clip)" opacity="0.8"/>')
  body.append('<circle cx="128" cy="124" r="96" fill="url(#spec)"/>')
  return svg_doc(size, size, "".join(body).replace('width="256" height="256" fill="url(#chk)"', 'width="256" height="256" fill="url(#chk)"'), defs).replace(
      f'width="{size}" height="{size}" viewBox="0 0 {size} {size}"', f'width="{size}" height="{size}" viewBox="0 0 256 256"')


def photo(w=960, h=640, sunset=True) -> str:
  rnd = random.Random(7)
  defs = ('<linearGradient id="psky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#20304f"/>'
          '<stop offset="0.45" stop-color="#d0607a"/><stop offset="0.7" stop-color="#ffb36b"/><stop offset="1" stop-color="#ffe2a8"/></linearGradient>'
          '<linearGradient id="lake" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e08a6a"/>'
          '<stop offset="1" stop-color="#1c2236"/></linearGradient>'
          '<radialGradient id="sun"><stop offset="0" stop-color="#fff6d8"/><stop offset="0.3" stop-color="#ffd27a"/>'
          '<stop offset="1" stop-color="#ffb36b" stop-opacity="0"/></radialGradient>'
          '<filter id="soft"><feGaussianBlur stdDeviation="2"/></filter>')
  hz = h * 0.62
  body = [f'<rect width="{w}" height="{hz}" fill="url(#psky)"/>',
          f'<circle cx="{w * 0.62}" cy="{hz - 40}" r="160" fill="url(#sun)"/>']
  for layer, (col, amp, base) in enumerate((("#7a4a6e", 170, 0.12), ("#4d3352", 110, 0.05), ("#2a1f35", 50, 0.0))):
    pts = [f"0,{hz}"]
    x = -20
    up = layer % 2 == 0
    while x <= w + 40:
      y = hz - h * base - (amp * rnd.uniform(0.55, 1.0) if up else amp * rnd.uniform(0.1, 0.4))
      pts.append(f"{x:.0f},{y:.0f}")
      up = not up
      x += rnd.randint(50, 120) if layer == 0 else rnd.randint(30, 80)
    pts.append(f"{w},{hz}")
    body.append(f'<polygon points="{" ".join(pts)}" fill="{col}" stroke="{col}" stroke-linejoin="round"/>')
  body.append(f'<rect y="{hz}" width="{w}" height="{h - hz}" fill="url(#lake)"/>')
  for i in range(14):
    y = hz + 8 + i * 14
    body.append(f'<rect x="{w * 0.62 - 60 + rnd.uniform(-20, 20)}" y="{y}" width="{120 - i * 6}" height="3" fill="#fff0c0" opacity="{0.6 - i * 0.04:.2f}" filter="url(#soft)"/>')
  # pine silhouettes
  for i in range(18):
    x = rnd.uniform(0, w * 0.35) if i % 2 else rnd.uniform(w * 0.8, w)
    s = rnd.uniform(40, 90)
    body.append(f'<polygon points="{x},{hz - s} {x - s * 0.22},{hz + 4} {x + s * 0.22},{hz + 4}" fill="#120e18"/>')
  return svg_doc(w, h, "".join(body), defs)


def radar(w=640, h=400) -> str:
  rnd = random.Random(3)
  defs = ('<filter id="cells"><feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="4" seed="21"/>'
          '<feComponentTransfer><feFuncA type="discrete" tableValues="0 0 0 0 0.55 0.7 0.85 1"/></feComponentTransfer>'
          '<feColorMatrix type="matrix" values="0 0 0 0 0.2  0 0 0 0 0.85  0 0 0 0 0.35  0 0 0 1 0"/></filter>'
          '<filter id="core"><feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="4" seed="21"/>'
          '<feComponentTransfer><feFuncA type="discrete" tableValues="0 0 0 0 0 0 0.9 1"/></feComponentTransfer>'
          '<feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 0.75  0 0 0 0 0.1  0 0 0 1 0"/></filter>')
  body = [f'<rect width="{w}" height="{h}" fill="#1a2027"/>']
  coast = "M0,250 C80,230 120,280 190,250 S300,180 360,210 S470,260 520,220 S600,170 640,190 L640,400 L0,400 Z"
  body.append(f'<path d="{coast}" fill="#232b33" stroke="#3b4652"/>')
  for i in range(1, 8):
    body.append(f'<line x1="{i * 80}" y1="0" x2="{i * 80}" y2="{h}" stroke="#ffffff" stroke-opacity="0.04"/>')
  for i in range(1, 5):
    body.append(f'<line x1="0" y1="{i * 80}" x2="{w}" y2="{i * 80}" stroke="#ffffff" stroke-opacity="0.04"/>')
  body.append(f'<rect width="{w}" height="{h}" filter="url(#cells)"/><rect width="{w}" height="{h}" filter="url(#core)"/>')
  body.append('<circle cx="300" cy="230" r="5" fill="#fff"/><text x="310" y="234" fill="#fff" font-family="sans-serif" font-size="13">KSFO</text>')
  for r in (60, 120, 180):
    body.append(f'<circle cx="300" cy="230" r="{r}" fill="none" stroke="#fff" stroke-opacity="0.12"/>')
  return svg_doc(w, h, "".join(body), defs)


def mission_map(w=640, h=420) -> str:
  defs = ('<filter id="terrain"><feTurbulence type="fractalNoise" baseFrequency="0.008" numOctaves="5" seed="5"/>'
          '<feColorMatrix type="matrix" values="0.25 0 0 0 0.18  0.35 0 0 0 0.25  0.1 0 0 0 0.12  0 0 0 0 1"/></filter>')
  body = [f'<rect width="{w}" height="{h}" filter="url(#terrain)"/>',
          '<path d="M-10,300 C120,260 200,340 330,300 S520,220 660,260" fill="none" stroke="#5f8fb8" stroke-width="14" opacity="0.8"/>',
          '<path d="M60,0 L140,420" stroke="#d8cfa8" stroke-width="3" opacity="0.5"/>']
  for i in range(0, w, 64):
    body.append(f'<line x1="{i}" y1="0" x2="{i}" y2="{h}" stroke="#fff" stroke-opacity="0.07"/>')
  for i in range(0, h, 64):
    body.append(f'<line x1="0" y1="{i}" x2="{w}" y2="{i}" stroke="#fff" stroke-opacity="0.07"/>')
  wps = [(110, 330), (220, 120), (400, 90), (520, 210), (430, 340), (250, 290)]
  d = "M" + " L".join(f"{x},{y}" for x, y in wps) + " Z"
  body.append(f'<path d="{d}" fill="#4772b3" fill-opacity="0.12" stroke="#ffaa40" stroke-width="2.5" stroke-dasharray="8 6"/>')
  for i, (x, y) in enumerate(wps):
    col = "#ffaa40" if i else "#5bb85b"
    body.append(f'<circle cx="{x}" cy="{y}" r="12" fill="#1d1d1d" stroke="{col}" stroke-width="2.5"/>'
                f'<text x="{x}" y="{y + 4.5}" fill="#fff" font-family="sans-serif" font-size="12" text-anchor="middle" font-weight="bold">{i if i else "H"}</text>')
  body.append('<polygon points="312,192 300,214 312,208 324,214" fill="#fff" stroke="#000"/>')
  return svg_doc(w, h, "".join(body), defs)


def portrait(w=320, h=400, skin="#c98e6b", hair="#3b2a20", cls="#7a5cff") -> str:
  defs = ('<linearGradient id="pbg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2d3550"/>'
          '<stop offset="1" stop-color="#14161f"/></linearGradient>'
          f'<radialGradient id="aura" cx="50%" cy="45%" r="55%"><stop offset="0" stop-color="{cls}" stop-opacity="0.55"/>'
          f'<stop offset="1" stop-color="{cls}" stop-opacity="0"/></radialGradient>')
  body = [f'<rect width="{w}" height="{h}" fill="url(#pbg)"/>', f'<rect width="{w}" height="{h}" fill="url(#aura)"/>',
          f'<path d="M40,400 C50,300 110,270 160,270 C210,270 270,300 280,400 Z" fill="#3c4a6b"/>',
          f'<path d="M95,330 L160,282 L225,330 L210,400 L110,400 Z" fill="#59688f"/>',
          f'<rect x="138" y="225" width="44" height="60" rx="16" fill="{skin}"/>',
          f'<ellipse cx="160" cy="170" rx="66" ry="80" fill="{skin}"/>',
          f'<path d="M92,160 C88,90 130,70 165,72 C210,74 238,105 230,165 C222,130 200,112 160,112 C125,112 102,130 92,160 Z" fill="{hair}"/>',
          '<ellipse cx="135" cy="172" rx="9" ry="6" fill="#fff"/><ellipse cx="185" cy="172" rx="9" ry="6" fill="#fff"/>',
          '<circle cx="135" cy="172" r="4.5" fill="#2f6f4f"/><circle cx="185" cy="172" r="4.5" fill="#2f6f4f"/>',
          f'<path d="M122,158 L148,154 M172,154 L198,158" stroke="{hair}" stroke-width="5" stroke-linecap="round"/>',
          '<path d="M140,215 Q160,228 180,215" stroke="#7a3b2e" stroke-width="4" fill="none" stroke-linecap="round"/>',
          '<path d="M160,175 L154,200 L164,200" stroke="#00000033" stroke-width="3" fill="none"/>']
  return svg_doc(w, h, "".join(body), defs)


def noise_tex(w=200, h=140, seed=2, freq=0.03, ramp=("0.1", "0.9")) -> str:
  defs = (f'<filter id="n"><feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="5" seed="{seed}"/>'
          '<feColorMatrix type="saturate" values="0"/>'
          f'<feComponentTransfer><feFuncR type="table" tableValues="{ramp[0]} {ramp[1]}"/>'
          f'<feFuncG type="table" tableValues="{ramp[0]} {ramp[1]}"/><feFuncB type="table" tableValues="{ramp[0]} {ramp[1]}"/></feComponentTransfer></filter>')
  return svg_doc(w, h, f'<rect width="{w}" height="{h}" filter="url(#n)"/>', defs)


def colored_noise(w=200, h=140) -> str:
  defs = ('<filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.025" numOctaves="5" seed="11"/>'
          '<feColorMatrix type="matrix" values="1.4 0 0 0 0.05  0.6 0.4 0 0 0.0  0 0 0.3 0 0.05  0 0 0 0 1"/></filter>')
  return svg_doc(w, h, f'<rect width="{w}" height="{h}" filter="url(#n)"/>', defs)


def tile_icon(kind: str, size=256) -> str:
  """Simple stylized asset thumbnails (props / geometry)."""
  bg = ('<radialGradient id="tb" cx="50%" cy="40%" r="70%"><stop offset="0" stop-color="#5a5a5a"/>'
        '<stop offset="1" stop-color="#2a2a2a"/></radialGradient>')
  body = ['<rect width="256" height="256" fill="url(#tb)"/>', '<ellipse cx="128" cy="214" rx="80" ry="14" fill="#000" opacity="0.35"/>']
  if kind == "tree":
    body += ['<rect x="118" y="150" width="20" height="64" fill="#6b4a2b"/>',
             '<polygon points="128,30 70,120 186,120" fill="#3f7a3a"/>', '<polygon points="128,70 60,170 196,170" fill="#356b31"/>']
  elif kind == "rock":
    body += ['<polygon points="60,210 80,140 130,110 185,130 205,205" fill="#7c7a76"/>',
             '<polygon points="80,140 130,110 140,160 98,175" fill="#9a9893"/>', '<polygon points="140,160 185,130 205,205 150,210" fill="#5d5b58"/>']
  elif kind == "chair":
    body += ['<rect x="80" y="60" width="96" height="80" rx="8" fill="#b4793f"/>', '<rect x="70" y="138" width="116" height="22" rx="6" fill="#c98a4b"/>',
             '<rect x="78" y="158" width="10" height="56" fill="#7a4f27"/>', '<rect x="168" y="158" width="10" height="56" fill="#7a4f27"/>']
  elif kind == "lamp":
    body += ['<polygon points="96,60 160,60 186,120 70,120" fill="#e9d9b4"/>', '<rect x="124" y="120" width="8" height="80" fill="#333"/>',
             '<ellipse cx="128" cy="204" rx="40" ry="10" fill="#333"/>', '<ellipse cx="128" cy="124" rx="50" ry="10" fill="#ffe7a8" opacity="0.5"/>']
  elif kind == "crate":
    body += ['<polygon points="64,100 128,70 192,100 128,130" fill="#c08d52"/>', '<polygon points="64,100 128,130 128,210 64,180" fill="#9c6f3c"/>',
             '<polygon points="192,100 128,130 128,210 192,180" fill="#7d5730"/>',
             '<path d="M64,100 L128,210 M128,130 L64,180 M192,100 L128,210 M128,130 L192,180" stroke="#5b3e20" stroke-width="5"/>']
  elif kind == "suzanne":
    body += ['<ellipse cx="128" cy="130" rx="74" ry="66" fill="#9b9b9b"/>', '<ellipse cx="62" cy="112" rx="26" ry="18" fill="#8a8a8a"/>',
             '<ellipse cx="194" cy="112" rx="26" ry="18" fill="#8a8a8a"/>', '<ellipse cx="104" cy="118" rx="22" ry="16" fill="#c4c4c4"/>',
             '<ellipse cx="152" cy="118" rx="22" ry="16" fill="#c4c4c4"/>', '<circle cx="106" cy="120" r="7" fill="#333"/>',
             '<circle cx="150" cy="120" r="7" fill="#333"/>', '<ellipse cx="128" cy="166" rx="40" ry="20" fill="#b0b0b0"/>']
  elif kind == "hdri":
    body = ['<linearGradient id="h" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5d8fd0"/><stop offset="0.6" stop-color="#d9e6f2"/>'
            '<stop offset="0.6" stop-color="#5c6b3d"/><stop offset="1" stop-color="#2e3520"/></linearGradient>',
            '<rect width="256" height="256" fill="url(#h)"/>', '<circle cx="180" cy="80" r="22" fill="#fffbe8"/>']
    bg = ""
  return svg_doc(size, size, "".join(body), bg).replace(f'viewBox="0 0 {size} {size}"', 'viewBox="0 0 256 256"')


def bounce_frame(t: float, w=480, h=270) -> str:
  y_ground = h * 0.78
  phase = (t * 2) % 1.0
  hgt = 4 * phase * (1 - phase)
  r = 26
  squash = 1.0 + max(0, 0.08 - hgt) * 4
  cy = y_ground - r - hgt * 150
  cx = w * 0.15 + t * w * 0.7
  defs = ('<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a3f4b"/>'
          '<stop offset="1" stop-color="#22252c"/></linearGradient>'
          '<radialGradient id="ball" cx="35%" cy="30%" r="70%"><stop offset="0" stop-color="#ffd2a0"/>'
          '<stop offset="0.4" stop-color="#e8743b"/><stop offset="1" stop-color="#6a2a10"/></radialGradient>')
  body = [f'<rect width="{w}" height="{h}" fill="url(#bg)"/>', f'<rect y="{y_ground}" width="{w}" height="{h - y_ground}" fill="#1a1c21"/>',
          f'<ellipse cx="{cx}" cy="{y_ground + 2}" rx="{r * (1.3 - hgt * 0.5)}" ry="5" fill="#000" opacity="{0.55 - hgt * 0.35:.2f}"/>',
          f'<ellipse cx="{cx}" cy="{cy + r * (squash - 1)}" rx="{r * squash}" ry="{r / squash}" fill="url(#ball)"/>',
          f'<text x="12" y="22" fill="#9aa" font-family="monospace" font-size="13">frame {int(t * 96) + 1:03d}</text>']
  return svg_doc(w, h, "".join(body), defs)


def svg_frames_to_mp4(frames, name: str, fps=24) -> None:
  tmp = pathlib.Path(tempfile.mkdtemp())
  try:
    for i, svg in enumerate(frames):
      (tmp / f"f{i:04d}.svg").write_text(svg)
    ffmpeg("-framerate", str(fps), "-i", str(tmp / "f%04d.svg"), "-pix_fmt", "yuv420p", "-c:v", "libx264",
           "-preset", "veryfast", "-crf", "26", "-movflags", "+faststart", str(OUT / name))
  finally:
    shutil.rmtree(tmp)


def main() -> None:
  OUT.mkdir(exist_ok=True)
  to_png(write("render.svg", render_scene(960, 540, 0.08)), "render.png")
  write("viewport.svg", viewport())
  to_png(write("photo.svg", photo()), "photo.png")
  write("radar.svg", radar())
  write("mission_map.svg", mission_map())
  write("portrait.svg", portrait())
  write("node_noise.svg", noise_tex())
  write("node_color.svg", colored_noise())
  mats = {
      "mat_red_plastic": dict(color=(0.8, 0.12, 0.1), rough=0.3),
      "mat_gold": dict(color=(0.95, 0.68, 0.22), rough=0.2, metal=True),
      "mat_steel": dict(color=(0.6, 0.62, 0.66), rough=0.35, metal=True),
      "mat_rubber": dict(color=(0.1, 0.1, 0.11), rough=0.95),
      "mat_jade": dict(color=(0.2, 0.62, 0.42), rough=0.15),
      "mat_wood": dict(color=(0.55, 0.33, 0.15), rough=0.7, pattern="wood"),
      "mat_concrete": dict(color=(0.55, 0.55, 0.52), rough=0.9, pattern="noise"),
      "mat_brick": dict(color=(0.6, 0.25, 0.18), rough=0.85, pattern="brick"),
      "mat_emission": dict(color=(0.2, 0.75, 1.0), emissive=True),
      "mat_skin": dict(color=(0.86, 0.6, 0.48), rough=0.5),
      "mat_glass": dict(color=(0.7, 0.85, 0.95), rough=0.05),
      "mat_copper": dict(color=(0.85, 0.42, 0.25), rough=0.3, metal=True),
  }
  for name, kw in mats.items():
    write(f"{name}.svg", material_ball(**kw))
  to_png(OUT / "mat_red_plastic.svg", "material_preview.png")
  for kind in ("tree", "rock", "chair", "lamp", "crate", "suzanne", "hdri"):
    write(f"asset_{kind}.svg", tile_icon(kind))
  # Render preview: orbiting objects, sampling noise clearing over the first second.
  frames = [render_scene(640, 360, i / 96, noise=max(0, 0.35 - i * 0.012)) for i in range(96)]
  (OUT / "render_poster.svg").write_text(frames[0])
  to_png(OUT / "render_poster.svg", "render_poster.png")
  (OUT / "render_poster.svg").unlink()
  svg_frames_to_mp4(frames, "render_preview.mp4")
  balls = [bounce_frame(i / 96) for i in range(96)]
  (OUT / "playblast_poster.svg").write_text(balls[0])
  to_png(OUT / "playblast_poster.svg", "playblast_poster.png")
  (OUT / "playblast_poster.svg").unlink()
  svg_frames_to_mp4(balls, "playblast.mp4")
  print("assets:", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
  main()
