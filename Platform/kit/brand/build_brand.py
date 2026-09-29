"""F-05: one brand kit file -> web style tokens, Power BI theme, deck colours, logo files, preview.

Usage:  python build_brand.py kits/meridian.json            (writes to out/<kit id>/)
        python build_brand.py kits/harbor.json --preview   (also opens nothing; just writes preview.html)
Exit code 1 if the kit is invalid or a mandatory contrast check fails.
"""
import json, os, re, sys, shutil
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = r"C:\Windows\Fonts"
FONT_FILES = {"Segoe UI Semibold": "seguisb.ttf", "Segoe UI": "segoeui.ttf", "Georgia": "georgiab.ttf", "Calibri": "calibrib.ttf", "Arial": "arialbd.ttf"}

REQUIRED_COLORS = ["primary", "secondary", "accent", "positive", "warning", "negative", "background", "surface", "border", "text", "muted"]
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

# ------------------------------------------------------------------ helpers
def hex_to_rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
def rgb_to_hex(c): return "#%02X%02X%02X" % tuple(int(round(x)) for x in c)
def mix(a, b, t): return rgb_to_hex([x + (y - x) * t for x, y in zip(hex_to_rgb(a), hex_to_rgb(b))])
def tint(h, t): return mix(h, "#FFFFFF", t)

def luminance(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = hex_to_rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)

def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

def ink_on(bg):
    """Text colour (white or near-black) that reads best on bg."""
    return "#FFFFFF" if contrast("#FFFFFF", bg) >= contrast("#111111", bg) else "#111111"

def font(name, size):
    f = FONT_FILES.get(name, "arialbd.ttf")
    return ImageFont.truetype(os.path.join(FONT_DIR, f), size)

def wjson(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f: json.dump(obj, f, indent=2)

def wtext(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f: f.write(text)

# ------------------------------------------------------------------ validation
def validate(kit):
    errs = []
    for k in ("name", "palette", "fonts"):
        if k not in kit: errs.append(f"missing '{k}'")
    if errs: return errs
    p = kit["palette"]
    for c in REQUIRED_COLORS:
        if c not in p: errs.append(f"palette.{c} missing")
        elif not HEX.match(p[c]): errs.append(f"palette.{c} is not #RRGGBB: {p[c]}")
    dc = p.get("dataColors", [])
    if len(dc) < 6: errs.append("palette.dataColors needs at least 6 colours")
    for c in dc:
        if not HEX.match(c): errs.append(f"dataColors entry not #RRGGBB: {c}")
    for k in ("heading", "body"):
        if k not in kit["fonts"]: errs.append(f"fonts.{k} missing")
    return errs

def contrast_checks(kit):
    p = kit["palette"]
    pairs = [("text on background", p["text"], p["background"], 4.5, True),
             ("text on surface", p["text"], p["surface"], 4.5, True),
             ("muted text on background", p["muted"], p["background"], 4.5, True),
             ("muted text on surface", p["muted"], p["surface"], 4.5, True),
             (f"white on primary", "#FFFFFF", p["primary"], 4.5, True),
             (f"white on secondary", "#FFFFFF", p["secondary"], 4.5, True),
             ("primary on surface (links, big numbers)", p["primary"], p["surface"], 3.0, True),
             ("positive on surface", p["positive"], p["surface"], 3.0, False),
             ("negative on surface", p["negative"], p["surface"], 3.0, False),
             ("warning on surface", p["warning"], p["surface"], 3.0, False),
             ("accent on secondary (deck accents)", p["accent"], p["secondary"], 3.0, False)]
    out = []
    for name, fg, bg, need, mandatory in pairs:
        r = contrast(fg, bg)
        out.append((name, fg, bg, r, need, r >= need, mandatory))
    return out

# ------------------------------------------------------------------ logo
def make_logo(kit, outdir):
    p = kit["palette"]; prim = p["primary"]; sec = p["secondary"]
    mark = kit.get("logo", {}).get("mark", "bars")
    lp = kit.get("logo", {}).get("path")
    os.makedirs(outdir, exist_ok=True)
    if lp:  # client-supplied logo: copy as-is (a light-on-dark version can be supplied as logoLight)
        ext = os.path.splitext(lp)[1]
        shutil.copy(lp, os.path.join(outdir, "logo" + ext))
        ll = kit.get("logo", {}).get("pathLight")
        if ll: shutil.copy(ll, os.path.join(outdir, "logo-light" + os.path.splitext(ll)[1]))
        return "logo" + ext
    S = 512
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    r = hex_to_rgb(prim)
    if mark == "ring":
        d.ellipse((16, 16, S - 16, S - 16), fill=r)
        d.ellipse((120, 120, S - 120, S - 120), outline=(255, 255, 255), width=44)
        d.ellipse((216, 216, S - 216, S - 216), fill=(255, 255, 255))
        svg_mark = (f'<circle cx="256" cy="256" r="240" fill="{prim}"/><circle cx="256" cy="256" r="136" fill="none" stroke="#FFFFFF" stroke-width="44"/>'
                    f'<circle cx="256" cy="256" r="40" fill="#FFFFFF"/>')
    else:
        d.rounded_rectangle((16, 16, S - 16, S - 16), radius=110, fill=r)
        for i, h in enumerate((150, 230, 320)):
            x0 = 118 + i * 100
            d.rounded_rectangle((x0, S - 108 - h, x0 + 68, S - 108), radius=16, fill=(255, 255, 255))
        svg_mark = f'<rect x="16" y="16" width="480" height="480" rx="110" fill="{prim}"/>' + "".join(
            f'<rect x="{118 + i * 100}" y="{404 - h}" width="68" height="{h}" rx="16" fill="#FFFFFF"/>' for i, h in enumerate((150, 230, 320)))
    img.save(os.path.join(outdir, "logo-mark.png"))
    # wordmark
    name = kit["name"]; f = font(kit["fonts"]["heading"], 170)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(name, font=f)); W = S + 40 + tw + 20
    for fname, col in (("logo-full.png", hex_to_rgb(sec)), ("logo-full-light.png", (255, 255, 255))):
        wm = Image.new("RGBA", (W, S), (0, 0, 0, 0)); wm.paste(img, (0, 0))
        ImageDraw.Draw(wm).text((S + 50, S // 2), name, font=f, fill=col, anchor="lm")
        wm.save(os.path.join(outdir, fname))
    wtext(os.path.join(outdir, "logo-mark.svg"),
          f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="256" height="256">{svg_mark}</svg>\n')
    return "logo-full.png"

def light_logo(outdir, logo_full):
    """Logo to place on dark backgrounds (headers, title slides)."""
    for cand in ("logo-full-light.png", "logo-light.png", "logo-light.svg"):
        if os.path.exists(os.path.join(outdir, cand)): return cand
    return logo_full

# ------------------------------------------------------------------ web tokens
def make_web(kit, out):
    p = kit["palette"]; f = kit["fonts"]; rad = kit.get("shape", {}).get("radius", 12)
    tokens = {
        "primary": p["primary"], "primary-hover": mix(p["primary"], "#000000", 0.12), "primary-soft": tint(p["primary"], 0.9),
        "on-primary": ink_on(p["primary"]), "secondary": p["secondary"], "on-secondary": ink_on(p["secondary"]), "accent": p["accent"],
        "positive": p["positive"], "warning": p["warning"], "negative": p["negative"], "background": p["background"],
        "surface": p["surface"], "border": p["border"], "text": p["text"], "muted": p["muted"]}
    css = ["/* Generated by build_brand.py from the brand kit. Do not edit by hand. */", ":root {"]
    css += [f"  --color-{k}: {v};" for k, v in tokens.items()]
    css += [f"  --data-{i + 1}: {c};" for i, c in enumerate(p["dataColors"])]
    css += [f"  --radius: {rad}px;", f"  --radius-lg: {rad + 4}px;", "  --shadow-card: 0 1px 2px rgba(15,23,42,.06), 0 4px 12px rgba(15,23,42,.06);",
            f"  --font-body: {f['webStack']};", f"  --font-heading: {f['webStack']};", "}", ""]
    wtext(os.path.join(out, "web", "tokens.css"), "\n".join(css))
    wjson(os.path.join(out, "web", "tailwind.brand.json"),
          {"colors": {k: f"var(--color-{k})" for k in tokens}, "borderRadius": {"brand": "var(--radius)", "brand-lg": "var(--radius-lg)"},
           "fontFamily": {"sans": ["var(--font-body)"], "heading": ["var(--font-heading)"]}})
    return tokens

# ------------------------------------------------------------------ Power BI theme
def make_powerbi(kit, out):
    p = kit["palette"]; f = kit["fonts"]; rad = kit.get("shape", {}).get("radius", 12)
    solid = lambda c: {"solid": {"color": c}}
    theme = {
        "name": kit["name"],
        "dataColors": p["dataColors"],
        "background": p["surface"], "foreground": p["text"], "tableAccent": p["primary"],
        "good": p["positive"], "neutral": p["warning"], "bad": p["negative"],
        "maximum": p["primary"], "center": tint(p["primary"], 0.5), "minimum": tint(p["primary"], 0.9),
        "textClasses": {
            "callout": {"fontSize": 28, "fontFace": f["heading"], "color": p["text"]},
            "title": {"fontSize": 13, "fontFace": f["heading"], "color": p["text"]},
            "header": {"fontSize": 12, "fontFace": f["heading"], "color": p["text"]},
            "label": {"fontSize": 10, "fontFace": f["body"], "color": p["muted"]}},
        "visualStyles": {
            "*": {"*": {
                "title": [{"show": True, "fontColor": solid(p["text"]), "fontFamily": f["heading"], "fontSize": 12, "alignment": "left"}],
                "background": [{"show": True, "color": solid(p["surface"]), "transparency": 0}],
                "border": [{"show": True, "color": solid(p["border"]), "radius": rad}],
                "dropShadow": [{"show": False}]}},
            "page": {"*": {"background": [{"color": solid(p["background"]), "transparency": 0}]}}}}
    wjson(os.path.join(out, "powerbi", "theme.json"), theme)
    return theme

def validate_theme(theme):
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed; theme not schema-checked"]
    schema = json.load(open(os.path.join(HERE, "schemas", "reportThemeSchema-2.156.json"), encoding="utf-8"))
    v = jsonschema.Draft7Validator(schema)
    return [f"{'/'.join(map(str, e.path))}: {e.message[:140]}" for e in v.iter_errors(theme)]

# ------------------------------------------------------------------ deck
def make_deck(kit, out, logo_full):
    p = kit["palette"]; f = kit["fonts"]
    deck = {"name": kit["name"], "tagline": kit.get("tagline", ""), "colors": {k: p[k] for k in REQUIRED_COLORS}, "dataColors": p["dataColors"],
            "fonts": {"heading": f["heading"], "body": f["body"]}, "logo": os.path.join("..", logo_full)}
    wjson(os.path.join(out, "deck", "deck_theme.json"), deck)
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.enum.shapes import MSO_SHAPE
    rgb = lambda h: RGBColor.from_string(h.lstrip("#"))
    prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5); blank = prs.slide_layouts[6]
    def tb(s, x, y, w, h, t, size, color, name, bold=False):
        b = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = b.text_frame; tf.word_wrap = True
        r = tf.paragraphs[0].add_run(); r.text = t; r.font.size = Pt(size); r.font.name = name; r.font.bold = bold; r.font.color.rgb = rgb(color); return b
    def fill(s, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE):
        sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h)); sh.fill.solid(); sh.fill.fore_color.rgb = rgb(color); sh.line.fill.background(); return sh
    # slide 1: title
    s = prs.slides.add_slide(blank); fill(s, 0, 0, 13.333, 7.5, p["secondary"]); fill(s, 0, 0, 0.35, 7.5, p["primary"])
    lg = os.path.join(out, light_logo(out, logo_full))
    if os.path.exists(lg):
        try: s.shapes.add_picture(lg, Inches(0.9), Inches(0.7), height=Inches(0.7))
        except Exception: pass
    tb(s, 0.9, 2.6, 11, 1.6, "Quarterly Performance Review", 44, ink_on(p["secondary"]), f["heading"], True)
    tb(s, 0.9, 4.2, 11, 0.8, kit.get("tagline", ""), 20, p["accent"], f["body"])
    tb(s, 0.9, 6.6, 8, 0.4, "Sample slide generated from the brand kit", 12, mix(p["secondary"], "#FFFFFF", 0.6), f["body"])
    # slide 2: KPIs + chart
    s = prs.slides.add_slide(blank); fill(s, 0, 0, 13.333, 7.5, p["background"])
    tb(s, 0.6, 0.4, 9, 0.9, "Sales grew in three of four regions", 30, p["text"], f["heading"], True)
    for i, (n, l, c) in enumerate([("12.4K", "Orders", p["primary"]), ("68%", "On-time delivery", p["positive"]), ("4.2%", "Return rate", p["negative"])]):
        x = 0.6 + i * 4.1
        fill(s, x, 1.6, 3.8, 1.5, p["surface"]); fill(s, x, 1.6, 3.8, 0.08, c)
        tb(s, x + 0.25, 1.85, 3.3, 0.8, n, 36, c, f["heading"], True); tb(s, x + 0.25, 2.6, 3.3, 0.4, l.upper(), 11, p["muted"], f["body"], True)
    cd = CategoryChartData(); cd.categories = ["North", "South", "East", "West"]
    cd.add_series("Q1", (42, 31, 55, 38)); cd.add_series("Q2", (48, 29, 61, 44))
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(3.4), Inches(12.1), Inches(3.6), cd); ch = gf.chart
    ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(12); ch.legend.font.name = f["body"]
    for i, ser in enumerate(ch.plots[0].series):
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = rgb(p["dataColors"][i])
    ch.category_axis.tick_labels.font.size = Pt(12); ch.value_axis.tick_labels.font.size = Pt(12)
    ch.value_axis.major_gridlines.format.line.color.rgb = rgb(p["border"])
    prs.save(os.path.join(out, "deck", "brand_sample.pptx"))
    return deck

# ------------------------------------------------------------------ preview
def make_preview(kit, out, tokens, checks, logo_full):
    p = kit["palette"]
    sw = "".join(f'<div class="sw"><span style="background:{c}"></span><small>{c}</small></div>' for c in p["dataColors"])
    rows = "".join(f'<tr><td>{n}</td><td>{r:.1f}:1</td><td class="{"ok" if ok else "bad"}">{"pass" if ok else "below target"}</td></tr>' for n, fg, bg, r, need, ok, m in checks)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Brand preview: {kit['name']}</title>
<link rel="stylesheet" href="web/tokens.css"><style>
body{{margin:0;font-family:var(--font-body);background:var(--color-background);color:var(--color-text)}}
header{{background:var(--color-secondary);color:var(--color-on-secondary);padding:14px 32px;display:flex;align-items:center;gap:16px}}
header img{{height:40px;background:transparent}} main{{max-width:1080px;margin:32px auto;padding:0 24px;display:grid;gap:24px}}
.card{{background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--radius-lg);box-shadow:var(--shadow-card);padding:24px}}
h1,h2{{font-family:var(--font-heading);margin:0 0 12px}} .btn{{background:var(--color-primary);color:var(--color-on-primary);border:0;border-radius:var(--radius);padding:10px 20px;font-size:15px}}
.btn.alt{{background:var(--color-primary-soft);color:var(--color-primary)}} .row{{display:flex;gap:12px;flex-wrap:wrap;align-items:center}}
.kpi{{flex:1;min-width:180px;border-top:4px solid var(--c);padding:14px 16px;background:var(--color-background);border-radius:var(--radius)}} .kpi b{{font-size:30px;color:var(--c);display:block}}
.sw{{display:inline-block;margin-right:10px;text-align:center}} .sw span{{display:block;width:56px;height:40px;border-radius:var(--radius)}} small{{color:var(--color-muted)}}
table{{border-collapse:collapse;width:100%}} td{{padding:6px 10px;border-bottom:1px solid var(--color-border)}} .ok{{color:var(--color-positive)}} .bad{{color:var(--color-negative)}}
img.deck{{width:100%;border:1px solid var(--color-border);border-radius:var(--radius)}}</style></head><body>
<header><img src="{light_logo(out, logo_full)}" alt="logo"><span style="opacity:.8">{kit.get('tagline','')}</span></header><main>
<div class="card"><h1>Welcome back</h1><p style="color:var(--color-muted)">Your report is ready for review.</p>
<div class="row"><button class="btn">Review draft</button><button class="btn alt">Download log</button></div></div>
<div class="card"><h2>Status</h2><div class="row">
<div class="kpi" style="--c:var(--color-primary)"><b>12.4K</b><small>ORDERS</small></div>
<div class="kpi" style="--c:var(--color-positive)"><b>68%</b><small>ON-TIME</small></div>
<div class="kpi" style="--c:var(--color-negative)"><b>4.2%</b><small>RETURNS</small></div></div></div>
<div class="card"><h2>Chart colours (used by the dashboard and the deck)</h2>{sw}</div>
<div class="card"><h2>Readability checks</h2><table>{rows}</table></div></main></body></html>"""
    wtext(os.path.join(out, "preview.html"), html)

# ------------------------------------------------------------------ main
def main(path, out_root=None):
    """out_root lets the web app build a customer's kit outside the kit folder; report.json in the output folder records the result."""
    kit = json.load(open(path, encoding="utf-8"))
    kid = os.path.splitext(os.path.basename(path))[0]
    errs = validate(kit)
    out = os.path.join(out_root or os.path.join(HERE, "out"), kid)
    if os.path.isdir(out): shutil.rmtree(out)
    if errs:
        print("INVALID KIT:"); [print("  -", e) for e in errs]
        os.makedirs(out); json.dump({"ok": False, "errors": errs}, open(os.path.join(out, "report.json"), "w"), indent=2); return 1
    checks = contrast_checks(kit)
    failed = [c for c in checks if not c[5] and c[6]]
    print(f"Kit: {kit['name']}  ->  {out}")
    for n, fg, bg, r, need, ok, m in checks:
        print(f"  {'PASS' if ok else ('FAIL' if m else 'warn')}  {r:5.1f}:1 (need {need})  {n}")
    logo_full = make_logo(kit, out)
    tokens = make_web(kit, out)
    theme = make_powerbi(kit, out)
    terrs = validate_theme(theme)
    print("  Power BI theme schema errors:", len(terrs)); [print("    ", e) for e in terrs[:8]]
    make_deck(kit, out, logo_full)
    make_preview(kit, out, tokens, checks, logo_full)
    print("  files:", sorted(os.path.relpath(os.path.join(dp, f), out) for dp, _, fs in os.walk(out) for f in fs))
    theme_bad = bool(terrs and "not installed" not in terrs[0])
    json.dump({"ok": not failed and not theme_bad, "name": kit["name"], "logo": logo_full,
               "checks": [{"name": n, "foreground": fg, "background": bg, "ratio": round(r, 2), "needed": need, "pass": ok, "mandatory": m} for n, fg, bg, r, need, ok, m in checks],
               "mandatory_failed": [c[0] for c in failed], "theme_errors": terrs}, open(os.path.join(out, "report.json"), "w"), indent=2)
    if failed: print("MANDATORY CONTRAST CHECKS FAILED:", [c[0] for c in failed]); return 1
    return 1 if theme_bad else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
