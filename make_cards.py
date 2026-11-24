#!/usr/bin/env python3
"""Globalissimo card maker.

Reads the country table (CSV) and writes print-ready card sheets:
  cards.html  - open in a browser to look at the cards
  cards.pdf   - made automatically if Edge or Chrome is installed

Front: flag and country name.  Back: board number and capital in the middle,
the twelve category values around them like the hours of a clock.
Card size 63 x 88 mm (landscape); fronts and backs are on separate sheets.

Usage:
  python make_cards.py globalissimo_cards_data.csv
  python make_cards.py globalissimo_cards_data.csv --lang de
  python make_cards.py globalissimo_cards_data.csv --only DEU,JPN,FRA
  python make_cards.py --download-flags        (once; needs internet)
"""
import argparse, csv, html, math, os, pathlib, re, shutil, subprocess, urllib.request

# ----------------------------------------------------------------------------
# SETTINGS
# ----------------------------------------------------------------------------
CARD_MM = (88, 63)      # width, height in mm: a standard 63 x 88 mm card, landscape
PAGE_MM = (210, 297)    # A4 portrait
MIN_MARGIN_MM = 8       # unprintable border of the printer
DUPLEX_FLIP = "none"    # "none": fronts and backs are separate slips (sleeve method);
                        # "long" or "short": mirror the backs for double-sided printing
FLAG_DIR = "flags"      # folder with one SVG per country, named by ISO2 code: de.svg

# The twelve categories, clockwise, starting at 12 o'clock.
#   column : column name in the CSV
#   icon   : one of the names in ICONS further down
#   fmt    : "big"  1,464 M / 83.5 M / 554,000    "int"  2,962
#            "dec1" 81.4    "dec2" 4.59           "raw"  as written in the CSV
#   en/de  : label on the card; "|" starts a second line (keep lines short)
CATEGORIES = [
    dict(column="population",          icon="people",   fmt="big",  en="Population",               de="Einwohner"),
    dict(column="area_km2",            icon="area",     fmt="big",  en="Area in km²",              de="Fläche in km²"),
    dict(column="fertility_rate",      icon="baby",     fmt="dec2", en="Fertility rate|births per woman", de="Geburtenrate|Kinder pro Frau"),
    dict(column="physicians_per_1000", icon="cross",    fmt="dec2", en="Physicians|per 1,000",     de="Ärzte pro|1.000 Einw."),
    dict(column="pop_density_per_km2", icon="density",  fmt="raw",  en="People|per km²",           de="Einwohner|pro km²"),
    dict(column="gdp_per_capita_usd",  icon="coin",     fmt="int",  en="GDP per capita|in US$",    de="BIP pro Kopf|in US-$"),
    dict(column="tourist_arrivals",    icon="suitcase", fmt="big",  en="Tourists per year",        de="Touristen pro Jahr"),
    dict(column="paved_road_km",       icon="road",     fmt="big",  en="Paved roads in km",        de="Asphaltierte Straßen in km"),
    dict(column="mobile_subs_per_100", icon="phone",    fmt="int",  en="Mobile phones|per 100",    de="Mobiltelefone|pro 100 Einw."),
    dict(column="prisoners_per_100k",  icon="bars",     fmt="int",  en="Prisoners|per 100,000",    de="Gefangene pro|100.000 Einw."),
    dict(column="co2_t_per_capita",    icon="cloud",    fmt="dec2", en="CO₂ per capita|in tonnes", de="CO₂ pro Kopf|in Tonnen"),
    dict(column="highest_point_m",     icon="mountain", fmt="int",  en="Highest point|in m",       de="Höchster Punkt|in m"),
]

# CSV columns for names and capitals.  Without "capital_de" the English capitals are used.
TEXT_COLUMNS = {
    "en": dict(name="name_en", capital="capital"),
    "de": dict(name="name_de", capital="capital_de"),
}
NO_DATA = "–"

# Colors and type
INK = "#18284a"        # deep atlas blue: frame, dial, numbers
MUTED = "#5d6b82"      # labels
HAIR = "#c3ccd9"       # hairlines
ACCENT = "#a8322d"     # atlas red: board number ring
PAPER = "#ffffff"
FONT = "'Palatino Linotype', 'Book Antiqua', Palatino, 'TeX Gyre Pagella', 'URW Palladio L', P052, Georgia, serif"

# ----------------------------------------------------------------------------
# Icons: drawn in a box from -2.2 to +2.2 mm around the origin
# ----------------------------------------------------------------------------
S = 'fill="none" stroke="{ink}" stroke-width="0.32" stroke-linecap="round" stroke-linejoin="round"'
ICONS = {
    "people":   '<circle cx="0" cy="-0.95" r="0.8" {s}/><path d="M-1.7,1.75 a1.7,1.7 0 0 1 3.4,0" {s}/>',
    "area":     '<rect x="-1.55" y="-1.55" width="3.1" height="3.1" {s}/><path d="M-0.8,0.8 L0.8,-0.8 M0.15,-0.8 H0.8 V-0.15 M-0.15,0.8 H-0.8 V0.15" {s}/>',
    "density":  '<rect x="-1.6" y="-1.6" width="3.2" height="3.2" {s}/><g fill="{ink}"><circle cx="-0.75" cy="-0.75" r="0.3"/><circle cx="0.75" cy="-0.75" r="0.3"/><circle cx="0" cy="0" r="0.3"/><circle cx="-0.75" cy="0.75" r="0.3"/><circle cx="0.75" cy="0.75" r="0.3"/></g>',
    "baby":     '<circle cx="0" cy="0.25" r="1.55" {s}/><path d="M-0.3,-1.3 q0.45,-0.75 0.95,-0.15 M-0.5,0.8 q0.5,0.45 1,0" {s}/><g fill="{ink}"><circle cx="-0.55" cy="0.1" r="0.2"/><circle cx="0.55" cy="0.1" r="0.2"/></g>',
    "cross":    '<path d="M-0.6,-1.7 H0.6 V-0.6 H1.7 V0.6 H0.6 V1.7 H-0.6 V0.6 H-1.7 V-0.6 H-0.6 Z" {s}/>',
    "coin":     '<circle cx="0" cy="0" r="1.75" {s}/><text x="0" y="0.85" text-anchor="middle" font-size="2.5" font-weight="bold" fill="{ink}">$</text>',
    "suitcase": '<rect x="-1.75" y="-0.75" width="3.5" height="2.5" rx="0.35" {s}/><path d="M-0.7,-0.75 V-1.55 H0.7 V-0.75 M-1.75,0.35 H1.75" {s}/>',
    "road":     '<path d="M-1.75,1.75 L-0.55,-1.75 M1.75,1.75 L0.55,-1.75" {s}/><path d="M0,1.6 V-1.6" {s} stroke-dasharray="0.55 0.6"/>',
    "phone":    '<rect x="-1.05" y="-1.8" width="2.1" height="3.6" rx="0.4" {s}/><path d="M-0.35,1.15 H0.35" {s}/>',
    "cloud":    '<path d="M-1.45,1.15 H1.35 A0.95,0.95 0 0 0 1.45,-0.75 A1.35,1.35 0 0 0 -1.1,-1.05 A1.1,1.1 0 0 0 -1.45,1.15 Z" {s}/>',
    "bars":     '<rect x="-1.6" y="-1.6" width="3.2" height="3.2" rx="0.25" {s}/><path d="M-0.8,-1.6 V1.6 M0,-1.6 V1.6 M0.8,-1.6 V1.6" {s}/>',
    "mountain": '<path d="M-1.95,1.45 L-0.45,-1.4 L0.45,0.15 L0.95,-0.55 L1.95,1.45 Z" {s}/>',
}

ISO2 = dict(pair.split(":") for pair in (
    "DZA:dz AGO:ao BEN:bj BWA:bw BFA:bf BDI:bi CPV:cv CMR:cm CAF:cf TCD:td COM:km COG:cg COD:cd CIV:ci DJI:dj EGY:eg GNQ:gq "
    "ERI:er SWZ:sz ETH:et GAB:ga GMB:gm GHA:gh GIN:gn GNB:gw KEN:ke LSO:ls LBR:lr LBY:ly MDG:mg MWI:mw MLI:ml MRT:mr MUS:mu "
    "MAR:ma MOZ:mz NAM:na NER:ne NGA:ng RWA:rw STP:st SEN:sn SYC:sc SLE:sl SOM:so ZAF:za SSD:ss SDN:sd TZA:tz TGO:tg TUN:tn "
    "UGA:ug ZMB:zm ZWE:zw AFG:af ARM:am AZE:az BHR:bh BGD:bd BTN:bt BRN:bn KHM:kh CHN:cn CYP:cy GEO:ge IND:in IDN:id IRN:ir "
    "IRQ:iq ISR:il JPN:jp JOR:jo KAZ:kz KWT:kw KGZ:kg LAO:la LBN:lb MYS:my MDV:mv MNG:mn MMR:mm NPL:np PRK:kp OMN:om PAK:pk "
    "PHL:ph QAT:qa SAU:sa SGP:sg KOR:kr LKA:lk SYR:sy TJK:tj THA:th TLS:tl TUR:tr TKM:tm ARE:ae UZB:uz VNM:vn YEM:ye PSE:ps "
    "TWN:tw ALB:al AND:ad AUT:at BLR:by BEL:be BIH:ba BGR:bg HRV:hr CZE:cz DNK:dk EST:ee FIN:fi FRA:fr DEU:de GRC:gr HUN:hu "
    "ISL:is IRL:ie ITA:it LVA:lv LIE:li LTU:lt LUX:lu MLT:mt MDA:md MCO:mc MNE:me NLD:nl MKD:mk NOR:no POL:pl PRT:pt ROU:ro "
    "RUS:ru SMR:sm SRB:rs SVK:sk SVN:si ESP:es SWE:se CHE:ch UKR:ua GBR:gb VAT:va XKX:xk ATG:ag BHS:bs BRB:bb BLZ:bz CAN:ca "
    "CRI:cr CUB:cu DMA:dm DOM:do SLV:sv GRD:gd GTM:gt HTI:ht HND:hn JAM:jm MEX:mx NIC:ni PAN:pa KNA:kn LCA:lc VCT:vc TTO:tt "
    "USA:us ARG:ar BOL:bo BRA:br CHL:cl COL:co ECU:ec GUY:gy PRY:py PER:pe SUR:sr URY:uy VEN:ve AUS:au FJI:fj KIR:ki MHL:mh "
    "FSM:fm NRU:nr NZL:nz PLW:pw PNG:pg WSM:ws SLB:sb TON:to TUV:tv VUT:vu").split())

HERE = os.path.dirname(os.path.abspath(__file__))
DW, DH = 88.0, 63.0   # the card is drawn in a box of 88 x 63 units and then scaled to CARD_MM


# ----------------------------------------------------------------------------
# Number formatting
# ----------------------------------------------------------------------------
def format_value(raw, fmt, lang):
    raw = (raw or "").strip()
    if raw == "":
        return NO_DATA
    v = float(raw)
    unit = ""
    if fmt == "big" and v >= 1e6:
        decimals = 0 if v >= 1e9 else 1 if v >= 1e7 else 2
        out, unit = f"{v / 1e6:,.{decimals}f}", " Mio." if lang == "de" else " M"
    elif fmt == "big":
        out = f"{v:,.0f}" if v >= 100 or v == int(v) else f"{v:,.1f}"
    elif fmt == "int":  out = f"{v:,.0f}"
    elif fmt == "dec1": out = f"{v:,.1f}"
    elif fmt == "dec2": out = f"{v:,.2f}"
    else:               # "raw": keep the decimals written in the CSV
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        out = f"{v:,.{decimals}f}"
    if lang == "de":    # 1,234.5 -> 1.234,5
        out = out.replace(",", "#").replace(".", ",").replace("#", ".")
    return out.replace("-", "\u2212") + unit


# ----------------------------------------------------------------------------
# Small SVG helpers (all lengths in mm)
# ----------------------------------------------------------------------------
def text(x, y, s, size, anchor="middle", weight="normal", style="normal", fill=INK):
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" '
            f'font-style="{style}" fill="{fill}">{html.escape(str(s))}</text>')


def wrap(s, max_chars):
    """Split a name into at most two lines, as evenly as possible."""
    if len(s) <= max_chars or " " not in s:
        return [s]
    best = min((abs(len(s[:i]) - len(s[i + 1:])), i) for i, ch in enumerate(s) if ch == " ")[1]
    return [s[:best], s[best + 1:]]


def frame():
    return (f'<rect x="0" y="0" width="{DW}" height="{DH}" fill="{PAPER}"/>'
            f'<rect x="2.6" y="2.6" width="{DW - 5.2}" height="{DH - 5.2}" rx="2.3" fill="none" stroke="{INK}" stroke-width="0.4"/>'
            f'<rect x="3.5" y="3.5" width="{DW - 7}" height="{DH - 7}" rx="1.55" fill="none" stroke="{INK}" stroke-width="0.13"/>')


def flag_ratio(path):
    """Width/height ratio of a flag SVG, read from its viewBox or width/height."""
    head = open(path, encoding="utf-8", errors="ignore").read(2000)
    m = re.search(r'viewBox="\s*[-\d.]+[ ,]+[-\d.]+[ ,]+([\d.]+)[ ,]+([\d.]+)', head)
    if m:
        return float(m.group(1)) / float(m.group(2))
    return float(re.search(r'\bwidth="([\d.]+)', head).group(1)) / float(re.search(r'\bheight="([\d.]+)', head).group(1))


# ----------------------------------------------------------------------------
# The two card faces
# ----------------------------------------------------------------------------
def card_front(row, flag_href_base):
    out = [frame()]
    # flag, fitted into a box of 52 x 32; a dashed placeholder if the file is missing
    box_w, box_h, cx, cy = 52.0, 32.0, DW / 2, 24.5
    iso2 = ISO2.get(row["iso3"], row["iso3"].lower())
    path = os.path.join(HERE, FLAG_DIR, iso2 + ".svg")
    if os.path.exists(path):
        ratio = flag_ratio(path)
        w = min(box_w, box_h * ratio); h = w / ratio
        x, y = cx - w / 2, cy - h / 2
        out.append(f'<image href="{html.escape(flag_href_base + "/" + iso2 + ".svg")}" x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" preserveAspectRatio="none"/>')
        if iso2 != "np":   # Nepal's flag is not a rectangle
            out.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="none" stroke="{HAIR}" stroke-width="0.2"/>')
    else:
        w, h = 48.0, 32.0
        out.append(f'<rect x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" fill="none" stroke="{HAIR}" stroke-width="0.3" stroke-dasharray="1.2 1"/>')
        out.append(text(cx, cy + 1.2, f"{FLAG_DIR}/{iso2}.svg", 3.2, fill=MUTED, style="italic"))
    # country name, one or two lines
    lines = wrap(row["_name"], 26)
    longest = max(len(l) for l in lines)
    size = 6.6 if longest <= 14 else 6.0 if longest <= 18 else 5.4 if longest <= 22 else 4.8
    base = 52.3 if len(lines) == 1 else 49.3
    for i, line in enumerate(lines):
        out.append(text(cx, base + i * size * 1.16, line, size, weight="bold"))
    return "".join(out)


def card_back(row, lang):
    cx, cy = DW / 2, DH / 2
    R = 16.6                      # radius of the circle the icons sit on
    out = [frame(), f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{HAIR}" stroke-width="0.25"/>']
    vs, ls, lh = 3.3, 1.95, 2.15    # value size, label size, label line height
    for k, cat in enumerate(CATEGORIES):
        a = 2 * math.pi * k / len(CATEGORIES)
        sx, sy = math.sin(a), -math.cos(a)
        x, y = cx + R * sx, cy + R * sy
        out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.3" fill="{PAPER}" stroke="{INK}" stroke-width="0.3"/>')
        icon = ICONS[cat["icon"]].format(s=S.format(ink=INK), ink=INK)
        out.append(f'<g transform="translate({x:.2f},{y:.2f}) scale(0.97)">{icon}</g>')
        value = format_value(row[cat["column"]], cat["fmt"], lang)
        label = cat[lang].split("|")
        one_line = " ".join(label)
        if abs(sx) < 0.01 and sy < 0:      # 12 o'clock: text above the icon
            out.append(text(x, y - 4.5, value, vs, weight="bold"))
            out.append(text(x, y - 8.0, one_line, ls, fill=MUTED))
        elif abs(sx) < 0.01:               # 6 o'clock: text below the icon
            out.append(text(x, y + 6.9, value, vs, weight="bold"))
            out.append(text(x, y + 9.7, one_line, ls, fill=MUTED))
        else:
            anchor = "start" if sx > 0 else "end"
            tx = x + (4.5 if sx > 0 else -4.5)
            if abs(sx) < 0.6 and sy < 0:   # 1 and 11 o'clock: one-line label above the value
                out.append(text(tx, y - 1.0, value, vs, anchor=anchor, weight="bold"))
                out.append(text(tx, y - 4.6, one_line, ls, anchor=anchor, fill=MUTED))
            elif abs(sx) < 0.6:            # 5 and 7 o'clock: one-line label below the value
                out.append(text(tx, y + 3.3, value, vs, anchor=anchor, weight="bold"))
                out.append(text(tx, y + 6.0, one_line, ls, anchor=anchor, fill=MUTED))
            elif sy < -0.3:                # 2 and 10 o'clock: label above the value
                out.append(text(tx, y + 1.3, value, vs, anchor=anchor, weight="bold"))
                for i, line in enumerate(reversed(label)):
                    out.append(text(tx, y - 2.4 - i * lh, line, ls, anchor=anchor, fill=MUTED))
            elif sy > 0.3:                 # 4 and 8 o'clock: label below the value
                out.append(text(tx, y + 1.3, value, vs, anchor=anchor, weight="bold"))
                for i, line in enumerate(label):
                    out.append(text(tx, y + 4.0 + i * lh, line, ls, anchor=anchor, fill=MUTED))
            else:                          # 3 and 9 o'clock
                out.append(text(tx, y - 0.2, value, vs, anchor=anchor, weight="bold"))
                for i, line in enumerate(label):
                    out.append(text(tx, y + 2.5 + i * lh, line, ls, anchor=anchor, fill=MUTED))
    # hub: board number and capital
    out.append(f'<circle cx="{cx}" cy="{cy}" r="10.7" fill="{INK}"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="9.9" fill="none" stroke="{ACCENT}" stroke-width="0.4"/>')
    number = row["board_number"].strip()
    cap = wrap(row["_capital"], 13)
    longest = max(len(l) for l in cap)
    size = 2.55 if longest <= 11 else 2.15 if longest <= 14 else 1.8
    shift = 0 if len(cap) == 1 else -1.1
    out.append(text(cx, cy + 1.2 + shift, number, 8.8 if len(number) < 3 else 7.8, weight="bold", fill=PAPER))
    for i, line in enumerate(cap):
        out.append(text(cx, cy + 5.2 + shift + i * size * 1.18, line, size, style="italic", fill=PAPER))
    return "".join(out)


# ----------------------------------------------------------------------------
# Sheets and HTML page
# ----------------------------------------------------------------------------
def sheets(rows, lang, flag_href_base):
    pw, ph = PAGE_MM
    cw, ch = CARD_MM
    scale = min(cw / DW, ch / DH)
    ox, oy = (cw - DW * scale) / 2, (ch - DH * scale) / 2
    cols = int((pw - 2 * MIN_MARGIN_MM) // cw)
    per_col = int((ph - 2 * MIN_MARGIN_MM) // ch)
    per_sheet = cols * per_col
    x0, y0 = (pw - cols * cw) / 2, (ph - per_col * ch) / 2

    marks = []      # crop marks around the grid of cards
    for i in range(cols + 1):
        x = x0 + i * cw
        marks.append(f'<path d="M{x},{y0 - 6} V{y0 - 1.5} M{x},{y0 + per_col * ch + 1.5} V{y0 + per_col * ch + 6}"/>')
    for j in range(per_col + 1):
        y = y0 + j * ch
        marks.append(f'<path d="M{x0 - 6},{y} H{x0 - 1.5} M{x0 + cols * cw + 1.5},{y} H{x0 + cols * cw + 6}"/>')
    crop_marks = f'<g stroke="#000" stroke-width="0.15" fill="none">{"".join(marks)}</g>'

    def sheet(cards, mirror):
        parts = [f'<svg class="sheet" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {pw} {ph}" width="{pw}mm" height="{ph}mm" font-family="{FONT}">']
        for idx, body in enumerate(cards):
            col, r = idx % cols, idx // cols
            if mirror and DUPLEX_FLIP == "long":
                col = cols - 1 - col
            if mirror and DUPLEX_FLIP == "short":
                r = per_col - 1 - r
            parts.append(f'<g transform="translate({x0 + col * cw + ox},{y0 + r * ch + oy}) scale({scale})">{body}</g>')
        return "".join(parts) + crop_marks + "</svg>"

    pages = []
    for i in range(0, len(rows), per_sheet):
        chunk = rows[i:i + per_sheet]
        pages.append(sheet([card_front(r, flag_href_base) for r in chunk], mirror=False))
        pages.append(sheet([card_back(r, lang) for r in chunk], mirror=True))
    return pages


def build_html(pages):
    pw, ph = PAGE_MM
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>Globalissimo cards</title><style>"
            f"@page{{size:{pw}mm {ph}mm;margin:0}}html,body{{margin:0;padding:0;background:#fff}}"
            ".sheet{display:block;page-break-after:always;break-after:page}"
            "@media screen{body{background:#8d96a3}.sheet{margin:6mm auto;background:#fff;box-shadow:0 1mm 4mm rgba(0,0,0,.35)}}"
            "</style></head><body>" + "".join(pages) + "</body></html>")


# ----------------------------------------------------------------------------
# Data, flags, PDF
# ----------------------------------------------------------------------------
def load(csv_path, lang, only):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    cols = TEXT_COLUMNS[lang]
    for r in rows:
        r["_name"] = r[cols["name"]].strip()
        r["_capital"] = (r.get(cols["capital"]) or r["capital"]).strip()
    rows.sort(key=lambda r: int(r["board_number"]))
    if only:
        wanted = {c.strip().upper() for c in only.split(",")}
        rows = [r for r in rows if r["iso3"] in wanted]
    return rows


def download_flags():
    """Fetch missing flag SVGs from flagcdn.com (flags from Flagpedia, public domain)."""
    os.makedirs(os.path.join(HERE, FLAG_DIR), exist_ok=True)
    for iso2 in sorted(ISO2.values()):
        dest = os.path.join(HERE, FLAG_DIR, iso2 + ".svg")
        if not os.path.exists(dest):
            req = urllib.request.Request(f"https://flagcdn.com/{iso2}.svg", headers={"User-Agent": "globalissimo-card-maker"})
            with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as out:
                out.write(resp.read())


def find_browser():
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        # Windows browsers seen from WSL (Linux inside Windows)
        "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        "/mnt/c/Program Files/Microsoft/Edge/Application/msedge.exe",
        "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
        "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    ]
    found = [c for c in candidates if os.path.exists(c)]
    found += [shutil.which(n) for n in ("msedge", "google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(n)]
    return found[0]


def make_pdf(html_path, pdf_path):
    browser = find_browser()
    html_file, pdf = os.path.abspath(html_path), os.path.abspath(pdf_path)
    if browser.startswith("/mnt/"):     # Windows browser from WSL: needs Windows paths
        html_file, pdf = (subprocess.run(["wslpath", "-w", p], capture_output=True, text=True).stdout.strip()
                          for p in (html_file, pdf))
        url = "file:" + html_file.replace("\\", "/")     # \\wsl.localhost\... -> file://wsl.localhost/...
    else:
        url = pathlib.Path(html_file).as_uri()
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", url],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)


def main():
    ap = argparse.ArgumentParser(description="Make Globalissimo cards from the country CSV.")
    ap.add_argument("csv", nargs="?", help="the country table, e.g. globalissimo_cards_data.csv")
    ap.add_argument("--lang", choices=sorted(TEXT_COLUMNS), default="en", help="language of names, labels and number format")
    ap.add_argument("--only", help="comma-separated ISO3 codes, to make just a few cards")
    ap.add_argument("--out", default="cards", help="name of the output files, without extension")
    ap.add_argument("--no-pdf", action="store_true", help="write only the HTML file")
    ap.add_argument("--download-flags", action="store_true", help="fetch the flag images into the flags folder")
    args = ap.parse_args()

    try:
        if args.download_flags:
            download_flags()
            print("Flags downloaded ->", FLAG_DIR)
            if not args.csv:
                return
        rows = load(args.csv, args.lang, args.only)
        html_path = args.out + ".html"
        flag_base = os.path.relpath(os.path.join(HERE, FLAG_DIR), os.path.dirname(os.path.abspath(html_path))).replace("\\", "/")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(build_html(sheets(rows, args.lang, flag_base)))
        print(f"{len(rows)} cards written ->", html_path)
    except Exception:
        print("Error")
        return

    if not args.no_pdf:
        try:
            make_pdf(html_path, args.out + ".pdf")
            print("PDF written ->", args.out + ".pdf")
        except Exception:
            print("PDF step failed")


if __name__ == "__main__":
    main()
