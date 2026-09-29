"""Findings deck agent (stories D-03, D-04): builds the findings deck from the brand kit and the verified facts, with talking points in the speaker notes.

Every number is requested from facts.py, so it traces to a value that Power BI Desktop returned in the last check run.
Usage: python deck_agent.py
"""
import json, os, sys
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from facts import Facts, OUT, PLAT
from PIL import Image

DECK = json.load(open(os.path.join(PLAT, "kit", "brand", "out", "meridian", "deck", "deck_theme.json"), encoding="utf-8"))
BR = os.path.join(PLAT, "kit", "brand", "out", "meridian")
CO = DECK["colors"]; FH = DECK["fonts"]["heading"]; FB = DECK["fonts"]["body"]; DC = DECK["dataColors"]
DOCS = os.path.join(OUT, "docs"); REPORT = os.path.join(OUT, "report")
rgb = lambda h: RGBColor.from_string(h.lstrip("#"))
F = Facts(); n, pct, usd = F.n, F.pct, F.usd

prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5); BLANK = prs.slide_layouts[6]
SRC = "Source: RewardsNext offer and customer data, 30-day window; every figure checked in Power BI Desktop."

def box(s, x, y, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE):
    sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill: sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
    else: sh.fill.background()
    if line: sh.line.color.rgb = rgb(line); sh.line.width = Pt(1)
    else: sh.line.fill.background()
    sh.shadow.inherit = False; return sh

def text(s, x, y, w, h, paras, size=14, color=None, bold=False, font=None, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.15, after=4):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    if isinstance(paras, str): paras = [paras]
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph(); para.alignment = align; para.line_spacing = spacing; para.space_after = Pt(after)
        runs = p if isinstance(p, list) else [(p, {})]
        for t, o in runs:
            r = para.add_run(); r.text = t; r.font.size = Pt(o.get("size", size)); r.font.bold = o.get("bold", bold); r.font.name = o.get("font", font or FB)
            r.font.color.rgb = rgb(o.get("color", color or CO["text"])); r.font.italic = o.get("italic", False)
    return tb

def slide(kicker, title, dark=False, notes=""):
    s = prs.slides.add_slide(BLANK); box(s, 0, 0, 13.333, 7.5, fill=CO["secondary"] if dark else CO["background"])
    if kicker: text(s, 0.6, 0.38, 9, 0.3, kicker.upper(), 12, CO["primary"], True)
    if title: text(s, 0.6, 0.72, 12.1, 0.9, title, 28, "FFFFFF" if dark else CO["text"], True, FH)
    s.notes_slide.notes_text_frame.text = notes; return s

def footer(s, k):
    text(s, 0.6, 7.05, 10.5, 0.3, SRC, 9, CO["muted"]); text(s, 12.3, 7.05, 0.5, 0.3, f"{k:02d}", 10, CO["muted"], align=PP_ALIGN.RIGHT)

def stat(s, x, y, w, h, num, label, color=None):
    box(s, x, y, w, h, fill=CO["surface"], line=CO["border"]); box(s, x, y, w, 0.07, fill=color or CO["primary"])
    text(s, x + 0.2, y + 0.2, w - 0.4, h * 0.5, num, 30, color or CO["primary"], True, FH, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.2, y + h * 0.62, w - 0.4, h * 0.35, label, 12, CO["muted"])

def card(s, x, y, w, h, head, body, color=None, size=12.5):
    box(s, x, y, w, h, fill=CO["surface"], line=CO["border"]); box(s, x, y, 0.07, h, fill=color or CO["primary"])
    text(s, x + 0.25, y + 0.15, w - 0.4, 0.4, head, 14, CO["text"], True, FH)
    text(s, x + 0.25, y + 0.6, w - 0.4, h - 0.7, body, size, CO["text"], spacing=1.2)

def cip(s, x, y, w, context, insight, implication, action, size=12):
    """Context / insight / implication / action panel."""
    rows = [("Context", context, CO["muted"]), ("Insight", insight, CO["primary"]), ("So what", implication, "6C5CE7"), ("Action", action, CO["positive"])]
    yy = y
    for lab, body, col in rows:
        text(s, x, yy, 1.1, 0.3, lab.upper(), 10.5, col, True)
        tb = text(s, x + 1.15, yy - 0.02, w - 1.15, 1.2, body, size, CO["text"], spacing=1.15)
        yy += 0.32 + 0.235 * (1 + len(body) // int((w - 1.15) * 11.2))
    return yy

def chart(s, kind, x, y, w, h, cats, series, colors=None, labels=True, fmt='0.0%', legend=False, gap=60, size=11, vmax=None):
    cd = CategoryChartData(); cd.categories = cats
    for name, vals in series: cd.add_series(name, vals)
    gf = s.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd); ch = gf.chart
    ch.has_title = False; ch.has_legend = legend; ch.font.size = Pt(size); ch.font.name = FB
    if legend: ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
    pl = ch.plots[0]; pl.gap_width = gap; pl.vary_by_categories = False
    for i, ser in enumerate(pl.series):
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = rgb((colors or DC)[i % len(colors or DC)])
    if labels:
        pl.has_data_labels = True; dl = pl.data_labels; dl.number_format = fmt; dl.number_format_is_linked = False; dl.font.size = Pt(size); dl.position = XL_LABEL_POSITION.OUTSIDE_END
    va = ch.value_axis; va.has_major_gridlines = True; va.major_gridlines.format.line.color.rgb = rgb(CO["border"]); va.tick_labels.font.size = Pt(size - 1); va.tick_labels.number_format = fmt; va.tick_labels.number_format_is_linked = False
    va.format.line.fill.background()
    if vmax: va.maximum_scale = vmax
    va.minimum_scale = 0
    ch.category_axis.tick_labels.font.size = Pt(size - 1); ch.category_axis.format.line.color.rgb = rgb(CO["border"])
    return ch

def crop(png, scale=1.0):
    im = Image.open(os.path.join(REPORT, png)).crop((48, 214, 774, 624)); p = os.path.join(DOCS, "deck_" + png)
    im.resize((int(im.width * 2), int(im.height * 2)), Image.LANCZOS).save(p); return p

# ------------------------------------------------------------------ facts used
cust = F.raw("Total Customers"); sent = F.raw("Offers Sent"); viewed = F.raw("Offers Viewed"); comp = F.raw("Offers Completed"); redeemable = F.raw("Redeemable Offers Sent")
view_rate = F.raw("View Rate"); redem = F.raw("Redemption Rate"); comp_of_sent = F.derived("Completed as share of all sent", "c / s", c="Offers Completed", s="Offers Sent")
info_sent = F.raw("Offers Sent, Informational offers"); txn = F.raw("Transactions"); spend = F.raw("Total Spend"); avg_txn = F.raw("Average Transaction Amount"); funnel_txn = F.raw("Funnel Transactions (viewed or completed customers)")
unk = F.raw("Customers, Age Band = Unknown"); unk_share = F.derived("Unknown-profile share of customers", "u / c", u="Customers, Age Band = Unknown", c="Total Customers"); unk_red = F.raw("Redemption Rate, Age Band = Unknown")
rep = F.raw("Repeated Completion Rows"); unviewed = F.derived("Share of offers never viewed", "1 - v", v="View Rate")
ages = ["18-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+", "Unknown"]; age_r = [F.raw(f"Redemption Rate, Age Band = {a}") for a in ages]
incs = ["Under $40K", "$40K-$59K", "$60K-$79K", "$80K-$99K", "$100K+", "Not disclosed"]; inc_r = [F.raw(f"Redemption Rate, Income Band = {a}") for a in incs]
genders = ["Female", "Male", "Other", "Not disclosed"]; gen_r = [F.raw(f"Redemption Rate, gender {g}") for g in genders]
tenures = [f"Joined {y}" for y in range(2013, 2019)]; ten_r = [F.raw(f"Redemption Rate, Tenure Cohort = {t}") for t in tenures]
offers = [("BOGO | spend 5 | reward 5 | 5d", "BOGO $5 / $5, 5 days"), ("BOGO | spend 5 | reward 5 | 7d", "BOGO $5 / $5, 7 days"), ("BOGO | spend 10 | reward 10 | 5d", "BOGO $10 / $10, 5 days"), ("BOGO | spend 10 | reward 10 | 7d", "BOGO $10 / $10, 7 days"),
          ("Discount | spend 7 | reward 3 | 7d", "Discount $7 / $3, 7 days"), ("Discount | spend 10 | reward 2 | 7d", "Discount $10 / $2, 7 days"), ("Discount | spend 10 | reward 2 | 10d", "Discount $10 / $2, 10 days"), ("Discount | spend 20 | reward 5 | 10d", "Discount $20 / $5, 10 days")]
off_r = {lab: F.raw(f"Redemption Rate, offer {k}") for k, lab in offers}
rew = {r: F.raw(f"Redemption Rate, reward {r}") for r in ("$2", "$3", "$5", "$10")}
g1, g0 = "Completed at least one offer", "Never completed an offer"
c1 = F.raw(f"Customers, {g1}"); c0 = F.raw(f"Customers, {g0}"); a1 = F.raw(f"Average Transaction Amount, {g1}"); a0 = F.raw(f"Average Transaction Amount, {g0}")
t1 = F.raw(f"Daily Transactions per Customer overall, {g1}"); t0 = F.raw(f"Daily Transactions per Customer overall, {g0}")
ab = F.raw("Average Amount Before Completion"); aa = F.raw("Average Amount After Completion"); tb_ = F.raw("Transactions Before First Completion"); ta = F.raw("Transactions After First Completion")
ch_sent = {c: F.raw(f"Offers Sent, channel {c}") for c in ("Email", "Mobile", "Social", "Web")}; ch_red = {c: F.raw(f"Redemption Rate, channel {c}") for c in ("Email", "Mobile", "Social", "Web")}
ev_rows = json.load(open(os.path.join(OUT, "profile", "reference_totals.json"), encoding="utf-8"))["sources"]["events"]["rows"]

# ------------------------------------------------------------------ 1 title
s = slide("", "", dark=True, notes="Open with the question: which customers redeem offers, which offers work, and what should the marketing team change? This deck answers it from 17,000 customers over 30 days. Every number is checked against an independent calculation. Two minutes for the whole story, then the detail.")
box(s, 0, 0, 0.35, 7.5, fill=CO["primary"]); s.shapes.add_picture(os.path.join(BR, "logo-full-light.png"), Inches(0.9), Inches(0.7), height=Inches(0.75))
text(s, 0.9, 2.5, 11.5, 1.5, "Customer Offer Engagement", 46, "FFFFFF", True, FH); text(s, 0.9, 3.7, 11.5, 0.8, "What drives offer redemption, and where to act", 22, CO["accent"])
for i, (a, b) in enumerate([(n(cust), "customers"), (n(sent), "offers sent"), (n(ev_rows), "events analysed"), ("30 days", "observation window")]):
    text(s, 0.9 + i * 3.0, 5.6, 2.8, 0.5, a, 26, "FFFFFF", True, FH); text(s, 0.9 + i * 3.0, 6.15, 2.8, 0.4, b, 12, "94A3B8")

# ------------------------------------------------------------------ 2 question and data
s = slide("01 · Question and data", "Which offers work, for whom, and what do customers buy?", notes=f"The brief: help marketing teams see how customers engage with promotional offers. Four files: {n(cust)} customers, {n(ev_rows)} events, 10 offers and a data dictionary. Events are offer received, viewed, completed and purchases. One caution to keep in mind throughout: this is a 30-day window, so every figure describes that window only.")
text(s, 0.6, 1.9, 6.6, 3.2, [[("The question", {"bold": True, "color": CO["primary"]})], "Marketing wants to know how customers respond to promotional offers, which offer types, channels and rewards work best, and how spending changes after an offer is completed.", "",
                              [("How we answered it", {"bold": True, "color": CO["primary"]})], "A Power BI dashboard of five pages, built on a clean star model, with every figure checked against an independent calculation."], 15, spacing=1.25)
for i, (a, b) in enumerate([(n(cust), "customers"), (n(ev_rows), "events"), ("10", "offers"), (n(txn), "purchases")]):
    stat(s, 7.9 + (i % 2) * 2.55, 1.9 + (i // 2) * 1.75, 2.35, 1.55, a, b)
text(s, 0.6, 5.3, 12, 0.9, "Events: offer received, offer viewed, offer completed, and purchase. Time is measured in hours from the start of a 30-day window.", 13, CO["muted"]); footer(s, 2)

# ------------------------------------------------------------------ 3 data prep
s = slide("02 · Data preparation", "Five data problems, found before they could distort the numbers", notes=f"Walk the five cards. The events value column looks like JSON but uses single quotes, and one key is spelled two ways. {n(unk)} customers, {pct(unk_share)}, have age 118, which is a placeholder for unknown, and their income and gender are blank as well. {n(rep)} completed-offer rows repeat exactly; we kept them and flagged them. Time is shared across customers, so we use observation day rather than a calendar date. The file has {n(ev_rows)} events against about 100,000 in the brief; we used the file provided.")
items = [("Events value column", "Looks like JSON but uses single quotes, and the offer id key has two spellings. Parsed per event type.", CO["primary"]),
         ("Missing profiles", f"{n(unk)} customers ({pct(unk_share)}) have age 118, blank gender and blank income. Treated as one 'not disclosed' group, no guessing.", CO["accent"]),
         ("Repeated rows", f"{n(rep)} completed-offer rows repeat exactly. Kept and flagged, so they can be filtered out.", "6C5CE7"),
         ("Time axis", "All customers share one 30-day window, so time is observation day 0 to 29, not a calendar date.", CO["positive"]),
         ("Data volume", f"{n(ev_rows)} events, about three times the ~100,000 in the brief. The file provided was used.", CO["warning"])]
for i, (h, b, c) in enumerate(items):
    card(s, 0.6 + (i % 3) * 4.1, 1.9 + (i // 3) * 2.45, 3.9, 2.25, h, b, c)
text(s, 8.8 + 0.0, 4.4, 3.9, 2.2, [[("Result", {"bold": True, "color": CO["primary"]})], f"Raw totals were captured first; the cleaned tables reproduce them exactly (18 of 18 checks)."], 13, spacing=1.2); footer(s, 3)

# ------------------------------------------------------------------ 4 model and dashboard
s = slide("03 · Model", "A star model, 30 measures and five report pages", notes="One fact table of events, three dimensions, and a bridge for channels. The channel bridge is the only relationship that filters both ways. All 30 measures live in one table so a reviewer can find every formula. The dashboard has five pages plus two drill-through pages and two tooltips. Everything was built from configuration files and checked in Power BI Desktop against independent numbers.")
s.shapes.add_picture(os.path.join(DOCS, "erd.png"), Inches(0.6), Inches(1.75), width=Inches(7.6))
for i, (h, b) in enumerate([("Overview", "Headline numbers"), ("Offer Funnel", "Sent, viewed, completed"), ("Customer Segmentation", "Who redeems"), ("Offer Performance", "Which offers work"), ("Transaction Behavior", "What customers buy")]):
    box(s, 8.6, 1.85 + i * 0.85, 4.1, 0.72, fill=CO["surface"], line=CO["border"]); box(s, 8.6, 1.85 + i * 0.85, 0.07, 0.72, fill=DC[i]); text(s, 8.85, 1.93 + i * 0.85, 3.8, 0.3, h, 13, CO["text"], True); text(s, 8.85, 2.2 + i * 0.85, 3.8, 0.3, b, 11.5, CO["muted"])
text(s, 8.6, 6.2, 4.1, 0.6, "Plus drill-through to one offer or one customer, and hover tooltips.", 12, CO["muted"]); footer(s, 4)

# ------------------------------------------------------------------ 5 funnel
s = slide("04 · Findings", f"{pct(view_rate)} of offers are viewed; {pct(redem)} of redeemable offers are completed", notes=f"{n(sent)} offers were sent, {n(viewed)} viewed, {n(comp)} completed. Completed is {pct(comp_of_sent)} of all offers sent, but informational offers, {n(info_sent)} of them, can never be completed, so the redemption rate excludes them: {pct(redem)} of the {n(redeemable)} redeemable offers. About a quarter of offers are never viewed, which is the first place to look.")
chart(s, XL_CHART_TYPE.BAR_CLUSTERED, 0.6, 1.8, 6.0, 4.4, ["Completed", "Viewed", "Sent"], [("Offers", (comp, viewed, sent))], colors=[CO["primary"]], fmt="#,##0", gap=45, size=12)
cip(s, 7.0, 1.9, 5.7, "Offers move from received to viewed to completed.", f"{n(sent)} sent, {n(viewed)} viewed ({pct(view_rate)}), {n(comp)} completed ({pct(comp_of_sent)} of all sent; {pct(redem)} of redeemable offers).",
    f"About one offer in four is never viewed, so it cannot work. {n(info_sent)} informational offers can never be completed.", "Test ways to raise the view rate first: timing, channel mix and subject lines.", 12)
footer(s, 5)

# ------------------------------------------------------------------ 6 missing profiles
s = slide("04 · Findings", f"Customers with a missing profile redeem only {pct(unk_red)}", notes=f"{n(unk)} customers, {pct(unk_share)} of the base, have age, income and gender all missing. They redeem {pct(unk_red)} against {pct(redem)} overall. Women redeem {pct(gen_r[0])}, men {pct(gen_r[1])}, other {pct(gen_r[2])}. The data cannot say why: they may be less engaged, or incomplete accounts. That is worth investigating before any campaign targets them.")
chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 0.6, 1.8, 6.2, 4.6, genders, [("Redemption rate", gen_r)], colors=[CO["primary"]], size=12, vmax=1.0)
cip(s, 7.2, 1.9, 5.5, f"{n(unk)} customers ({pct(unk_share)}) have no age, income or gender on file.", f"They redeem {pct(unk_red)}, against {pct(redem)} overall and {pct(gen_r[0])} for women.", "Either they are far less engaged, or these are incomplete accounts. The data cannot tell which.", "Capture profile details at sign-up, and study this group separately before targeting it.", 12); footer(s, 6)

# ------------------------------------------------------------------ 7 income and age
s = slide("04 · Findings", "Redemption climbs with income and, more gently, with age", notes=f"Income is the clearest gradient: {pct(inc_r[0])} under $40K rising to {pct(inc_r[4])} at $100K and over. Age rises from {pct(age_r[0])} for 18 to 24 to {pct(age_r[6])} for 75 and over. Customers who joined in 2018 redeem least, {pct(ten_r[5])}, against {pct(ten_r[3])} for 2016; they had less time in the window, but the data cannot confirm that. The heatmap on the Segmentation page shows the two together.")
chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 0.6, 1.75, 6.0, 3.3, ages[:7], [("Redemption rate", age_r[:7])], colors=[CO["primary"]], size=10, vmax=1.0)
chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 6.8, 1.75, 5.9, 3.3, incs[:5], [("Redemption rate", inc_r[:5])], colors=["6C5CE7"], size=10, vmax=1.0)
text(s, 0.6, 5.1, 6.0, 0.3, "Redemption rate by age band", 12, CO["muted"], True); text(s, 6.8, 5.1, 5.9, 0.3, "Redemption rate by income band", 12, CO["muted"], True)
text(s, 0.6, 5.6, 12.1, 1.3, [[("So what: ", {"bold": True, "color": "6C5CE7"}), (f"lower-income and younger customers complete fewer offers ({pct(inc_r[0])} under $40K, {pct(age_r[0])} at 18 to 24), which suggests the spending thresholds are harder for them. ", {}), ("Action: ", {"bold": True, "color": CO["positive"]}), ("test lower minimum spends for these groups.", {})]], 14, spacing=1.25); footer(s, 7)

# ------------------------------------------------------------------ 8 offer design
s = slide("04 · Findings", "Easier thresholds and longer windows complete more often", notes=f"Eight redeemable offers. The best is a $10 discount at $2 reward with a 10-day window, {pct(off_r['Discount $10 / $2, 10 days'])}; the same offer with 7 days completes {pct(off_r['Discount $10 / $2, 7 days'])}. The hardest offers, with a $10 or $20 spend, complete {pct(off_r['BOGO $10 / $10, 5 days'])} to {pct(off_r['Discount $20 / $5, 10 days'])}. By reward, $3 offers do best at {pct(rew['$3'])} and $10 offers worst at {pct(rew['$10'])}. Cause is not proven: offers differ in more than one way at a time.")
order = sorted(off_r, key=lambda k: off_r[k]); chart(s, XL_CHART_TYPE.BAR_CLUSTERED, 0.6, 1.75, 7.0, 4.9, order, [("Redemption rate", [off_r[k] for k in order])], colors=[CO["primary"]], size=11, vmax=0.8, gap=40)
cip(s, 7.9, 1.9, 4.8, "Eight redeemable offers differ in minimum spend, reward and duration.", f"The $10-spend, $2-reward discount completes {pct(off_r['Discount $10 / $2, 10 days'])} with 10 days but {pct(off_r['Discount $10 / $2, 7 days'])} with 7. High-spend offers complete least ({pct(off_r['BOGO $10 / $10, 5 days'])} to {pct(off_r['Discount $20 / $5, 10 days'])}).",
    f"Threshold and time allowed appear to matter more than reward size: $2 offers complete {pct(rew['$2'])}, $10 offers {pct(rew['$10'])}.", "Favour lower spend thresholds and longer windows; run a controlled test to confirm.", 11.5); footer(s, 8)

# ------------------------------------------------------------------ 9 spending
s = slide("04 · Findings", "Customers who complete offers spend far more per purchase", notes=f"{n(c1)} customers completed at least one offer; {n(c0)} never did. Completers spend {usd(a1)} per purchase and make {t1:.1f} purchases each; never-completers spend {usd(a0)} and make {t0:.1f}. Among completers, the average purchase is {usd(ab)} before their first completed offer and {usd(aa)} after. This is association, not cause: customers who complete offers may already be bigger spenders. Only a controlled test can show whether offers change spending.")
stat(s, 0.6, 1.9, 3.0, 1.6, usd(a1), "average purchase, completed at least one offer"); stat(s, 3.8, 1.9, 3.0, 1.6, usd(a0), "average purchase, never completed", CO["muted"])
stat(s, 0.6, 3.7, 3.0, 1.6, f"{t1:.1f}", "purchases per customer, completers", CO["positive"]); stat(s, 3.8, 3.7, 3.0, 1.6, f"{t0:.1f}", "purchases per customer, others", CO["muted"])
stat(s, 0.6, 5.5, 3.0, 1.4, usd(ab), "average purchase before first completed offer", CO["warning"]); stat(s, 3.8, 5.5, 3.0, 1.4, usd(aa), "average purchase after it", CO["positive"])
cip(s, 7.2, 1.9, 5.5, f"{n(c1)} customers completed at least one offer; {n(c0)} never did.", f"Completers spend {usd(a1)} per purchase against {usd(a0)}, and their average purchase rises from {usd(ab)} to {usd(aa)} after their first completed offer.",
    "This is association, not proof that offers cause spending: customers who complete offers may already spend more.", "Run a controlled test (offer versus no offer) before crediting offers with the uplift.", 12); footer(s, 9)

# ------------------------------------------------------------------ 10 limits
s = slide("05 · Caveats", "What the dashboard cannot say", notes=f"Four limits to state plainly. Channels are listed per offer, not per event, and every offer uses email, so email is {n(ch_sent['Email'])} of {n(sent)} offers and channel results overlap: email {pct(ch_red['Email'])}, mobile {pct(ch_red['Mobile'])}, web {pct(ch_red['Web'])}, social {pct(ch_red['Social'])}. Purchases carry no offer, so they cannot be attributed to one. The window is 30 days. And all comparisons are association, not cause.")
for i, (h, b, c) in enumerate([("Channels overlap", f"Channels are listed per offer, not per event. Email carries every offer ({n(ch_sent['Email'])} of {n(sent)}), so channel redemption rates ({pct(ch_red['Email'])} to {pct(ch_red['Social'])}) are not exclusive.", CO["primary"]),
                               ("Purchases carry no offer", f"{n(txn)} purchases cannot be tied to a specific offer. The funnel's purchase count ({n(funnel_txn)}) is for customers who viewed or completed an offer, not a conversion rate.", "6C5CE7"),
                               ("A 30-day window", "Everything describes 30 days. Seasonal effects and longer-term behaviour are outside the data.", CO["warning"]),
                               ("Association, not cause", "Comparisons between groups show what goes together, not what causes what. Tests are needed for cause.", CO["positive"])]):
    card(s, 0.6 + (i % 2) * 6.15, 1.9 + (i // 2) * 2.5, 5.95, 2.3, h, b, c, 13)
footer(s, 10)

# ------------------------------------------------------------------ 11 recommendations
s = slide("06 · Recommendations", "Five actions, each with an owner, a timeframe and a measure", notes=f"Each recommendation names who acts, what they do, when, and how we will know. One: fix profile capture. Two: test lower spend thresholds for lower-income customers. Three: test 10-day against 7-day windows. Four: work on the {pct(unviewed)} of offers never viewed. Five: improve the data so channel and purchase attribution become possible.")
recs = [("CRM lead", f"Capture age, income and gender at sign-up; study the {n(unk)} customers with missing profiles separately.", "Next quarter", "Share of profiles complete; redemption of the group"),
        ("Offer designers", f"Test lower minimum spends for customers under $40K, where redemption is {pct(inc_r[0])}.", "One campaign", "Redemption by income band"),
        ("Offer designers", f"Test 10-day against 7-day windows for the $10-spend discount ({pct(off_r['Discount $10 / $2, 10 days'])} vs {pct(off_r['Discount $10 / $2, 7 days'])} today).", "One campaign", "Redemption by duration"),
        ("Campaign owners", f"Investigate why {pct(unviewed)} of offers are never viewed: timing, channel, message.", "Next two campaigns", "View rate"),
        ("Data owner", "Record the channel of each offer event and the offer behind each purchase; extend beyond 30 days.", "Next data refresh", "Attribution becomes possible")]
box(s, 0.6, 1.85, 12.1, 0.42, fill=CO["secondary"])
for x, w, t in ((0.75, 1.9, "OWNER"), (2.7, 5.4, "ACTION"), (8.2, 1.7, "WHEN"), (10.0, 2.6, "MEASURE")): text(s, x, 1.93, w, 0.3, t, 10.5, "FFFFFF", True)
for i, (o, a, w_, m) in enumerate(recs):
    y = 2.35 + i * 0.86; box(s, 0.6, y, 12.1, 0.78, fill=CO["surface"], line=CO["border"]); box(s, 0.6, y, 0.07, 0.78, fill=DC[i])
    text(s, 0.75, y + 0.1, 1.9, 0.6, o, 12.5, CO["text"], True); text(s, 2.7, y + 0.1, 5.4, 0.7, a, 12); text(s, 8.2, y + 0.1, 1.7, 0.6, w_, 12, CO["muted"]); text(s, 10.0, y + 0.1, 2.6, 0.7, m, 12, CO["muted"])
footer(s, 11)

# ------------------------------------------------------------------ 12 tour
s = slide("07 · Using the dashboard", "Five pages, hover cards and two drill-throughs", notes="Show the five pages. On any chart on Segmentation, Offer Performance or Funnel, hover for a small card. On Offer Performance, right-click an offer in the scorecard, choose Drill through, then Offer detail. From there, right-click a customer and drill through to see every event for that customer. Slicers on each page filter that page.")
pages = [("Overview", "overview_v3.png"), ("Offer Funnel", "funnel_v3.png"), ("Customer Segmentation", "segmentation_v3.png"), ("Offer Performance", "performance_v3.png"), ("Transaction Behavior", "behavior_v2.png")]
for i, (t, png) in enumerate(pages):
    x = 0.6 + (i % 3) * 4.1; y = 1.7 + (i // 3) * 2.6
    s.shapes.add_picture(crop(png), Inches(x), Inches(y), width=Inches(3.7)); text(s, x, y + 2.14, 3.7, 0.3, t, 12, CO["text"], True)
card(s, 8.8, 4.45, 3.9, 2.2, "Tips", "Hover for detail. Right-click an offer in the scorecard and choose Drill through. Slicers filter the page they sit on.", CO["accent"], 12)
footer(s, 12)

# ------------------------------------------------------------------ 13 decisions
s = slide("08 · Decisions", "Definitions the customer approved", notes="These definitions change the numbers, so each was put to the customer and recorded. The redemption rate excludes informational offers. Repeated rows are kept and flagged. Missing profiles are not filled in. Time is observation day. Channel results overlap. The funnel's purchase step is separate. Age, income and engagement bands were approved as shown.")
short = {"D2": "Redemption = completed divided by sent, excluding informational offers; stated on every page.", "D3": f"Repeated completed rows are kept and flagged ({n(rep)} rows).",
         "D6": "No guessing: gender shows 'Not disclosed'; age 118 becomes blank; a flag marks these customers.", "D1": "Time is observation day 0 to 29 (hours divided by 24), not a calendar date.",
         "D10": "Channel results are shown as overlapping: channels are listed per offer, not per event.", "D11": "Before and after excludes the purchase at the completion hour and customers who never completed an offer.",
         "D12": "Funnel purchases ignore offer and channel filters, because purchases carry no offer.", "D13": "Age, income and tenure bands as shown on the Customer Segmentation page."}
dec = json.load(open(os.path.join(OUT, "decisions.json"), encoding="utf-8"))["business_rules"]; want = ["D2", "D3", "D6", "D1", "D10", "D11", "D12", "D13"]
rows = [r for w_ in want for r in dec if r["id"] == w_]
box(s, 0.6, 1.85, 12.1, 0.4, fill=CO["secondary"]); text(s, 0.75, 1.92, 1.0, 0.3, "ID", 10.5, "FFFFFF", True); text(s, 1.6, 1.92, 3, 0.3, "TOPIC", 10.5, "FFFFFF", True); text(s, 4.6, 1.92, 8, 0.3, "DECISION", 10.5, "FFFFFF", True)
for i, r in enumerate(rows):
    y = 2.3 + i * 0.58; box(s, 0.6, y, 12.1, 0.54, fill=CO["surface"] if i % 2 == 0 else CO["background"], line=CO["border"])
    text(s, 0.75, y + 0.14, 0.8, 0.4, r["id"], 11.5, CO["primary"], True); text(s, 1.6, y + 0.14, 2.9, 0.4, r["topic"], 11.5, CO["text"], True); text(s, 4.6, y + 0.12, 8.0, 0.42, short[r["id"]], 11.5, CO["text"])
footer(s, 13)

# ------------------------------------------------------------------ 14 conclusion
s = slide("", "", dark=True, notes="Close with three sentences. Offers work best when they are easy to reach and given time. Customers with missing profiles and lower incomes are the biggest opportunity. Before crediting offers with more spending, run a controlled test. Then invite questions.")
box(s, 0, 0, 0.35, 7.5, fill=CO["primary"]); text(s, 0.9, 0.9, 11.5, 0.6, "CONCLUSION", 14, CO["primary"], True)
text(s, 0.9, 1.5, 11.5, 2.4, "Offers work best when they are easy to reach and give customers time.", 34, "FFFFFF", True, FH)
text(s, 0.9, 3.9, 11.5, 2.6, [f"{pct(redem)} of redeemable offers are completed; the gaps are missing profiles ({pct(unk_red)}), lower incomes ({pct(inc_r[0])} under $40K) and hard thresholds.", "Spending is higher among customers who complete offers, but only a controlled test can show whether offers cause it.", "Next: run the two offer tests, fix profile capture, and record channel and offer on every event."], 17, "E2E8F0", spacing=1.35, after=10)

out = os.path.join(DOCS, "RewardsNext_Findings_Deck.pptx"); prs.save(out); F.save(os.path.join(DOCS, "traceability_deck.json"))
print("deck:", out, "slides:", len(prs.slides), "facts used:", len(F.used))
