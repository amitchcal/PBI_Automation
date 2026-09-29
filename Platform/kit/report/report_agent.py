"""Report agent (stories R-01 to R-05, first slice: the Overview page).

Takes the model project and a report config and writes a Power BI report (PBIR) with:
  the brand theme registered as a custom theme, the logo as a registered image, and pages built from a compact visual list.
Supported visuals: card, slicer, lineChart, clusteredBarChart, textbox, image.
Usage: python report_agent.py <report_config.json>
"""
import json, os, shutil, sys

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item"

def lit(v):
    if isinstance(v, bool): return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)): return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}

def column(entity, prop): return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}
def measure(entity, prop): return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}

def proj(field, entity, prop, active=False):
    p = {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}
    if active: p["active"] = True
    return p

def container_title(text, size=None):
    props = {"show": lit(True), "text": lit(text)}
    return {"title": [{"properties": props}]}

def build_visual(v, mtable):
    """One visual spec -> the visual.json body (without $schema and name)."""
    pos = v["pos"]; t = v["type"]
    body = {"position": {"x": pos[0], "y": pos[1], "z": v.get("z", 0), "width": pos[2], "height": pos[3], "tabOrder": v.get("tab", 0)}}
    vis = {"visualType": t, "drillFilterOtherVisuals": True}
    if t == "card":
        vis["query"] = {"queryState": {"Values": {"projections": [proj(measure(mtable, v["measure"]), mtable, v["measure"])]}}}
        if v.get("full_number", True):   # show 17,000 rather than 17K on KPI cards (1 = no display unit)
            vis["objects"] = {"labels": [{"properties": {"labelDisplayUnits": lit(1)}}]}
    elif t == "slicer":
        e, c = v["field"].split(".", 1)
        vis["query"] = {"queryState": {"Values": {"projections": [proj(column(e, c), e, c, True)]}}}
        vis["objects"] = {"data": [{"properties": {"mode": lit(v.get("mode", "Dropdown"))}}]}
    elif t in ("lineChart", "clusteredBarChart", "clusteredColumnChart", "funnel"):
        e, c = v["category"].split(".", 1)
        vis["query"] = {"queryState": {"Category": {"projections": [proj(column(e, c), e, c, True)]},
                                       "Y": {"projections": [proj(measure(mtable, m), mtable, m) for m in v["measures"]]}}}
        if v.get("series"):   # one line/bar series per value of this column
            se, sc = v["series"].split(".", 1); vis["query"]["queryState"]["Series"] = {"projections": [proj(column(se, sc), se, sc, True)]}
        if v.get("sort"):   # sort by the category column, which follows its sort-by-column (e.g. age bands in age order)
            vis["query"]["sortDefinition"] = {"sort": [{"field": column(e, c), "direction": "Ascending"}], "isDefaultSort": False}
        vis["objects"] = {} if t == "funnel" else {"valueAxis": [{"properties": {"showAxisTitle": lit(False)}}], "categoryAxis": [{"properties": {"showAxisTitle": lit(False)}}]}   # the chart title already says what is shown
        if v.get("labels") or t == "funnel":
            vis["objects"]["labels"] = [{"properties": {"show": lit(True), **({"labelDisplayUnits": lit(1)} if t == "funnel" else {})}}]   # full numbers on the funnel
    elif t == "pivotTable":   # matrix, optionally shaded like a heatmap
        re_, rc = v["rows"].split(".", 1); ce, cc = v["columns"].split(".", 1)
        vis["query"] = {"queryState": {"Rows": {"projections": [proj(column(re_, rc), re_, rc, True)]}, "Columns": {"projections": [proj(column(ce, cc), ce, cc, True)]},
                                       "Values": {"projections": [proj(measure(mtable, v["measure"]), mtable, v["measure"])]}}}
        if v.get("heat"):
            m = v["measure"]
            rule = {"FillRule": {"Input": measure(mtable, m), "FillRule": {"linearGradient2": {"min": {"color": {"Literal": {"Value": f"'{v['heat']['min']}'"}}}, "max": {"color": {"Literal": {"Value": f"'{v['heat']['max']}'"}}},
                                                                                              "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'noColor'"}}}}}}}
            vis["objects"] = {"values": [{"properties": {"backColor": {"solid": {"color": {"expr": rule}}}}, "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"{mtable}.{m}"}},
                                         {"properties": {"fontSize": lit(8)}}],
                              "rowHeaders": [{"properties": {"fontSize": lit(8)}}], "columnHeaders": [{"properties": {"fontSize": lit(8)}}],
                              "grid": [{"properties": {"rowPadding": lit(1)}}]}   # compact rows so every age band fits
    elif t == "scatterChart":   # one point per category; x, y and bubble size are measures
        e, c = v["category"].split(".", 1)
        vis["query"] = {"queryState": {"Category": {"projections": [proj(column(e, c), e, c, True)]},
                                       "X": {"projections": [proj(measure(mtable, v["x"]), mtable, v["x"])]}, "Y": {"projections": [proj(measure(mtable, v["y"]), mtable, v["y"])]},
                                       "Size": {"projections": [proj(measure(mtable, v["size"]), mtable, v["size"])]}}}
        if v.get("series"):   # colour the dots by this column
            se, sc = v["series"].split(".", 1); vis["query"]["queryState"]["Series"] = {"projections": [proj(column(se, sc), se, sc, True)]}
        vis["objects"] = {"categoryLabels": [{"properties": {"show": lit(bool(v.get("labels", False)))}}]}
        if v.get("x_axis_end") is not None:   # headroom past the highest dot, so it doesn't sit flush on the border
            vis["objects"]["categoryAxis"] = [{"properties": {"end": lit(v["x_axis_end"])}}]
    elif t == "tableEx":   # a plain table: first the columns, then the measures
        projs = []
        for cref in v.get("columns", []):
            ce, cc = cref.split(".", 1); projs.append(proj(column(ce, cc), ce, cc))
        projs += [proj(measure(mtable, m), mtable, m) for m in v["measures"]]
        vis["query"] = {"queryState": {"Values": {"projections": projs}}}
        vis["objects"] = {"values": [{"properties": {"fontSize": lit(8)}}], "columnHeaders": [{"properties": {"fontSize": lit(8)}}], "grid": [{"properties": {"rowPadding": lit(1)}}]}   # compact so every row fits
        if v.get("sort"):
            se, sc = v["sort"].split(".", 1); vis["query"]["sortDefinition"] = {"sort": [{"field": column(se, sc), "direction": v.get("sort_dir", "Ascending")}], "isDefaultSort": False}
    elif t == "pageNavigator":
        vis.pop("drillFilterOtherVisuals")
        vis["objects"] = {"pages": [{"properties": {"showHiddenPages": lit(False)}}]}   # drill-through and tooltip pages are not tabs
    elif t == "textbox":
        runs = [{"value": r["text"], "textStyle": {k: val for k, val in r.items() if k != "text"}} for r in v["runs"]]
        vis["objects"] = {"general": [{"properties": {"paragraphs": [{"textRuns": runs}]}}]}
        vis.pop("drillFilterOtherVisuals")
    elif t == "image":
        vis["objects"] = {"general": [{"properties": {"imageUrl": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1, "ItemName": v["image"]}}}}}]}
        vis.pop("drillFilterOtherVisuals")
    else:
        raise ValueError(f"unsupported visual type {t}")
    vco = container_title(v["title"]) if v.get("title") else {}
    if v.get("tooltip"):   # hovering shows this report page; it must be assigned per visual
        vco["visualTooltip"] = [{"properties": {"show": lit(True), "section": lit(v["tooltip"])}}]   # same shape Desktop writes
    if vco: vis["visualContainerObjects"] = vco
    body["visual"] = vis
    return body

def page_json(pg):
    """page.json for a normal, drill-through or tooltip page."""
    kind = pg.get("type", "Default")
    obj = {"$schema": f"{SCHEMA}/report/definition/page/2.0.0/schema.json", "name": pg["name"], "displayName": pg["displayName"], "displayOption": "FitToPage",
           "height": pg.get("height", 720), "width": pg.get("width", 1280)}
    if kind == "Drillthrough":
        e, c = pg["drill_field"].split(".", 1); fname = "f" + pg["name"]
        obj.update({"type": "Drillthrough", "visibility": "HiddenInViewMode",
                    "filterConfig": {"filters": [{"name": fname, "field": column(e, c), "type": "Categorical", "howCreated": "Drillthrough"}]},
                    "pageBinding": {"name": "pb" + pg["name"], "type": "Drillthrough", "parameters": [{"name": "p" + pg["name"], "boundFilter": fname, "fieldExpr": column(e, c)}]}})
        if pg.get("keep_only_drill_field"):   # do not carry the source row's other fields (e.g. offer) into this page
            obj["pageBinding"]["acceptsFilterContext"] = "None"
    elif kind == "Tooltip":
        obj.update({"type": "Tooltip", "visibility": "HiddenInViewMode", "displayOption": "ActualSize"})   # Desktop writes no page binding for tooltip pages
    return obj

def wjson(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f: json.dump(obj, f, indent=2)

def main(cfg_path, active=None):
    cfg = json.load(open(cfg_path, encoding="utf-8")); cdir = os.path.dirname(os.path.abspath(cfg_path)); plat = os.path.normpath(os.path.join(cdir, ".."))
    eid = cfg["engagement"]["id"]; proj_name = cfg["engagement"]["project"]; mtable = cfg["measures_table"]
    src = os.path.join(plat, "outputs", eid, "model", "pbip"); out = os.path.join(plat, "outputs", eid, "report"); dst = os.path.join(out, "pbip")
    os.makedirs(out, exist_ok=True)
    if os.path.isdir(dst): shutil.rmtree(dst)
    shutil.copytree(src, dst)
    rp = os.path.join(dst, f"{proj_name}.Report"); d = os.path.join(rp, "definition")
    shutil.rmtree(os.path.join(d, "pages"))
    # theme and logo from the brand kit output (F-05)
    brand = os.path.normpath(os.path.join(plat, "kit", "brand", "out", cfg["brand_kit"]))
    res = os.path.join(rp, "StaticResources", "RegisteredResources"); os.makedirs(res, exist_ok=True)
    shutil.copy(os.path.join(brand, "powerbi", "theme.json"), os.path.join(res, "BrandTheme.json"))
    items = [{"name": "BrandTheme.json", "path": "BrandTheme.json", "type": "CustomTheme"}]
    for img in cfg.get("images", []):
        shutil.copy(os.path.join(brand, img), os.path.join(res, img)); items.append({"name": img, "path": img, "type": "Image"})
    wjson(os.path.join(d, "report.json"), {
        "$schema": f"{SCHEMA}/report/definition/report/3.1.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY24SU10", "reportVersionAtImport": {"visual": "1.8.0", "report": "2.0.0", "page": "1.3.0"}, "type": "SharedResources"},
                            "customTheme": {"name": "BrandTheme.json", "reportVersionAtImport": {"visual": "1.8.0", "report": "2.0.0", "page": "1.3.0"}, "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources", "items": items}],
        "settings": {"useStylableVisualContainerHeader": True}})
    names = []
    for pg in cfg["pages"]:
        names.append(pg["name"])
        wjson(os.path.join(d, "pages", pg["name"], "page.json"), page_json(pg))
        for i, v in enumerate(pg["visuals"]):
            body = build_visual(v, mtable)
            body = {"$schema": f"{SCHEMA}/report/definition/visualContainer/2.4.0/schema.json", "name": v["id"], **body}
            body["position"]["tabOrder"] = i
            wjson(os.path.join(d, "pages", pg["name"], "visuals", v["id"], "visual.json"), body)
    wjson(os.path.join(d, "pages", "pages.json"), {"$schema": f"{SCHEMA}/report/definition/pagesMetadata/1.0.0/schema.json", "pageOrder": names, "activePageName": active or names[0]})   # 'active' lets a screenshot run open on a chosen page
    print(f"report project: {os.path.join(dst, proj_name + '.pbip')}  pages: {names}  visuals: {sum(len(p['visuals']) for p in cfg['pages'])}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
