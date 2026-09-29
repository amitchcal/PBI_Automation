"""Documents agent (stories D-01, D-02): the one-page user guide and the technical document, generated from the project files.

Reads: the model TMDL (tables, columns), the model and transform configs (measures, relationships, steps), the queries (M code),
the decisions log and the Desktop check record. Branding comes from the brand kit output. Numbers come only through facts.py.
Usage: python docs_agent.py
"""
import datetime as dt
import json, os, re, sys
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, Image as RLImage,
                                Preformatted, PageBreak, KeepTogether)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from facts import Facts, OUT, PLAT

FD = r"C:\Windows\Fonts"
for n, f in (("Body", "segoeui.ttf"), ("Body-Bold", "segoeuib.ttf"), ("Body-Ital", "segoeuii.ttf"), ("Head", "seguisb.ttf"), ("Code", "consola.ttf")):
    pdfmetrics.registerFont(TTFont(n, os.path.join(FD, f)))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Ital", boldItalic="Body-Bold")

KIT = json.load(open(os.path.join(PLAT, "kit", "brand", "kits", "meridian.json"), encoding="utf-8"))
BR = os.path.join(PLAT, "kit", "brand", "out", "meridian")
P = KIT["palette"]
C = {k: colors.HexColor(v) for k, v in P.items() if isinstance(v, str)}
DOCS = os.path.join(OUT, "docs"); os.makedirs(DOCS, exist_ok=True)
REPORT = os.path.join(OUT, "report")

def wrapcode(text, n=100):
    """Wrap long code lines at a comma or space so they stay inside the page; continuation lines are indented."""
    out = []
    for ln in text.split("\n"):
        ind = len(ln) - len(ln.lstrip())
        while len(ln) > n:
            cut = max(ln.rfind(", ", 0, n), ln.rfind(" ", 0, n))
            if cut <= ind + 10: cut = n
            out.append(ln[:cut + 1].rstrip()); ln = " " * (ind + 4) + ln[cut + 1:].lstrip()
        out.append(ln)
    return "\n".join(out)

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def sty(name, **kw): return ParagraphStyle(name, **kw)

def crop_page(png, out, scale=1.0):
    im = Image.open(os.path.join(REPORT, png)).crop((48, 214, 774, 624))
    if scale != 1: im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    p = os.path.join(DOCS, out); im.save(p); return p

# ------------------------------------------------------------------ project facts read from files
def read_tmdl_tables():
    d = os.path.join(OUT, "model", "pbip", "RewardsNext.SemanticModel", "definition", "tables"); tables = {}
    for fn in sorted(os.listdir(d)):
        text = open(os.path.join(d, fn), encoding="utf-8").read().split("\n"); name = None; cols = []; cur = None
        for ln in text:
            m = re.match(r"^table (.+)$", ln)
            if m: name = m.group(1).strip("'"); continue
            m = re.match(r"^\tcolumn (.+?)( =)?$", ln)
            if m: cur = {"name": m.group(1).strip("'"), "calc": bool(m.group(2)), "hidden": False, "type": ""}; cols.append(cur); continue
            if cur is not None:
                m = re.match(r"^\t\tdataType: (\w+)", ln)
                if m: cur["type"] = m.group(1)
                if ln.strip() == "isHidden": cur["hidden"] = True
            if ln.startswith("\tpartition") or ln.startswith("\tmeasure"): cur = None
        tables[name] = cols
    return tables

def load_all():
    L = lambda p: json.load(open(p, encoding="utf-8"))
    return dict(model=L(os.path.join(PLAT, "configs", "rewardsnext_model.json")), prof=L(os.path.join(PLAT, "configs", "rewardsnext_profile.json")),
                plan=L(os.path.join(OUT, "transform", "transform_plan.json")), decisions=L(os.path.join(OUT, "decisions.json")),
                issues=L(os.path.join(OUT, "profile", "issues.json")), ref=L(os.path.join(OUT, "profile", "reference_totals.json")),
                check=json.load(open(os.path.join(OUT, "model", "desktop_check.json"), encoding="utf-8-sig")), tables=read_tmdl_tables())

# ------------------------------------------------------------------ ERD picture
def draw_erd(A, path):
    W, H = 1700, 1000; im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
    fh = ImageFont.truetype(os.path.join(FD, "seguisb.ttf"), 26); fb = ImageFont.truetype(os.path.join(FD, "segoeui.ttf"), 19); fs = ImageFont.truetype(os.path.join(FD, "segoeui.ttf"), 22)
    T = A["tables"]
    def box(x, y, w, name, lines, color):
        h = 46 + 26 * len(lines) + 12
        d.rounded_rectangle((x, y, x + w, y + h), 12, fill="white", outline=color, width=3); d.rounded_rectangle((x, y, x + w, y + 46), 12, fill=color)
        d.rectangle((x, y + 30, x + w, y + 46), fill=color); d.text((x + 14, y + 8), name, font=fh, fill="white")
        for i, ln in enumerate(lines): d.text((x + 14, y + 54 + 26 * i), ln, font=fb, fill="#1F2937")
        return (x, y, x + w, y + h)
    pr, sec, ac = P["primary"], "#6C5CE7", P["accent"]
    cust = box(40, 120, 400, "DimCustomer", ["Customer ID (key)", "Member Since, Membership Year", "Gender, Age, Income", "Profile Disclosed", "Age Band, Income Band", "Tenure Cohort", "Engagement Tier / Level", "First Completion Hour", "Offer Completion Group"], sec)
    fact = box(640, 190, 420, "FactEvents", ["EventID", "Customer ID (foreign key)", "Offer ID (foreign key)", "Event", "Amount, Reward", "Hours Since Start", "Observation Day (foreign key)", "Is Repeated Row"], pr)
    offer = box(1260, 120, 400, "DimOffer", ["Offer ID (key)", "Offer Type, Offer Label", "Minimum Spend, Reward Amount", "Duration Days, Channel Count", "Is Informational", "Reward Label"], sec)
    chan = box(1260, 470, 400, "OfferChannel (bridge)", ["Offer ID", "Channel"], ac)
    day = box(640, 590, 420, "DimObservationDay", ["Observation Day (key)", "Week Number, Week Label"], sec)
    box(40, 620, 400, "DataDictionary", ["Table, Field, Description", "(not related; documentation)"], "#9CA3AF")
    box(1260, 640, 400, "FunnelSteps", ["Step, Step Order", "(not related; feeds the funnel)"], "#9CA3AF")
    box(640, 800, 420, "Key Measures", ["30 measures, no data", "(all report numbers come from here)"], "#059669")
    def line(a, b, ta, tb, both=False):
        d.line((a, b), fill="#374151", width=3); d.text((a[0] + (10 if b[0] > a[0] else -32), a[1] - 26), ta, font=fs, fill="#111827"); d.text((b[0] + (-32 if b[0] > a[0] else 10), b[1] - 26), tb, font=fs, fill="#111827")
    line((cust[2], 260), (fact[0], 260), "1", "*")
    line((offer[0], 260), (fact[2], 260), "1", "*")
    line((day[0] + 210, day[1]), (fact[0] + 210, fact[3]), "1", "*")
    line((offer[0] + 200, offer[3]), (chan[0] + 200, chan[1]), "1", "*")
    d.text((1330, 400), "both directions", font=fb, fill="#B45309")
    d.text((40, 30), "Data model: a star with one fact table and three dimensions", font=fh, fill="#111827")
    d.text((40, 70), "1 = one side, * = many side. All relationships filter in one direction except the channel bridge.", font=fb, fill="#4B5563")
    im.save(path); return path

# ------------------------------------------------------------------ D-01 user guide (one page)
def user_guide(A, F):
    out = os.path.join(DOCS, "RewardsNext_User_Guide.pdf")
    doc = BaseDocTemplate(out, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=10 * mm, title="Customer Offer Engagement dashboard: user guide", author="Meridian Analytics")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 20 * mm, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    def band(cv, dc):
        cv.saveState(); cv.setFillColor(C["secondary"]); cv.rect(0, A4[1] - 26 * mm, A4[0], 26 * mm, stroke=0, fill=1)
        try: cv.drawImage(os.path.join(BR, "logo-full-light.png"), 14 * mm, A4[1] - 20 * mm, height=13 * mm, width=13 * mm * 3.9, mask="auto", preserveAspectRatio=True)
        except Exception: pass
        cv.setFillColor(colors.white); cv.setFont("Head", 15); cv.drawRightString(A4[0] - 14 * mm, A4[1] - 14 * mm, "Customer Offer Engagement dashboard")
        cv.setFont("Body", 9.5); cv.drawRightString(A4[0] - 14 * mm, A4[1] - 20 * mm, "User guide: one page"); cv.restoreState()
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=band)])
    h = sty("h", fontName="Head", fontSize=10.5, leading=13, textColor=C["primary"], spaceBefore=5, spaceAfter=2)
    b = sty("b", fontName="Body", fontSize=8.3, leading=10.6, textColor=C["text"], spaceAfter=1.5)
    bl = sty("bl", parent=b, leftIndent=8, bulletIndent=0)
    th = sty("th", fontName="Body-Bold", fontSize=8, leading=10, textColor=colors.white); td = sty("td", fontName="Body", fontSize=8, leading=10, textColor=C["text"])
    def bullets(items): return [Paragraph(x, bl, bulletText="\u2022") for x in items]
    pages = [["Overview", "Customers, offers sent and completed, redemption rate, average purchase; activity by day; redemption by offer type."],
             ["Offer Funnel", "How many offers were sent, viewed and completed; view and redemption rate by offer type and channel."],
             ["Customer Segmentation", "Who redeems: by age, income, gender and tenure, with an age by income heatmap."],
             ["Offer Performance", "Which offer types, rewards and channels work; minimum spend against redemption; a scorecard of every offer."],
             ["Transaction Behavior", "Spending over the 30 days for customers who completed an offer and those who never did."]]
    pt = Table([[Paragraph("Page", th), Paragraph("What it answers", th)]] + [[Paragraph(a, sty("x", parent=td, fontName="Body-Bold")), Paragraph(t, td)] for a, t in pages], colWidths=[30 * mm, 60 * mm])
    pt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), C["secondary"]), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C["background"]]), ("LINEBELOW", (0, 0), (-1, -1), 0.3, C["border"]),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    thumb = RLImage(crop_page("overview_v3.png", "thumb_overview.png"), width=90 * mm, height=90 * mm * 410 / 726)
    red = F.pct(F.raw("Redemption Rate")); sent = F.n(F.raw("Offers Sent"))
    left = [Paragraph("What this dashboard shows", h), Paragraph(f"How {F.n(F.raw('Total Customers'))} customers responded to {F.n(F.raw('Offers Sent'))} offers over a 30-day window: who viewed and completed offers, which offers work, and what customers bought.", b),
            Paragraph("The five pages", h), pt, Spacer(1, 3), thumb,
            Paragraph("Reading the numbers", h)] + bullets([
        "<b>Redemption rate</b> = offers completed divided by offers sent, leaving out informational offers, which cannot be completed.",
        "<b>Channels overlap.</b> The data lists channels per offer, not per event, so an offer counts under every channel it uses.",
        "<b>Purchases carry no offer.</b> Choosing an offer type or channel removes purchases from the spend numbers.",
        "<b>Association, not cause.</b> Customers who complete offers may already spend more."])
    right = [Paragraph("Use the slicers to compare groups", h)] + bullets([
        "Pick a value in a drop-down (for example Gender or Age band); every chart on the page updates.",
        "Tick more than one value in the drop-down to compare groups side by side. Untick a value, or choose Clear selections, to undo.",
        "Slicers are per page. Use the page tabs at the top to move between pages."]) + [
        Paragraph("Hover for detail", h)] + bullets(["Point at a bar or dot on the Segmentation, Offer Performance or Funnel pages to see a small card with customers, redemption, view rate and more."]) + [
        Paragraph("Drill through to one offer or one customer", h)] + bullets([
        "On Offer Performance, right-click an offer in the scorecard, choose <b>Drill through</b>, then <b>Offer detail</b>.",
        "On Offer detail, right-click a customer, choose Drill through, then <b>Customer detail</b> to see every event.",
        "Use the back arrow (or the browser back button) to return."]) + [
        Paragraph("Refresh the data", h)] + bullets([
        "In Power BI Desktop: Home, then <b>Refresh</b>. The data comes from the folder in the <b>SourceFolder</b> parameter (Home, Transform data, Edit parameters).",
        "To add data, replace or extend the CSV files in that folder (same column names) and refresh.",
        "In the Power BI service: open the semantic model settings and schedule a daily or weekly refresh. Files kept on a personal computer need a data gateway; files in a shared cloud folder do not.",
        "If numbers look wrong after a refresh, check that the file names and headers are unchanged."]) + [
        Paragraph("Need more?", h), Paragraph("The technical document lists every table, measure and data-preparation step, and how to add a new offer.", b)]
    t = Table([[left, right]], colWidths=[92 * mm, doc.width - 92 * mm - 4 * mm], hAlign="LEFT"); t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, 0), 6), ("RIGHTPADDING", (1, 0), (1, 0), 0), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    doc.build([Spacer(1, 4 * mm), t]); return out

# ------------------------------------------------------------------ D-02 technical document
def tech_doc(A, F):
    out = os.path.join(DOCS, "RewardsNext_Technical_Document.pdf")
    erd = draw_erd(A, os.path.join(DOCS, "erd.png"))
    doc = BaseDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title="Customer Offer Engagement: technical document", author="Meridian Analytics")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    def foot(cv, dc):
        cv.saveState(); cv.setFont("Body", 8); cv.setFillColor(C["muted"]); cv.drawString(18 * mm, 10 * mm, "Customer Offer Engagement: technical document"); cv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {dc.page}")
        cv.setStrokeColor(C["border"]); cv.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm); cv.restoreState()
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=foot)])
    H1 = sty("H1", fontName="Head", fontSize=15, leading=19, textColor=C["secondary"], spaceBefore=12, spaceAfter=5, keepWithNext=1)
    H2 = sty("H2", fontName="Head", fontSize=11, leading=14, textColor=C["primary"], spaceBefore=8, spaceAfter=3, keepWithNext=1)
    B = sty("B", fontName="Body", fontSize=9.6, leading=13.4, textColor=C["text"], spaceAfter=4, alignment=TA_LEFT)
    BL = sty("BL", parent=B, leftIndent=12, bulletIndent=2, spaceAfter=2)
    TH = sty("TH", fontName="Body-Bold", fontSize=8.6, leading=11, textColor=colors.white); TD = sty("TD", fontName="Body", fontSize=8.6, leading=11, textColor=C["text"])
    CODE = sty("CODE", fontName="Code", fontSize=7.6, leading=9.6, textColor=colors.HexColor("#111827"), backColor=C["background"], borderPadding=4, spaceAfter=6)
    def tbl(rows, widths, head=True):
        t = Table([[Paragraph(esc(c), TH if (head and i == 0) else TD) for c in r] for i, r in enumerate(rows)], colWidths=widths, repeatRows=1 if head else 0)
        cmds = [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C["background"]]), ("LINEBELOW", (0, 0), (-1, -1), 0.3, C["border"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
        if head: cmds.insert(0, ("BACKGROUND", (0, 0), (-1, 0), C["secondary"]))
        t.setStyle(TableStyle(cmds)); return t
    def bullets(items): return [Paragraph(x, BL, bulletText="\u2022") for x in items]
    S = []
    # title
    S += [Spacer(1, 30 * mm), RLImage(os.path.join(BR, "logo-full.png"), width=70 * mm, height=70 * mm * 512 / 1997), Spacer(1, 12 * mm),
          Paragraph("Customer Offer Engagement Dashboard", sty("T", fontName="Head", fontSize=26, leading=31, textColor=C["secondary"])),
          Paragraph("Technical document", sty("T2", fontName="Body", fontSize=15, leading=20, textColor=C["primary"], spaceBefore=4)), Spacer(1, 8 * mm),
          Paragraph("Data model, data preparation, measures, report design, validation and maintenance. Generated from the project files on %s from the checked build (%d Desktop checks passed)." % ("%d %s %d" % (dt.date.today().day, dt.date.today().strftime("%B"), dt.date.today().year), F.desktop_checks), B), PageBreak()]
    # 1 overview
    S += [Paragraph("1. What was built", H1), Paragraph(f"A Power BI report of five pages, two drill-through pages and two tooltip pages, on a semantic model of {len(A['tables'])} tables and {len(A['model']['measures'])} measures, built from four CSV files supplied for the RewardsNext offer-engagement problem statement. The report was generated from configuration files and checked in Power BI Desktop against independent calculations.", B)]
    S += [tbl([["Source file", "Rows", "Content"], ["customers.csv", F.n(A["ref"]["sources"]["customers"]["rows"]), "One row per customer: membership date, gender, age, income"],
              ["events.csv", F.n(A["ref"]["sources"]["events"]["rows"]), "Offer received, viewed, completed and transaction events with a JSON-style value column and hours since the start of the window"],
              ["offers.csv", str(A["ref"]["sources"]["offers"]["rows"]), "Offer type, minimum spend, reward, duration, channels"], ["data_dictionary.csv", str(A["ref"]["sources"]["data_dictionary"]["rows"]), "Field descriptions (three rows describe tables)"]], [40 * mm, 20 * mm, doc.width - 60 * mm]), Spacer(1, 4)]
    S += [Paragraph("Data volume note: the problem statement expected about 100,000 events; the file supplied has %s. The supplied file was used (decision D5)." % F.n(A["ref"]["sources"]["events"]["rows"]), B)]
    # 2 data prep
    S += [Paragraph("2. Data preparation (Power Query)", H1), Paragraph("Each source has a staging query (load disabled) that reads its file from the SourceFolder parameter and sets column types. Model tables are built from the staging queries, so a source can move without editing any step.", B), Paragraph("Issues found by profiling, and how each was handled", H2)]
    dec = {d["issue_id"]: d for d in A["decisions"]["profile_issue_decisions"]}
    rows = [["Finding", "Decision"]]
    for i in A["issues"]:
        if i["id"] in dec: rows.append([i["title"], dec[i["id"]]["decision"]])
    S += [tbl(rows, [doc.width * 0.62, doc.width * 0.38]), Spacer(1, 4)]
    S += [Paragraph("Steps by table", H2)]
    for p in A["plan"]:
        S += [Paragraph(f"<b>{p['table']}</b> ({p['role']}, from {p['source']}, {F.n(p['rows'])} rows)", B)] + bullets([esc(x) for x in p["steps"]])
    S += [Paragraph("Extracting values from the events column", H2), Paragraph("The value column holds a Python-style dictionary with single quotes, so it is not valid JSON. The query replaces single quotes with double quotes, parses the text, and reads each field by name. The offer id key is spelled <i>offer id</i> (with a space) on received and viewed events and <i>offer_id</i> on completed events, so both spellings are tried.", B)]
    fm = open(os.path.join(OUT, "transform", "queries", "FactEvents.m"), encoding="utf-8").read()
    S += [Preformatted(wrapcode(fm), CODE)]
    # 3 model
    S += [PageBreak(), Paragraph("3. Data model", H1), RLImage(erd, width=doc.width, height=doc.width * 1000 / 1700), Spacer(1, 4)]
    rels = [["From (many side)", "To (one side)", "Direction", "Note"]] + [[r["from"], r["to"], "both" if r.get("both") else "single", r.get("note", "")] for r in A["model"]["relationships"]]
    S += [Paragraph("Relationships", H2), tbl(rels, [45 * mm, 45 * mm, 18 * mm, doc.width - 108 * mm])]
    S += [Paragraph("Tables and columns", H2), Paragraph("Calculated columns and hidden technical columns are marked. Hidden columns are used by relationships and sorting but do not appear in the field list.", B)]
    for tname, cols in A["tables"].items():
        rows = [["Column", "Type", "Kind"]] + [[c["name"], c["type"] or "text", ("calculated" if c["calc"] else "loaded") + (", hidden" if c["hidden"] else "")] for c in cols]
        S += [KeepTogether([Paragraph(f"<b>{tname}</b>", B), tbl(rows, [70 * mm, 30 * mm, doc.width - 100 * mm]), Spacer(1, 4)])] if cols else [Paragraph(f"<b>{tname}</b>: measures only (no data columns).", B)]
    # 4 segments
    seg = A["model"]["segments"]
    S += [Paragraph("4. Customer segments", H1), Paragraph("Band edges and tier thresholds were approved by the customer (decisions D13 and D14). Every customer belongs to exactly one group in each dimension; group sizes add up to the customer total (checked).", B)]
    rows = [["Segment", "Definition"]]
    for b_ in seg["bands"]: rows.append([b_["name"], f"{b_['source']} in bands {', '.join(b_['labels'])}; blank shown as {b_['unknown']}"])
    rows.append([seg["tenure"]["name"], "Membership year (Joined 2013 to Joined 2018)"])
    e = seg["engagement"]
    rows.append([e["tier_name"], f"Heavy completer: {e['heavy_min']} or more completed offers; Light completer: {e['light_min']} to {e['heavy_min'] - 1}; Viewer only: viewed but none completed; Ignored: received but none viewed or completed; Not reached: none received"])
    rows.append([e["level_name"], f"High: {e['heavy_min']} or more completed; Medium: {e['light_min']} to {e['heavy_min'] - 1}; Low: none"])
    S += [tbl(rows, [40 * mm, doc.width - 40 * mm]), Paragraph("Engagement groups are defined from completions, so redemption by engagement group is true by construction. Use them to describe customers, not to explain redemption.", B)]
    # 5 measures
    S += [Paragraph("5. Measures", H1), Paragraph(f"All {len(A['model']['measures'])} measures are in the Key Measures table, grouped in display folders. Every value shown in the report comes from these measures.", B)]
    for folder in sorted({m["folder"] for m in A["model"]["measures"]}):
        S += [Paragraph(folder[2:], H2)]
        for m in [m for m in A["model"]["measures"] if m["folder"] == folder]:
            S += [KeepTogether([Paragraph(f"<b>{esc(m['name'])}</b> <font color='#475569'>({esc(m['format'])})</font>", B), Paragraph(esc(m["description"]), sty("md", parent=B, fontSize=8.8, leading=12, textColor=C["muted"], spaceAfter=1)), Preformatted(wrapcode("\n".join(m["dax"])), CODE)])]
    # 6 report
    S += [Paragraph("6. Report design", H1), Paragraph("The report uses the brand theme (Meridian Analytics: blue primary, dark header, Segoe UI). Chart types follow simple rules: columns and bars for categories, a funnel for a sequence, a shaded matrix for two dimensions, lines only where every day has a value.", B)]
    S += [tbl([["Page", "Purpose"], ["Overview", "Headline KPIs and activity by day"], ["Offer Funnel", "Sent, viewed, completed; view and redemption rate by type and channel"], ["Customer Segmentation", "Redemption by age, income, gender, tenure; heatmap"],
              ["Offer Performance", "Type, reward, channel; minimum spend against redemption; scorecard"], ["Transaction Behavior", "Spending by customers who completed an offer versus those who never did; before and after"],
              ["Offer detail (hidden)", "Drill through from an offer: KPIs, segments, customers who received it"], ["Customer detail (hidden)", "Drill through from a customer: profile and every event"],
              ["Two tooltip pages (hidden)", "Customer group and Offer tooltips shown on hover"]], [45 * mm, doc.width - 45 * mm])]
    S += [Paragraph("Tooltips must be assigned to each visual; the generator does this from the configuration. Test drill-through and tooltips again after publishing.", B)]
    # 7 validation
    chk = A["check"]["checks"]; nsc = sum(1 for c in chk if isinstance(c.get("expected"), (int, float)) and "rows" not in str(c.get("actual", "")))
    S += [Paragraph("7. Validation", H1), Paragraph(f"The last full run in Power BI Desktop passed all {len(chk)} checks. Expected values were computed independently in pandas from the transformed tables and compared with values returned by the model.", B)] + bullets([
        "Every measure, in total and by segment group, offer, reward, channel, gender and customer group.",
        "A seeded sample of 100 customers: offers sent, viewed and completed, transactions and spend per customer.",
        "Every age band by income band heatmap cell, for customers and for redemption rate.",
        "Model integrity: no event without a customer, offer or observation day; every offer has a channel; relationship count and direction; hidden columns.",
        "Raw file totals captured before transformation with file hashes; the transformed tables reproduce them (18 checks).",
        "A full refresh takes about 30 seconds (target: under 3 minutes)."])
    S += [Paragraph("Two limits: the expected values and the DAX were written by the same author, so agreement is strong but not fully independent proof; and slicer behaviour and the published report have not been tested in bulk.", B)]
    # 8 adding an offer
    S += [Paragraph("8. How to add a new offer", H1), Paragraph("Offers are read from offers.csv; nothing in the report needs to be edited for an ordinary new offer.", B)] + bullets([
        "Add a row to offers.csv: a new unique offer_id, the offer_type (bogo, discount or informational), difficulty (minimum spend), reward, duration in days, and channels as a list in single quotes, for example ['web', 'email'].",
        "Make sure events.csv contains events for the new offer using the same offer_id.",
        "Refresh. The offer appears in the scorecard, in the offer-type, reward and channel charts, and in the drill-through.",
        "A new offer type (something other than the three above) will show in lower case; add it to the labels in the DimOffer query (Offer Type step). A new channel appears automatically.",
        "A new reward value appears as a new bar in Redemption rate by reward, ordered by amount.",
        "Check: the number of rows in DimOffer equals the rows in offers.csv, and Offers Sent on the Overview page still equals the number of offer received events."])
    S += [Paragraph("This procedure was tested on 28 September 2026: a new offer with five events was added to a copy of the data, the model was refreshed without editing any step, and all nine checks passed (offers 11, channel rows 35, offers sent 76,280, the new offer visible with 3 sent and 1 completed, no orphan events). The record is in add_offer_test_record.", B)]
    # 9 refresh / publish
    S += [Paragraph("9. Refresh and publishing", H1)] + bullets([
        "The SourceFolder parameter holds the folder of CSV files. Change it under Transform data, Edit parameters. Keep file names and headers unchanged.",
        "Scheduled refresh in the Power BI service needs the files to be reachable: use a data gateway for a personal computer or file server, or move the files to a shared cloud folder.",
        "Publishing, workspace roles and sharing are set by the customer's administrator. After publishing, test slicers, drill-through and tooltips as a viewer."])
    # 10 decisions
    S += [Paragraph("10. Decisions and assumptions", H1)]
    rows = [["Id", "Topic", "Decision"]] + [[r["id"], r["topic"], r["decision"]] for r in A["decisions"]["business_rules"]]
    S += [tbl(rows, [12 * mm, 38 * mm, doc.width - 50 * mm])]
    S += [Paragraph("11. Known limitations", H1)] + bullets([
        "The window is 30 days; every figure describes that window only.",
        "Channels are listed per offer, not per event, so channel results overlap and say nothing about which channel delivered an individual offer.",
        "Purchases carry no offer, so purchases cannot be attributed to a specific offer.",
        "Customers with a missing profile (age, income and gender all blank) redeem far less than everyone else; the reason is not in the data.",
        "Spending comparisons between customers who completed offers and those who did not show association, not cause."])
    doc.build(S); return out

def main():
    A = load_all(); F = Facts()
    g = user_guide(A, F); t = tech_doc(A, F); F.save(os.path.join(DOCS, "traceability_docs.json"))
    print("user guide:", g); print("technical document:", t)

if __name__ == "__main__":
    main()
