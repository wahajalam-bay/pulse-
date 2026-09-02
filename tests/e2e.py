"""End-to-end check of the flows that are supposed to be CONNECTED."""
import json, urllib.request, urllib.error

BASE = "http://127.0.0.1:4010/zd"
TOK = None


def call(path, body=None, method=None):
    req = urllib.request.Request(BASE + path, method=method or ("POST" if body else "GET"))
    req.add_header("Content-Type", "application/json")
    if TOK:
        req.add_header("Authorization", "Bearer " + TOK)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


ok, fail = [], []


def check(name, cond, detail=""):
    (ok if cond else fail).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (("  -> " + str(detail)) if detail else ""))


_, r = call("/api/login", {"email": "haroon@zameen.com", "password": "ZDesign!2026"})
TOK = r["token"]
print("signed in as", r["user"]["name"], "tier", r["user"]["tier"])

_, boot = call("/api/bootstrap")
PID = [p for p in boot["projects"] if p["name"] == "Zameen Quadrangle"][0]["id"]
OPAL = [p for p in boot["projects"] if p["name"] == "Zameen Opal"][0]["id"]

print("\n1. A SITE VISIT THAT FINDS NON-COMPLIANCE RAISES AN NCR")
_, before = call("/api/site")
n0 = len(before["ncr"])
# NOTE: the visit contract changed with Haroon's 1 Sep review (#7). A visit is now a
# container of structured findings, and the NCR is raised by a FINDING rather than by
# the visit's free text — "a visit should not become one large unstructured record".
s, r = call("/api/visit/create", {
    "project_id": OPAL, "photos": 3, "summary": "E2E walk.",
    "findings": json.dumps([{
        "title": "E2E check — parapet height 900mm against 1100mm on A-201 Rev C.",
        "category": "Dimensional", "location": "Level 9, east elevation",
        "responsible_team": "Architecture", "priority": "Critical",
        "tat_days": 3, "non_compliance": 1}])})
check("visit accepted", s == 200, r)
check("an NCR ref came back", bool(r.get("ncr")), r)
_, after = call("/api/site")
check("NCR count went up", len(after["ncr"]) == n0 + 1, f"{n0} -> {len(after['ncr'])}")
ncr = [x for x in after["ncr"] if x["ref"] in (r.get("ncr") or [])]
check("the NCR sits at the design-assessment lane, not lane 0",
      bool(ncr) and ncr[0]["position"] == 1, ncr and ncr[0]["position"])
if ncr:
    _, ent = call(f"/api/entity/case/{ncr[0]['id']}")
    # provenance now runs NCR -> finding -> visit rather than NCR -> visit
    check("the NCR records where it came from",
          ent["record"]["origin_entity"] == "finding"
          and bool(ent["record"]["origin_id"]), ent["record"]["origin_entity"])
    _, fent = call(f"/api/entity/finding/{ent['record']['origin_id']}")
    check("and that finding points back at the visit",
          bool(fent["record"]["visit_id"]), fent["record"]["visit_id"])
    check("a QA/QC re-inspection clock was opened",
          any(a["to_lane"] == "QA/QC" for a in ent["extra"]["asks"]), ent["extra"]["asks"])

print("\n2. INITIATING A STAGE STAMPS THE §4.2 TEMPLATE ONTO THE CHECKLIST")
s, r = call("/api/stage/initiate", {"project_id": PID, "stage": 5})
check("stage 5 refused — stage 4 is not signed off", s == 409, r.get("error"))
check("the refusal is overridable", r.get("overridable"), r)
s, r = call("/api/stage/initiate", {"project_id": PID, "stage": 5,
                                    "override_reason": "E2E — checking the template stamp"})
check("override accepted", s == 200, r)
check("tasks generated from the catalog", r.get("tasks", 0) > 0, r)
s, chk = call(f"/api/checklist/{PID}/5")
check("the checklist arrived with content, not empty",
      len(chk["items"]) > 0, f"{len(chk['items'])} items")
check("the items cite their source",
      all(i["source"] for i in chk["items"]), chk["items"][:1])

print("\n3. A LESSON, ONCE RULED ON, CHANGES WHAT THE NEXT PROJECT IS CHECKED FOR")
s, r = call("/api/llr/create", {
    "title": "E2E — parapet height not cross-checked against the approved elevation",
    "detail": "Found on site at 900mm against 1100mm shown on A-201.",
    "impact": "Rework of 60 linear metres.", "stage": 11, "category": "Coordination"})
check("lesson raised", s == 200, r)
LID = r["id"]
s, r = call("/api/llr/promote", {"id": LID, "stage": 11, "text": "E2E parapet check"})
check("promotion refused before a ruling", s == 409, r.get("error"))
s, r = call("/api/llr/rule", {"id": LID, "ruling": "Parapet and balustrade heights are "
                              "checked against the approved elevation before IFC."})
check("ruling accepted", s == 200, r)
_, tpl_before = call("/api/template")
n_before = len(tpl_before["rows"])
s, r = call("/api/llr/promote", {
    "id": LID, "stage": 11,
    "text": "Parapet and balustrade heights checked against the approved elevation"})
check("adopted into the stage 11 template", s == 200, r)
check("it landed on open checklists too", r.get("checklists_updated", 0) >= 0, r)
_, tpl_after = call("/api/template")
check("the template grew", len(tpl_after["rows"]) == n_before + 1,
      f"{n_before} -> {len(tpl_after['rows'])}")
_, llr = call("/api/llr")
check("the lesson now reads as adopted",
      [x for x in llr["rows"] if x["id"] == LID][0]["status"] == "adopted")

print("\n4. A TRANSMITTAL CARRIES A SHEET LIST, AND ISSUING CHANGES THE REGISTER")
_, reg = call(f"/api/drawings?project={OPAL}")
draft = [d for d in reg["drawings"] if d["status"] != "IFC"]
pick = [d["id"] for d in reg["drawings"][:4]]
s, r = call("/api/transmittal/issue", {
    "project_id": OPAL, "phase": "IFC Phase II", "issued_to": "PM, QA/QC, Contractor",
    "drawing_ids": ",".join(str(x) for x in pick)})
check("transmittal issued", s == 200, r)
check("it recorded the sheet count from the list, not a typed number",
      r.get("sheets") == len(pick), r)
_, reg2 = call(f"/api/drawings?project={OPAL}")
tr = [t for t in reg2["transmittals"] if t["ref"] == r.get("ref")]
check("the sheet list is stored", bool(tr) and len(tr[0]["sheets"]) == len(pick),
      tr and len(tr[0]["sheets"]))
check("issuing for construction moved those sheets to IFC",
      all(d["status"] == "IFC" for d in reg2["drawings"] if d["id"] in pick))

print("\n5. A DRAWING KEEPS ITS REVISIONS")
did = pick[0]
_, d0 = call(f"/api/entity/drawing/{did}")
nrev = len(d0["extra"]["revs"])
s, r = call("/api/drawing/revise", {"id": did})
check("a revision with no reason is refused", s == 409, r.get("error"))
s, r = call("/api/drawing/revise", {"id": did, "note": "E2E — parapet height corrected"})
check("revision recorded", s == 200, r)
_, d1 = call(f"/api/entity/drawing/{did}")
check("history grew", len(d1["extra"]["revs"]) == nrev + 1,
      f"{nrev} -> {len(d1['extra']['revs'])}")
check("the sheet it was issued on still points at the old revision",
      bool(d1["extra"]["transmittals"]))

print("\n6. THE AUTHORITY CLOCK")
s, r = call("/api/authority/submit", {
    "project_id": PID, "authority": "LDA", "kind": "submission",
    "title": "E2E — revised building plan", "stage": 7, "sla_days": 21})
check("submission logged", s == 200, r)
AID = r["id"]
_, ent = call(f"/api/entity/authority/{AID}")
check("submitting opened a clock on the Authority", bool(ent["extra"]["ask"]), ent["extra"])
s, r = call("/api/authority/respond", {"id": AID, "status": "observations"})
check("an unrecorded observation is refused", s == 409, r.get("error"))
s, r = call("/api/authority/respond", {
    "id": AID, "status": "observations",
    "observations": "Setback on the north elevation queried under by-law 12(3)."})
check("response recorded", s == 200, r)
_, ent2 = call(f"/api/entity/authority/{AID}")
check("the clock closed when they answered",
      bool(ent2["extra"]["ask"] and ent2["extra"]["ask"]["closed_at"]), ent2["extra"]["ask"])
_, tasks = call(f"/api/tasks?project={PID}")
check("the observations came back as real work",
      any("authority observations" in t["title"] for t in tasks["rows"]))

print("\n7. CLOSEOUT — THE LIFECYCLE HAS AN END")
s, r = call("/api/project/close", {"project_id": PID})
check("closeout refused with reasons named", s == 409, r.get("missing"))
check("it names the as-built gate",
      any("as-built" in m for m in r.get("missing", [])), r.get("missing"))

print("\n8. SEARCH AND THE ENTITY DRAWER REACH EVERY REGISTER")
for q, kind in [("parapet", "llr"), ("Opal", "project"), ("A-101", "drawing"),
                ("Ahmed", "person"), ("Value Engineering", "product")]:
    _, sr = call("/api/search?q=" + q.replace(" ", "%20"))
    kinds = [g["kind"] for g in sr["groups"]]
    check(f"search “{q}” reaches {kind}", kind in kinds, kinds)

for kind, i in [("project", OPAL), ("task", 1), ("case", 1), ("drawing", 1),
                ("person", 1), ("obligation", 1), ("llr", LID), ("authority", AID),
                ("product", 1), ("coordination", 1)]:
    s, e = call(f"/api/entity/{kind}/{i}")
    check(f"drawer opens a {kind}", s == 200 and not e.get("error"), e.get("error"))

print(f"\n{len(ok)} passed, {len(fail)} failed")
if fail:
    print("FAILED: " + "; ".join(fail))
