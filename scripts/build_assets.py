#!/usr/bin/env python3
"""Generates every SVG card used by the profile README.

Run from the repo root:  python3 scripts/build_assets.py
Edit the CONTENT section below, re-run, commit the assets/ folder.
metrics.svg pulls live numbers from the GitHub API; a daily workflow re-runs this.
"""
import base64
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"

# ── Palette (taken from the profile photo: harbour water, late sun, black) ──
INK = "#07110E"
CARD_TOP = "#10211C"
CARD_BOTTOM = "#0A1613"
SURFACE = "#132822"
STROKE = "#FFFFFF"
TEXT = "#F2F5F1"
MUTED = "#93A89F"
FAINT = "#5E736A"
LEAF = "#3DDC97"
MOSS = "#1F6F4A"
WATER = "#2E6B5E"
SUN = "#E9C46A"
SIGNAL = "#FF6B5E"

SANS = "-apple-system,BlinkMacSystemFont,'SF Pro Display','Inter','Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO = "'SF Mono','JetBrains Mono',ui-monospace,Menlo,Consolas,monospace"

W = 900  # every full-width card shares this width


def esc(s):
    return escape(s, quote=True)


# Helvetica advance widths (per 100 em) for ASCII 32-126.
_GLYPHS = [28, 28, 35, 56, 56, 89, 67, 19, 33, 33, 39, 58, 28, 33, 28, 28, 56, 56, 56, 56, 56, 56, 56, 56,
           56, 56, 28, 28, 58, 58, 58, 56, 102, 67, 67, 72, 72, 67, 61, 78, 72, 28, 50, 67, 56, 83, 72, 78,
           67, 78, 72, 67, 61, 72, 67, 94, 67, 67, 61, 28, 28, 28, 47, 56, 33, 56, 56, 50, 56, 56, 28, 56,
           56, 22, 22, 50, 22, 83, 56, 56, 56, 56, 33, 50, 28, 56, 50, 72, 50, 50, 50, 33, 26, 33, 58]


def text_w(s, size, weight=500):
    """Rendered width estimate; SF/Inter run a little wider than Helvetica, hence the slack."""
    em = sum(_GLYPHS[ord(c) - 32] if 32 <= ord(c) < 127 else 60 for c in s) / 100
    return em * size * (1.1 if weight >= 600 else 1.05)


# ── Shared building blocks ──────────────────────────────────────────────────

STYLE = f"""
<style>
  .sans{{font-family:{SANS}}}
  .mono{{font-family:{MONO}}}
  @keyframes rise{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:none}}}}
  @keyframes drift{{0%,100%{{transform:translate(0,0)}}50%{{transform:translate(-28px,14px)}}}}
  @keyframes drift2{{0%,100%{{transform:translate(0,0)}}50%{{transform:translate(24px,-18px)}}}}
  @keyframes pulse{{0%,100%{{opacity:.35;transform:scale(1)}}50%{{opacity:0;transform:scale(2.4)}}}}
  @keyframes fill{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
  @keyframes marquee{{from{{transform:translateX(0)}}to{{transform:translateX(var(--shift))}}}}
  @keyframes sheen{{0%{{transform:translateX(-400px)}}60%,100%{{transform:translateX(1300px)}}}}
  .rise{{animation:rise .8s cubic-bezier(.2,.7,.2,1) both}}
  .drift{{animation:drift 14s ease-in-out infinite}}
  .drift2{{animation:drift2 18s ease-in-out infinite}}
  .pulse{{transform-box:fill-box;transform-origin:center;animation:pulse 2.2s ease-out infinite}}
  .fill{{transform-box:fill-box;transform-origin:left;animation:fill 1.4s cubic-bezier(.2,.7,.2,1) both}}
  .sheen{{animation:sheen 7s ease-in-out infinite}}
  @media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>"""


def card_defs(uid, w, h, r):
    return f"""
  <linearGradient id="bg{uid}" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{CARD_TOP}"/><stop offset="1" stop-color="{CARD_BOTTOM}"/>
  </linearGradient>
  <linearGradient id="hl{uid}" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{STROKE}" stop-opacity="0"/>
    <stop offset=".5" stop-color="{STROKE}" stop-opacity=".22"/>
    <stop offset="1" stop-color="{STROKE}" stop-opacity="0"/>
  </linearGradient>
  <clipPath id="clip{uid}"><rect x="6" y="6" width="{w - 12}" height="{h - 12}" rx="{r}"/></clipPath>
  <filter id="blur{uid}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="46"/></filter>"""


def card_shell(uid, w, h, r):
    """Background, clip group opener. Caller closes with card_close()."""
    return f"""
<rect x="6" y="6" width="{w - 12}" height="{h - 12}" rx="{r}" fill="url(#bg{uid})"/>
<g clip-path="url(#clip{uid})">"""


def card_close(uid, w, h, r):
    return f"""
</g>
<rect x="6.5" y="6.5" width="{w - 13}" height="{h - 13}" rx="{r - .5}" fill="none" stroke="{STROKE}" stroke-opacity=".08"/>
<rect x="{r + 6}" y="6" width="{w - 2 * r - 12}" height="1" fill="url(#hl{uid})"/>"""


def svg(w, h, label, body, defs=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(label)}">
<title>{esc(label)}</title>
<defs>{defs}
</defs>{STYLE}
{body}
</svg>
"""


def glow(uid, cx, cy, r, color, opacity, cls="drift"):
    return f'<circle class="{cls}" cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity="{opacity}" filter="url(#blur{uid})"/>'


def eyebrow(x, y, num, label):
    return (
        f'<text x="{x}" y="{y}" class="mono" font-size="11.5" font-weight="600" letter-spacing="1.6" fill="{LEAF}">'
        f'{esc(num)}<tspan fill="{FAINT}">  -  </tspan><tspan fill="{MUTED}">{esc(label.upper())}</tspan></text>'
    )


def pill(x, y, label, size=12.5, fg=TEXT, bg=STROKE, bg_op=".06", stroke_op=".08", h=28, dot=None):
    pad = 12
    dot_w = 14 if dot else 0
    w = text_w(label, size) + pad * 2 + dot_w
    out = f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="{h / 2}" fill="{bg}" fill-opacity="{bg_op}" stroke="{STROKE}" stroke-opacity="{stroke_op}"/>'
    if dot:
        out += f'<circle cx="{x + pad + 3}" cy="{y + h / 2}" r="3.5" fill="{dot}"/>'
    out += f'<text x="{x + pad + dot_w}" y="{y + h / 2 + size * .35:.1f}" class="sans" font-size="{size}" font-weight="500" fill="{fg}">{esc(label)}</text>'
    return out, w


def write(name, content):
    (OUT / name).write_text(content)
    print(f"  {name:<22} {len(content.encode()) / 1024:6.1f} KB")


# ── CONTENT ─────────────────────────────────────────────────────────────────

NAME = "Rodrigo Barbosa"
TAGLINE = "A designer who compiles."
META = "Computer Engineering student  ·  Portugal"

HERO_CHIPS = [("Java", "#E76F51"), ("Next.js", TEXT), ("Rust", "#DEA584"), ("UI / UX", LEAF)]

NOTIFICATIONS = [
    ("xiux-ide", "now", "GPU-rendered modal IDE - compiling…", "#DEA584", "R"),
    ("cipheraimg", "2m", "Image encrypted · 0 bytes of metadata leaked", "#3178C6", "C"),
    ("bug #∞", "since 2024", "Created on purpose. Fixed on purpose. 🙏🏻", SIGNAL, "!"),
]

TICKER = ["Java", "Next.js", "TypeScript", "Rust", "Python", "Spring Boot", "MySQL",
          "React", "Hibernate", "Maven", "Assembly", "R", "Git", "Linux", "Figma"]

QUOTE = ["Every interface is a promise.", "The code keeps it -", "the design makes people believe it."]
PRINCIPLES = ["works", "reads well", "looks good doing it"]
NOW = [
    ("🎓", "Studying", "Computer Engineering", MOSS),
    ("⚙️", "Building", "xiux - a native Rust IDE", "#8A5A2B"),
    ("🌱", "Learning", "React · Spring Boot", WATER),
    ("📍", "Based in", "Portugal", "#6B5A2A"),
]

STACK = [
    ("Fluent", 1.0, LEAF, ["Java", "Python", "HTML", "CSS", "Git", "Graphic Design"]),
    ("Building", .66, SUN, ["Next.js", "TypeScript", "MySQL", "Spring Boot", "Hibernate", "Maven", "Rust"]),
    ("Growing", .33, "#7FB8A4", ["React", "Backend architecture", "Assembly", "R"]),
]

PROJECTS = [
    ("xiux-ide", "Rust", "#DEA584",
     ["Native, GPU-rendered, Neovim-inspired IDE.", "No Electron - a real modal editing core."],
     ["GPU", "Vim motions", "Native"]),
    ("cipheraimg", "TypeScript", "#3178C6",
     ["Encrypts images until they look like noise.", "Fully local, offline by design."],
     ["Electron", "Crypto", "Offline"]),
    ("xubz-theme", "VS Code", "#2F80ED",
     ["Premium dark VS Code theme where every", "colour carries meaning. Red = errors only."],
     ["Theme", "Design system"]),
    ("cursed-calculators", "Python", "#3572A5",
     ["One runner for esoteric languages:", "LOLCODE, Rockstar, Shakespeare, Chef."],
     ["Esolangs", "Interpreters"]),
    ("portfolio", "Next.js", TEXT,
     ["My personal corner of the web,", "live at 0xbarbosa.dev."],
     ["TypeScript", "Web"]),
    ("prototipo-coworking", "HTML", "#E34C26",
     ["Validation prototype for a university", "coworking platform (Req. Engineering)."],
     ["Prototype", "UX"]),
]

USER = "barbosaz1"
LANG_COLORS = {
    "Java": "#E76F51", "TypeScript": "#3178C6", "JavaScript": "#F1E05A", "Python": "#3572A5",
    "Rust": "#DEA584", "HTML": "#E34C26", "CSS": "#663399", "Shell": "#89E051",
}

CONTACTS = [
    ("github", "GitHub", "@barbosaz1"),
    ("linkedin", "LinkedIn", "Rodrigo Barbosa"),
    ("mail", "Email", "rb6544758@gmail.com"),
    ("web", "Portfolio", "0xbarbosa.dev"),
]


# ── Cards ───────────────────────────────────────────────────────────────────

def hero():
    w, h, r, uid = W, 380, 28, "h"
    avatar = base64.b64encode((OUT / "avatar.jpg").read_bytes()).decode()
    defs = card_defs(uid, w, h, r) + f"""
  <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{LEAF}"/><stop offset=".55" stop-color="{WATER}"/><stop offset="1" stop-color="{SUN}"/>
  </linearGradient>
  <linearGradient id="tag" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{LEAF}"/><stop offset="1" stop-color="{SUN}"/>
  </linearGradient>
  <linearGradient id="sheenG" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".05"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
  </linearGradient>
  <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#fff" opacity=".07"/></pattern>
  <linearGradient id="fadeR" x1="0" y1="0" x2="1" y2="0"><stop offset=".35" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff"/></linearGradient>
  <mask id="dotMask"><rect width="{w}" height="{h}" fill="url(#fadeR)"/></mask>
  <clipPath id="av"><circle cx="106" cy="122" r="50"/></clipPath>"""

    b = card_shell(uid, w, h, r)
    b += glow(uid, 780, 40, 190, LEAF, .30)
    b += glow(uid, 600, 380, 210, WATER, .55, "drift2")
    b += glow(uid, 900, 260, 130, SUN, .22)
    b += f'<rect width="{w}" height="{h}" fill="url(#dots)" mask="url(#dotMask)"/>'
    b += f'<rect class="sheen" x="0" y="0" width="260" height="{h}" fill="url(#sheenG)" transform="skewX(-18)"/>'

    # window chrome
    b += f'<text x="40" y="44" class="mono" font-size="12" fill="{FAINT}">barbosaz1 <tspan fill="{FAINT}">/</tspan> <tspan fill="{MUTED}">README.md</tspan></text>'
    status = "Open to internships"
    sw = text_w(status, 12) + 40
    sx = w - 40 - sw
    b += f'<rect x="{sx:.1f}" y="26" width="{sw:.1f}" height="26" rx="13" fill="{LEAF}" fill-opacity=".1" stroke="{LEAF}" stroke-opacity=".3"/>'
    b += f'<circle class="pulse" cx="{sx + 15:.1f}" cy="39" r="4" fill="{LEAF}"/><circle cx="{sx + 15:.1f}" cy="39" r="4" fill="{LEAF}"/>'
    b += f'<text x="{sx + 27:.1f}" y="43.2" class="sans" font-size="12" font-weight="500" fill="{LEAF}">{status}</text>'

    # identity
    b += '<g class="rise" style="animation-delay:.05s">'
    b += f'<circle cx="106" cy="122" r="55" fill="none" stroke="url(#ring)" stroke-width="2.5"/>'
    b += f'<image href="data:image/jpeg;base64,{avatar}" x="56" y="72" width="100" height="100" clip-path="url(#av)" preserveAspectRatio="xMidYMid slice"/>'
    b += '</g>'
    b += f'<text class="sans rise" style="animation-delay:.15s" x="52" y="238" font-size="44" font-weight="700" letter-spacing="-1.4" fill="{TEXT}">{NAME}</text>'
    b += f'<text class="sans rise" style="animation-delay:.25s" x="54" y="274" font-size="21" font-weight="600" letter-spacing="-.3" fill="url(#tag)">{TAGLINE}</text>'
    b += f'<text class="sans rise" style="animation-delay:.32s" x="54" y="302" font-size="14" fill="{MUTED}">{esc(META)}</text>'
    x = 54
    b += '<g class="rise" style="animation-delay:.4s">'
    for label, dot in HERO_CHIPS:
        p, pw = pill(x, 320, label, size=12.5, dot=dot)
        b += p
        x += pw + 8
    b += '</g>'

    # notification stack (iOS style)
    nx, ny, nw, nh = 516, 84, 344, 72
    for i, (title, when, body, color, glyph) in enumerate(NOTIFICATIONS):
        y = ny + i * (nh + 12)
        b += f'<g class="rise" style="animation-delay:{.5 + i * .22:.2f}s">'
        b += f'<rect x="{nx}" y="{y}" width="{nw}" height="{nh}" rx="18" fill="#fff" fill-opacity=".055" stroke="#fff" stroke-opacity=".09"/>'
        b += f'<rect x="{nx + 14}" y="{y + 16}" width="40" height="40" rx="10" fill="{color}" fill-opacity=".18" stroke="{color}" stroke-opacity=".45"/>'
        b += f'<text x="{nx + 34}" y="{y + 42}" text-anchor="middle" class="mono" font-size="17" font-weight="700" fill="{color}">{esc(glyph)}</text>'
        b += f'<text x="{nx + 68}" y="{y + 31}" class="sans" font-size="14" font-weight="600" fill="{TEXT}">{esc(title)}</text>'
        b += f'<text x="{nx + nw - 16}" y="{y + 31}" text-anchor="end" class="sans" font-size="11.5" fill="{FAINT}">{esc(when)}</text>'
        b += f'<text x="{nx + 68}" y="{y + 52}" class="sans" font-size="12.5" fill="{MUTED}">{esc(body)}</text>'
        b += '</g>'

    b += card_close(uid, w, h, r)
    write("hero.svg", svg(w, h, f"{NAME} - {TAGLINE} {META}", b, defs))


def ticker():
    w, h, r, uid = W, 64, 26, "t"
    defs = card_defs(uid, w, h, r) + f"""
  <linearGradient id="edgeFade" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#000"/><stop offset=".08" stop-color="#fff"/><stop offset=".92" stop-color="#fff"/><stop offset="1" stop-color="#000"/>
  </linearGradient>
  <mask id="tm"><rect width="{w}" height="{h}" fill="url(#edgeFade)"/></mask>"""
    items, x = "", 0
    for name in TICKER:
        items += f'<text x="{x:.1f}" y="38.5" class="sans" font-size="15" font-weight="500" fill="{TEXT}" fill-opacity=".86">{esc(name)}</text>'
        x += text_w(name, 15) + 32
        items += f'<circle cx="{x - 16:.1f}" cy="33" r="2.5" fill="{LEAF}" opacity=".8"/>'
    span = x
    b = card_shell(uid, w, h, r)
    b += f'<g mask="url(#tm)"><g style="--shift:-{span:.1f}px;animation:marquee 32s linear infinite">'
    b += f'<g transform="translate(30 0)">{items}</g><g transform="translate({30 + span:.1f} 0)">{items}</g>'
    b += '</g></g>'
    b += card_close(uid, w, h, r)
    write("ticker.svg", svg(w, h, "Stack: " + " · ".join(TICKER), b, defs))


def about():
    w, h, r, uid = W, 336, 26, "a"
    defs = card_defs(uid, w, h, r)
    b = card_shell(uid, w, h, r)
    b += glow(uid, 120, 330, 160, MOSS, .5)
    b += eyebrow(40, 50, "01", "About")

    colors = [TEXT, MUTED, MUTED]
    for i, line in enumerate(QUOTE):
        fill = colors[i]
        b += f'<text class="sans rise" style="animation-delay:{.1 + i * .12:.2f}s" x="38" y="{106 + i * 36}" font-size="27" font-weight="650" letter-spacing="-.7" fill="{fill}">{esc(line)}</text>'

    b += f'<text x="40" y="236" class="mono" font-size="12" fill="{FAINT}">// code that</text>'
    x = 40
    for i, p in enumerate(PRINCIPLES):
        label = "✓  " + p
        wdt = text_w(label, 13) + 26
        b += f'<g class="rise" style="animation-delay:{.5 + i * .12:.2f}s">'
        b += f'<rect x="{x}" y="250" width="{wdt:.1f}" height="30" rx="9" fill="{LEAF}" fill-opacity=".08" stroke="{LEAF}" stroke-opacity=".25"/>'
        b += f'<text x="{x + 13}" y="270" class="sans" font-size="13" font-weight="500" fill="{LEAF}">{esc(label)}</text></g>'
        x += wdt + 8
    b += f'<text x="40" y="306" class="mono" font-size="12" fill="{FAINT}">// “it’s done - for now.” always improving, always building</text>'

    # iOS grouped list
    lx, ly, lw, rh = 520, 34, 340, 64
    b += f'<rect x="{lx}" y="{ly}" width="{lw}" height="{rh * len(NOW)}" rx="18" fill="{SURFACE}" stroke="#fff" stroke-opacity=".07"/>'
    for i, (icon, k, v, col) in enumerate(NOW):
        y = ly + i * rh
        b += f'<g class="rise" style="animation-delay:{.3 + i * .1:.2f}s">'
        b += f'<rect x="{lx + 16}" y="{y + 16}" width="32" height="32" rx="8" fill="{col}"/>'
        b += f'<text x="{lx + 32}" y="{y + 37.5}" text-anchor="middle" font-size="16">{icon}</text>'
        b += f'<text x="{lx + 62}" y="{y + 29}" class="sans" font-size="11.5" font-weight="500" fill="{FAINT}">{esc(k)}</text>'
        b += f'<text x="{lx + 62}" y="{y + 47}" class="sans" font-size="14.5" font-weight="600" fill="{TEXT}">{esc(v)}</text>'
        b += f'<path d="M{lx + lw - 24} {y + 27} l5 5 l-5 5" fill="none" stroke="{FAINT}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
        b += '</g>'
        if i < len(NOW) - 1:
            b += f'<rect x="{lx + 62}" y="{y + rh - .5}" width="{lw - 62}" height="1" fill="#fff" opacity=".07"/>'

    b += card_close(uid, w, h, r)
    write("about.svg", svg(w, h, "About - " + " ".join(QUOTE) + " Studying Computer Engineering, building xiux, learning React and Spring Boot, based in Portugal.", b, defs))


def stack():
    w, h, r, uid = W, 330, 26, "s"
    defs = card_defs(uid, w, h, r)
    b = card_shell(uid, w, h, r)
    b += glow(uid, 820, 330, 170, WATER, .45)
    b += eyebrow(40, 50, "02", "Stack")
    b += f'<text x="38" y="86" class="sans" font-size="24" font-weight="650" letter-spacing="-.6" fill="{TEXT}">Toolkit, layered like a design system.</text>'

    cw, gap, cx0, cy = 264, 14, 38, 112
    for i, (title, level, col, items) in enumerate(STACK):
        x = cx0 + i * (cw + gap)
        b += f'<g class="rise" style="animation-delay:{.1 + i * .15:.2f}s">'
        b += f'<rect x="{x}" y="{cy}" width="{cw}" height="184" rx="18" fill="{SURFACE}" stroke="#fff" stroke-opacity=".07"/>'
        b += f'<circle cx="{x + 22}" cy="{cy + 28}" r="4.5" fill="{col}"/>'
        b += f'<text x="{x + 34}" y="{cy + 33}" class="sans" font-size="15" font-weight="650" fill="{TEXT}">{title}</text>'
        b += f'<text x="{x + cw - 18}" y="{cy + 33}" text-anchor="end" class="mono" font-size="11" fill="{FAINT}">{int(level * 100)}%</text>'
        b += f'<rect x="{x + 18}" y="{cy + 46}" width="{cw - 36}" height="4" rx="2" fill="#fff" opacity=".08"/>'
        b += f'<rect class="fill" style="animation-delay:{.4 + i * .2:.2f}s" x="{x + 18}" y="{cy + 46}" width="{(cw - 36) * level:.1f}" height="4" rx="2" fill="{col}"/>'
        px, py = x + 18, cy + 66
        for it in items:
            pw = text_w(it, 12) + 22
            if px + pw > x + cw - 14:
                px, py = x + 18, py + 34
            p, pw = pill(px, py, it, size=12, h=26, fg="#DCE6E1")
            b += p
            px += pw + 6
        b += '</g>'

    b += card_close(uid, w, h, r)
    label = "Stack - " + "; ".join(f"{t}: {', '.join(i)}" for t, _, _, i in STACK)
    write("stack.svg", svg(w, h, label, b, defs))


def header(name, num, label, title, sub):
    w, h, r, uid = W, 112, 26, "x" + num
    defs = card_defs(uid, w, h, r)
    b = card_shell(uid, w, h, r)
    b += glow(uid, 860, 20, 120, LEAF, .22)
    b += eyebrow(40, 46, num, label)
    b += f'<text x="38" y="82" class="sans" font-size="24" font-weight="650" letter-spacing="-.6" fill="{TEXT}">{esc(title)}</text>'
    b += f'<text x="{w - 40}" y="82" text-anchor="end" class="sans" font-size="13.5" fill="{MUTED}">{esc(sub)}</text>'
    b += card_close(uid, w, h, r)
    write(name, svg(w, h, f"{num} · {label} - {title}", b, defs))


def project(i, name, lang, col, desc, tags):
    w, h, r, uid = 450, 214, 22, f"p{i}"
    defs = card_defs(uid, w, h, r)
    b = card_shell(uid, w, h, r)
    b += glow(uid, 430, 10, 110, col, .2)
    b += f'<circle cx="34" cy="40" r="5" fill="{col}"/>'
    b += f'<text x="46" y="44.5" class="sans" font-size="12.5" font-weight="500" fill="{MUTED}">{esc(lang)}</text>'
    b += f'<circle cx="{w - 40}" cy="40" r="15" fill="#fff" fill-opacity=".06" stroke="#fff" stroke-opacity=".1"/>'
    b += f'<path d="M{w - 45} {45} l10 -10 M{w - 42} {35} h7 v7" fill="none" stroke="{TEXT}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
    b += f'<text x="27" y="92" class="sans" font-size="23" font-weight="700" letter-spacing="-.6" fill="{TEXT}">{esc(name)}</text>'
    for j, line in enumerate(desc):
        b += f'<text x="28" y="{120 + j * 20}" class="sans" font-size="13.5" fill="{MUTED}">{esc(line)}</text>'
    x = 28
    for t in tags:
        p, pw = pill(x, 164, t, size=11.5, h=24, fg="#C9D6D0")
        b += p
        x += pw + 6
    b += card_close(uid, w, h, r)
    write(f"project-{name}.svg", svg(w, h, f"{name} ({lang}) - {' '.join(desc)}", b, defs))


ICONS = {
    "github": '<path fill="{c}" d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.2 1.77 1.2 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.41-2.69 5.38-5.26 5.67.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z"/>',
    "linkedin": '<path fill="{c}" d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28ZM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13ZM7.12 20.45H3.56V9h3.56v11.45ZM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0Z"/>',
    "mail": '<rect x="2" y="4.5" width="20" height="15" rx="3" fill="none" stroke="{c}" stroke-width="1.8"/><path d="m3 6.5 9 6.5 9-6.5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linejoin="round"/>',
    "web": '<circle cx="12" cy="12" r="10" fill="none" stroke="{c}" stroke-width="1.8"/><path d="M2 12h20M12 2c3 3.2 3 16.8 0 20M12 2c-3 3.2-3 16.8 0 20" fill="none" stroke="{c}" stroke-width="1.6"/>',
}


def contact(i, key, label, handle):
    w, h, r, uid = 225, 132, 20, f"c{i}"
    defs = card_defs(uid, w, h, r)
    b = card_shell(uid, w, h, r)
    b += glow(uid, 200, 0, 70, LEAF, .18)
    b += f'<rect x="24" y="24" width="38" height="38" rx="11" fill="{LEAF}" fill-opacity=".12" stroke="{LEAF}" stroke-opacity=".3"/>'
    b += f'<g transform="translate(33 33) scale(.83)">{ICONS[key].format(c=LEAF)}</g>'
    b += f'<path d="M{w - 40} 49 l10 -10 M{w - 37} 39 h7 v7" fill="none" stroke="{FAINT}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
    b += f'<text x="24" y="90" class="sans" font-size="15" font-weight="650" fill="{TEXT}">{esc(label)}</text>'
    size = 12.5 if len(handle) < 18 else 11.5
    b += f'<text x="24" y="110" class="sans" font-size="{size}" fill="{MUTED}">{esc(handle)}</text>'
    b += card_close(uid, w, h, r)
    write(f"contact-{key}.svg", svg(w, h, f"{label}: {handle}", b, defs))


def gh(path):
    req = urllib.request.Request(f"https://api.github.com/{path}", headers={"Accept": "application/vnd.github+json"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.load(res)


def metrics():
    try:
        user = gh(f"users/{USER}")
        repos = [r for r in gh(f"users/{USER}/repos?per_page=100") if not r["fork"] and r["name"] != USER]
        langs = {}
        for repo in repos:
            for lang, size in gh(f"repos/{USER}/{repo['name']}/languages").items():
                langs[lang] = langs.get(lang, 0) + size
    except Exception as err:  # offline or rate-limited: keep the last committed card
        print(f"  metrics.svg            skipped ({err})")
        return

    since = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
    days = (datetime.now(timezone.utc) - since).days
    latest = max(repos, key=lambda r: r["pushed_at"])
    tiles = [
        ("Public repos", str(user["public_repos"]), LEAF),
        ("Followers", str(user["followers"]), SUN),
        ("Languages", str(len(langs)), "#7FB8A4"),
        ("Days shipping", f"{days:,}", TEXT),
    ]

    w, h, r, uid = W, 286, 26, "m"
    defs = card_defs(uid, w, h, r) + f"""
  <clipPath id="bar"><rect x="38" y="190" width="{w - 76}" height="10" rx="5"/></clipPath>"""
    b = card_shell(uid, w, h, r)
    b += glow(uid, 100, 0, 150, LEAF, .2)
    tw, gap = 197, 12
    for i, (label, value, col) in enumerate(tiles):
        x = 38 + i * (tw + gap)
        b += f'<g class="rise" style="animation-delay:{.1 + i * .1:.2f}s">'
        b += f'<rect x="{x}" y="34" width="{tw}" height="110" rx="18" fill="{SURFACE}" stroke="#fff" stroke-opacity=".07"/>'
        b += f'<circle cx="{x + 22}" cy="60" r="4" fill="{col}"/>'
        b += f'<text x="{x + 34}" y="64.5" class="sans" font-size="12.5" font-weight="500" fill="{MUTED}">{label}</text>'
        b += f'<text x="{x + 20}" y="118" class="sans" font-size="38" font-weight="700" letter-spacing="-1.2" fill="{TEXT}">{value}</text>'
        b += '</g>'

    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])
    shown, other = top[:6], sum(v for _, v in top[6:])
    if other:
        shown.append(("Other", other))
    b += f'<text x="38" y="178" class="sans" font-size="13" font-weight="600" fill="{TEXT}">Languages by code written</text>'
    b += f'<text x="{w - 38}" y="178" text-anchor="end" class="sans" font-size="12" fill="{FAINT}">last push · {esc(latest["name"])} · {latest["pushed_at"][:10]}</text>'
    b += f'<g clip-path="url(#bar)"><rect x="38" y="190" width="{w - 76}" height="10" fill="#fff" opacity=".06"/>'
    x = 38.0
    for lang, size in shown:
        seg = (w - 76) * size / total
        b += f'<rect class="fill" x="{x:.1f}" y="190" width="{max(seg - 2, 1):.1f}" height="10" fill="{LANG_COLORS.get(lang, FAINT)}"/>'
        x += seg
    b += '</g>'
    x = 38.0
    for lang, size in shown:
        label = f"{lang} {size / total * 100:.1f}%"
        b += f'<circle cx="{x + 4:.1f}" cy="228" r="4" fill="{LANG_COLORS.get(lang, FAINT)}"/>'
        b += f'<text x="{x + 14:.1f}" y="232" class="sans" font-size="12.5" fill="{MUTED}">{esc(lang)} <tspan fill="{FAINT}">{size / total * 100:.1f}%</tspan></text>'
        x += text_w(label, 12.5) + 34
    b += card_close(uid, w, h, r)
    label = f"{user['public_repos']} public repos, {user['followers']} followers, {len(langs)} languages: " + ", ".join(
        f"{l} {v / total * 100:.0f}%" for l, v in shown)
    write("metrics.svg", svg(w, h, label, b, defs))


def footer():
    w, h, r, uid = W, 150, 26, "f"
    defs = card_defs(uid, w, h, r) + f"""
  <linearGradient id="wave" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{LEAF}" stop-opacity="0"/><stop offset=".3" stop-color="{LEAF}"/>
    <stop offset=".7" stop-color="{SUN}"/><stop offset="1" stop-color="{SUN}" stop-opacity="0"/>
  </linearGradient>"""
    b = card_shell(uid, w, h, r)
    b += glow(uid, 450, 170, 220, MOSS, .55)
    b += f'<path d="M60 52 C 240 22, 360 82, 450 52 S 660 22, 840 52" fill="none" stroke="url(#wave)" stroke-width="1.5" opacity=".7"/>'
    b += f'<text x="{w / 2}" y="96" text-anchor="middle" class="sans" font-size="19" font-weight="650" letter-spacing="-.3" fill="{TEXT}">Building bugs on purpose since 2024 <tspan>🙏🏻</tspan></text>'
    b += f'<text x="{w / 2}" y="122" text-anchor="middle" class="mono" font-size="11.5" fill="{FAINT}">designed &amp; compiled by rodrigo barbosa  ·  printed on {CARD_BOTTOM.lower()}  ·  🍃</text>'
    b += card_close(uid, w, h, r)
    write("footer.svg", svg(w, h, "Building bugs on purpose since 2024 - designed and compiled by Rodrigo Barbosa", b, defs))


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    print("Building assets/")
    hero()
    ticker()
    about()
    stack()
    header("h-work.svg", "03", "Selected work", "Things I built to learn by breaking.", "click a card to open the repo  ↗")
    header("h-metrics.svg", "04", "Metrics", "Commits, languages, streaks.", "live from GitHub")
    header("h-contact.svg", "05", "Contact", "Open to internships & good conversations.", "I read everything")
    for i, p in enumerate(PROJECTS):
        project(i, *p)
    for i, c in enumerate(CONTACTS):
        contact(i, *c)
    metrics()
    footer()
