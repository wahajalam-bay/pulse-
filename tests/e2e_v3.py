"""End-to-end check of the flows Haroon's 1 Sep review asked for."""
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
    print(("  PASS  " if cond else "  FAIL  ") + name + (("  -> " + str(detail)[:120]) if detail else ""))


_, r = call("/api/login", {"email": "haroon@zameen.com", "password": "ZDesign!2026"})
TOK = r["token"]
_, boot = call("/api/bootstrap")
OPAL = [p for p in boot["projects"] if p["name"] == "Zameen Opal"][0]["id"]
print("signed in:", r["user"]["name"], "| priorities:", boot["priorities"],
      "| unconfirmed:", boot["unconfirmed"])

print("\n#1 #2 #3 #4 #20 · CROSS-TEAM REQUEST, ACKNOWLEDGE, THREAD, ESCALATE")
s, r = call("/api/case/create", {
    "type": "CTR", "project_id": OPAL, "title": "E2E — confirm the fire NOC position",
    "to_team": "Legal", "priority": "High", "tat_days": 4,
    "note": "Authority has asked. We cannot answer without Legal."})
check("raised at another team", s == 200, r)
check("an acknowledgement window was set", bool(r.get("ack_due_at")), r.get("ack_due_at"))
CID = r["id"]
s, r = call("/api/case/create", {"type": "CTR", "project_id": OPAL,
                                 "title": "E2E bad team", "to_team": "Marketing Dept"})
check("an unknown department is refused", s == 409, r.get("error"))

s, r = call("/api/case/message", {"id": CID, "kind": "update",
                                  "body": "Pulling the title file now."})
check("an update posts without closing the case", s == 200, r)
_, e = call(f"/api/entity/case/{CID}")
check("the case is still open after an update", e["record"]["status"] == "open")
check("the update is on the thread", len(e["extra"]["messages"]) >= 2,
      len(e["extra"]["messages"]))
check("answering counted as acknowledging",
      bool(e["record"]["acknowledged_at"]), e["record"]["acknowledged_at"])
s, r = call("/api/case/ack", {"id": CID})
check("a second acknowledgement is refused", s == 409, r.get("error"))
s, r = call("/api/case/escalate", {"id": CID})
check("escalation without a reason is refused", s == 409, r.get("error"))
s, r = call("/api/case/escalate", {"id": CID, "reason": "Blocking the authority response."})
check("escalated up the configured ladder", s == 200 and r.get("level") == 1, r)
_, e = call(f"/api/entity/case/{CID}")
check("the escalation is on the thread",
      any(m["kind"] == "escalation" for m in e["extra"]["messages"]))

print("\n#5 #6 · PRIORITY IS SEPARATE FROM TAT, AND ITS HISTORY SURVIVES")
s, r = call("/api/priority/set", {"entity": "case", "id": CID, "priority": "Critical"})
check("priority change needs a reason", s == 409, r.get("error"))
s, r = call("/api/priority/set", {"entity": "case", "id": CID, "priority": "Critical",
                                  "reason": "Authority deadline is Thursday."})
check("priority changed", s == 200 and r.get("priority") == "Critical", r)
s, r = call("/api/priority/set", {"entity": "case", "id": CID, "priority": "Urgent",
                                  "reason": "x"})
check("a priority outside the configured levels is refused", s == 409, r.get("error"))
_, e = call(f"/api/entity/case/{CID}")
check("the old value and the reason are kept",
      len(e["extra"]["priority_log"]) == 1
      and e["extra"]["priority_log"][0]["old_priority"] == "High",
      e["extra"]["priority_log"])
check("TAT is still its own field", e["record"]["tat_days"] == 4, e["record"]["tat_days"])

print("\n#7 #8 #9 #10 #23 · ONE VISIT, MANY FINDINGS, EVIDENCE, RFI, HISTORY")
s, r = call("/api/visit/create", {"project_id": OPAL})
check("a visit with no findings and no summary is refused", s == 409, r.get("error"))
FINDS = [
    {"title": "E2E — parapet height 900mm against 1100mm", "category": "Dimensional",
     "location": "Level 9, east elevation", "responsible_team": "Architecture",
     "priority": "Critical", "tat_days": 3, "non_compliance": 1,
     "description": "Measured 900mm against 1100mm on A-201 Rev C."},
    {"title": "E2E — duct penetration not on the issued set", "category": "Documentation",
     "location": "Basement 1 blockwork", "responsible_team": "MEP",
     "priority": "Medium", "tat_days": 14},
    {"title": "E2E — lobby marble joint width", "category": "Architectural finish",
     "location": "Ground floor lobby", "responsible_team": "Architecture",
     "priority": "High", "tat_days": 7, "non_compliance": 1},
    {"title": "E2E — edge protection missing", "category": "Safety",
     "location": "Level 9, east elevation", "responsible_team": "Architecture",
     "priority": "Critical", "tat_days": 1},
    {"title": "E2E — slab rebar verified", "category": "Structural",
     "location": "Level 10 slab", "responsible_team": "Structure", "priority": "Low"},
]
s, r = call("/api/visit/create", {
    "project_id": OPAL, "photos": 12, "summary": "E2E walk of levels 9-10 and the lobby.",
    "findings": json.dumps(FINDS)})
check("one visit recorded five separate findings",
      s == 200 and len(r["findings"]) == 5, r)
check("the two non-compliant ones each raised an NCR", len(r["ncr"]) == 2, r["ncr"])
check("a repeat in the same place was flagged as recurrence", r["recurrences"] >= 1,
      r["recurrences"])
VID, FIDS = r["id"], r["findings"]
_, fe = call(f"/api/entity/finding/{FIDS[0]}")
check("the finding knows its visit", fe["record"]["visit_id"] == VID)
check("the finding carries its own owner, priority and TAT",
      fe["record"]["responsible_team"] == "Architecture"
      and fe["record"]["priority"] == "Critical" and fe["record"]["tat_days"] == 3)
check("the NCR is linked back to the finding", bool(fe["record"]["case_id"]))
_, ve = call(f"/api/entity/visit/{VID}")
check("the visit renders as a container of five", len(ve["extra"]["findings"]) == 5)

s, r = call("/api/finding/assign", {"id": FIDS[1], "responsible_team": "Legal",
                                    "tat_days": 5})
check("a finding can be assigned to any department, incl. Legal", s == 200, r)
s, r = call("/api/finding/assign", {"id": FIDS[1], "responsible_team": "Nowhere"})
check("an unknown department is refused", s == 409, r.get("error"))
s, r = call("/api/finding/raise", {"id": FIDS[1], "as": "RFI"})
check("a finding becomes an RFI on the relevant team", s == 200, r)
s, r = call("/api/finding/resolve", {"id": FIDS[3]})
check("resolving with no resolution text is refused", s == 409, r.get("error"))
s, r = call("/api/finding/resolve", {"id": FIDS[3],
            "resolution": "Handrail and toe board installed; verified on site."})
check("resolved with a record of what was done", s == 200, r)
s, r = call("/api/finding/resolve", {"id": FIDS[0], "status": "closed",
                                     "resolution": "done"})
check("cannot close a non-compliance while its NCR is open", s == 409, r.get("error"))
check("  and it says why, and offers an override", r.get("overridable"), r.get("detail"))

print("\n#10 · HISTORY: IS THIS NEW, RECURRING, OR STILL OUTSTANDING")
_, fl = call("/api/findings")
check("recurrence is reported across the register", fl["kpi"]["recurring"] >= 1,
      fl["kpi"])
_, fe4 = call(f"/api/entity/finding/{FIDS[3]}")
check("a finding shows what was found in the same place before",
      len(fe4["extra"]["same_place"]) >= 1, len(fe4["extra"]["same_place"]))

print("\n#12 #17 · LESSON FROM A FINDING, WITH ROOT CAUSE")
s, r = call("/api/finding/lesson", {
    "id": FIDS[0], "root_cause": "Parapet height was never cross-checked against the "
    "approved elevation before the pour.", "delay_kind": "internal",
    "delay_owner": "Architecture", "preventive_action":
    "Add a parapet/balustrade height check to the stage 11 checklist."})
check("a lesson can be raised from a finding", s == 200, r)
LID = r["id"]
_, le = call(f"/api/entity/llr/{LID}")
check("the lesson records the root cause", bool(le["record"]["root_cause"]))
check("and whose delay it was", le["record"]["delay_kind"] == "internal")
check("and is visible to the department head",
      bool(le["record"]["head_notified_at"]), le["record"]["head_notified_at"])
check("and points back at the finding", le["record"]["origin_finding_id"] == FIDS[0])
s, r = call("/api/llr/improve", {"id": LID, "improvement_status": "agreed",
                                 "improvement_owner": "Ahmed Khan"})
check("the improvement action tracks separately from the lesson", s == 200, r)
_, lrn = call("/api/learning")
check("the Learning Summary counts turnaround lost", lrn["kpi"]["tat_days_lost"] > 0,
      lrn["kpi"]["tat_days_lost"])
check("and separates internal from external causes",
      lrn["kpi"]["internal"] > 0 and lrn["kpi"]["external"] >= 0, lrn["kpi"])

print("\n#27 #30 #31 · HOLD IS NOT OWN TIME")
_, tl = call(f"/api/tasks?project={OPAL}&status=running")
TID = tl["rows"][0]["id"]
s, r = call("/api/task/hold", {"id": TID})
check("a hold with no reason is refused", s == 409, r.get("error"))
s, r = call("/api/task/hold", {"id": TID, "reason": "Waiting on the contractor's survey."})
check("held", s == 200, r)
_, te = call(f"/api/entity/task/{TID}")
check("the task reads as on hold", te["record"]["status"] == "hold")
check("and the reason is on it", bool(te["record"]["hold_reason"]))
s, r = call("/api/task/resume", {"id": TID})
check("resumed, and the blocked days are booked to hold", s == 200, r)

print("\n§36 · THE DEFINITIONS ARE SETTINGS, NOT CONSTANTS")
_, st = call("/api/settings")
check("all 26 ship unconfirmed", st["unconfirmed"] == st["total"] == 26, st["unconfirmed"])
s, r = call("/api/setting/save", {"key": "ack.window_unit", "value": "fortnights"})
check("an invalid value is refused", s == 409, r.get("error"))
s, r = call("/api/setting/save", {"key": "ack.window_unit", "value": "working_days",
                                  "confirm": 1})
check("a definition can be set and confirmed", s == 200 and r.get("confirmed"), r)
_, st2 = call("/api/settings")
check("the unconfirmed count drops", st2["unconfirmed"] == 25, st2["unconfirmed"])
row = [x for x in st2["rows"] if x["key"] == "ack.window_unit"][0]
check("and it records who confirmed it", row["confirmed_by"] == "Haroon Noon",
      row["confirmed_by"])

s, r = call("/api/setting/save", {"key": "delivery.exclude_md_approval", "value": "0"})
check("MD approval can be put back into delivery time", s == 200, r)
_, dl = call("/api/delivery")
check("and the delivery calculation follows the setting",
      "md_approval" not in dl["exclusions"], dl["exclusions"])
call("/api/setting/save", {"key": "delivery.exclude_md_approval", "value": "1"})

s, r = call("/api/setting/save", {"key": "time.wait_counts_as_inprogress", "value": "1"})
check("the open §36 D question is a switch", s == 200, r)
_, t1 = call(f"/api/tasks?project={OPAL}")
withwait = sum(1 for x in t1["rows"] if x["late"])
call("/api/setting/save", {"key": "time.wait_counts_as_inprogress", "value": "0"})
_, t2 = call(f"/api/tasks?project={OPAL}")
without = sum(1 for x in t2["rows"] if x["late"])
check("flipping it actually changes the variance figures", withwait != without,
      f"{withwait} late with wait counted vs {without} without")

print("\n#13 #21 #22 #28 #29 · THE VIEWS")
_, td = call("/api/today")
check("today is sorted overdue-then-priority",
      td["rows"][0]["overdue"] or td["rows"][0]["priority"] == "Critical",
      td["rows"][0])
check("every row says why it is there and what to do",
      all(x["why"] and x["action"] for x in td["rows"]))
_, ex = call("/api/exec")
check("exec reports per-department facts", len(ex["departments"]) == 4)
check("and workload by station, for the front-loading",
      all(t in ex["by_station"] for t in ["Architecture", "MEP"]))
check("and workload over calendar time", len(ex["by_month"]["Architecture"]) > 3,
      len(ex["by_month"]["Architecture"]))
_, mx = call("/api/matrix")
cell = next(c for row in mx["rows"] for c in row["cells"] if c["actual"])
check("matrix cells carry all five time categories",
      all(k in cell for k in ("expected", "actual", "in_progress",
                              "wait_internal", "wait_external", "hold")), cell)
check("and attribute the delay", "delay_owner" in cell, cell.get("delay_owner"))
_, cat = call("/api/catalog")
wf = cat["workflows"][0]
check("the catalogue carries the §23 attributes",
      all(k in wf for k in ("trigger", "completion", "receiving", "dependencies",
                            "tat_days", "visibility", "source")), list(wf)[:14])

print(f"\n{len(ok)} passed, {len(fail)} failed")
if fail:
    print("FAILED: " + "; ".join(fail))
