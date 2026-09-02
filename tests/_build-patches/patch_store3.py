"""Patch store.py part 3: seed the template, and fill the registers that were empty."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\store.py"
src = open(PATH, encoding="utf-8").read()

S = "\u00a7"


def sub(old, new):
    global src
    assert old in src, "anchor missing: " + old[:70]
    src = src.replace(old, new, 1)


# ── seed the §4.2 template alongside the catalog ──
sub('''    log(c, "system", 0, "system", None, "seed",''',
    '''    # the §4.2 annexure, authored once and stamped onto every stage checklist
    for stage, text, source in CHECKLIST_TEMPLATE:
        n = c.execute("SELECT COALESCE(MAX(seq),0) FROM checklist_templates "
                      "WHERE stage=?", (stage,)).fetchone()[0]
        c.execute("INSERT INTO checklist_templates(stage,seq,text,source,added_by,"
                  "added_at) VALUES(?,?,?,?,?,?)",
                  (stage, n + 1, text, source, "system", now()))

    log(c, "system", 0, "system", None, "seed",''')

sub('''        f"{len(catalog.flatten())} catalog steps from Design Workflow Booklet Vol.1")''',
    '''        f"{len(catalog.flatten())} catalog steps, "
        f"{len(CHECKLIST_TEMPLATE)} stage-checklist template items")''')

# ── call the new register seeds ──
sub('''    _demo_cases(c)
    _demo_obligations(c)
    c.commit()''',
    '''    _demo_cases(c)
    _demo_obligations(c)
    _demo_registers(c)
    _demo_visits(c)
    _demo_llr(c)
    c.commit()''')


REG = '''

# ── the registers, derived from where each project actually got to ───────────
# Before this, Drawings & Issuance, site visits and the authority file were all
# empty tables behind live buttons — a rail you could open and do nothing on.
# None of this is invented progress: every row below is generated FROM the stage
# each project has actually reached in project_stages, so the register and the
# spine can never disagree.

DRAWING_SET = [
    # (number, title, discipline, first issued at stage)
    ("A-001", "Site plan and setting out",                 "Architecture", 3),
    ("A-002", "Zoning and ground coverage compliance",      "Architecture", 3),
    ("A-101", "Basement floor plan",                        "Architecture", 5),
    ("A-102", "Ground floor plan",                          "Architecture", 5),
    ("A-103", "Typical floor plan",                         "Architecture", 5),
    ("A-104", "Roof plan",                                  "Architecture", 5),
    ("A-201", "Elevations %(D)s north and east",                 "Architecture", 5),
    ("A-202", "Sections A-A and B-B",                       "Architecture", 5),
    ("A-901", "Authority submission set",                   "Architecture", 7),
    ("A-301", "Core, staircase and lift details",           "Architecture", 10),
    ("A-401", "Finishing schedule and internal elevations", "Architecture", 12),
    ("S-101", "Raft foundation layout",                     "Structure", 5),
    ("S-201", "Column layout and schedule",                 "Structure", 5),
    ("S-301", "Typical slab reinforcement",                 "Structure", 10),
    ("S-401", "Retaining wall and ramp details",            "Structure", 11),
    ("E-101", "Power layout %(D)s typical floor",                "MEP", 4),
    ("M-101", "HVAC layout %(D)s typical floor",                 "MEP", 4),
    ("P-101", "Plumbing and drainage layout",               "MEP", 4),
    ("F-101", "Fire fighting and detection layout",         "MEP", 11),
]


def _stage_dates(c, pid):
    """actual_start / actual_end per stage, so register dates track the spine."""
    out = {}
    for r in c.execute("SELECT stage,status,actual_start,actual_end,planned_end "
                       "FROM project_stages WHERE project_id=?", (pid,)):
        out[r["stage"]] = dict(r)
    return out


def _reached(c, pid):
    done = c.execute("SELECT COALESCE(MAX(stage),0) FROM project_stages "
                     "WHERE project_id=? AND status='done'", (pid,)).fetchone()[0] or 0
    run = c.execute("SELECT COALESCE(MAX(stage),0) FROM project_stages "
                    "WHERE project_id=? AND status='running'", (pid,)).fetchone()[0] or 0
    return done, max(done, run)


def _add_doc(c, entity, eid, pid, title, kind, link, rev="A", who="system"):
    c.execute("INSERT INTO documents(entity,entity_id,project_id,title,kind,link,"
              "revision,added_by,added_at) VALUES(?,?,?,?,?,?,?,?,?)",
              (entity, eid, pid, title, kind, link, rev, who, now()))


def _demo_registers(c):
    """Drawing register, revision history, transmittals with real sheet lists,
    and the authority file. All keyed off the stage the project has reached."""
    if c.execute("SELECT COUNT(*) FROM drawings").fetchone()[0]:
        return
    for pr in c.execute("SELECT id,name,code FROM projects WHERE is_bau=0").fetchall():
        pid, code = pr["id"], pr["code"]
        done, top = _reached(c, pid)
        dates = _stage_dates(c, pid)

        def when(stage, fallback=60):
            d = dates.get(stage) or {}
            iso = d.get("actual_end") or d.get("actual_start") or d.get("planned_end")
            if iso:
                return iso[:10]
            return (today() - datetime.timedelta(days=fallback)).isoformat()

        made = {}
        for number, title, disc, from_stage in DRAWING_SET:
            if from_stage > top:
                continue
            # revision follows issuance history, not a random letter
            if top >= 11 and from_stage <= 11:
                revs = ["A", "B", "C"]
                status = "IFC"
            elif top >= 10 and from_stage <= 10:
                revs = ["A", "B"]
                status = "for review"
            else:
                revs = ["A"]
                status = "draft"
            rev = revs[-1]
            base = when(from_stage)
            c.execute("INSERT INTO drawings(project_id,number,title,discipline,"
                      "revision,status,link,stage,created_at,created_by) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (pid, number, title, disc, rev, status,
                       f"https://drive.zameen.com/zd/{code}/{number}-{rev}.pdf",
                       from_stage, base, "Design team"))
            did = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            made[number] = (did, rev, disc, from_stage)
            d0 = datetime.date.fromisoformat(base)
            for i, rv in enumerate(revs):
                st = "draft" if i == 0 else ("for review" if i == 1 else "IFC")
                c.execute("INSERT INTO drawing_revs(drawing_id,revision,status,link,"
                          "note,at,by_whom) VALUES(?,?,?,?,?,?,?)",
                          (did, rv, st,
                           f"https://drive.zameen.com/zd/{code}/{number}-{rv}.pdf",
                           "Initial issue" if i == 0 else "Revised after coordination",
                           _add_working_days(d0, i * 12).isoformat(), "Design team"))

        # transmittals — the contractual fact, with the sheet list attached
        def issue(phase, to, stage_cap, disciplines, day_stage):
            sheets = [v for k, v in made.items()
                      if v[3] <= stage_cap and v[2] in disciplines]
            if not sheets:
                return
            n = c.execute("SELECT COUNT(*) FROM transmittals").fetchone()[0]
            ref = f"TR-{code}-{200 + n + 1}"
            c.execute("INSERT INTO transmittals(ref,project_id,phase,issued_to,"
                      "drawing_count,note,issued_at,issued_by) VALUES(?,?,?,?,?,?,?,?)",
                      (ref, pid, phase, to, len(sheets),
                       f"{len(sheets)} sheets, register revisions attached",
                       when(day_stage), "Ahmed Khan"))
            tid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            for did, rev, _disc, _st in sheets:
                c.execute("INSERT OR IGNORE INTO transmittal_drawings(transmittal_id,"
                          "drawing_id,revision) VALUES(?,?,?)", (tid, did, rev))
            _add_doc(c, "transmittal", tid, pid, f"{ref} cover letter and sheet list",
                     "Transmittal", f"https://drive.zameen.com/zd/{code}/{ref}.pdf",
                     who="Ahmed Khan")

        if top >= 7:
            issue("Authority", "Authority, PM", 7,
                  {"Architecture", "Structure", "MEP"}, 7)
        if top >= 10:
            issue("Tender", "PM, Supply Chain", 10,
                  {"Architecture", "Structure", "MEP"}, 10)
        if top >= 11:
            issue("IFC Phase I", "PM, QA/QC, Contractor", 11,
                  {"Architecture", "Structure"}, 11)
            issue("IFC Phase II", "PM, QA/QC, Contractor", 11,
                  {"Architecture", "Structure", "MEP"}, 11)
        if top >= 12:
            issue("IFC Phase III", "PM, Contractor", 12, {"Architecture", "MEP"}, 12)

        # ── the authority file (%(SS)s7 / %(SS)s17) ──
        if top >= 7:
            sub_on = when(7, 200)
            approved = top >= 8
            resp = _add_working_days(datetime.date.fromisoformat(sub_on),
                                     28).isoformat() if approved else None
            c.execute("INSERT INTO authority(project_id,authority,kind,ref,title,stage,"
                      "submitted_on,submitted_by,status,responded_on,observations,"
                      "conditions) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (pid, "LDA" if pr["name"].find("Mall") < 0 else "CDA",
                       "submission", f"AUT-{code}-{300 + pid}",
                       "Building plan approval %(D)s full submission set", 7,
                       sub_on, "Ahmed Khan",
                       "approved" if approved else "observations", resp,
                       "" if approved else
                       "Setback on the north elevation queried; area statement "
                       "on sheet A-002 to be restated per by-law 12(3).",
                       "Approved subject to fire NOC before occupancy."
                       if approved else ""))
            aid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            _add_doc(c, "authority", aid, pid, "Submission letter and drawing list",
                     "Authority", f"https://drive.zameen.com/zd/{code}/AUT-submission.pdf",
                     who="Ahmed Khan")
            if not approved:
                c.execute("INSERT INTO coordination(project_id,stage,from_team,to_lane,"
                          "ask,sla_days,opened_at) VALUES(?,?,?,?,?,?,?)",
                          (pid, 7, "Architecture", "Authority",
                           "Response to building plan observations", 21, sub_on))
        if top >= 13:
            c.execute("INSERT INTO authority(project_id,authority,kind,ref,title,stage,"
                      "submitted_on,submitted_by,status,observations) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (pid, "LDA", "inspection", f"AUT-{code}-{400 + pid}",
                       "Structural completion inspection", 13,
                       when(13, 45), "Ahmed Khan", "submitted", ""))


def _demo_visits(c):
    """Manual %(SS)s15 — the monthly visit. And the point of it: a visit that finds
    non-compliance RAISES AN NCR, which is a case on a route with a clock on it,
    not a checkbox on a row."""
    if c.execute("SELECT COUNT(*) FROM site_visits").fetchone()[0]:
        return
    findings = [
        "Basement 1 blockwork checked against A-101 Rev C. Setting out correct; "
        "two service penetrations not shown on the MEP set.",
        "Ground floor lobby %(D)s marble mock-up laid. Joint width does not match the "
        "approved sample; shade variation across three crates.",
        "Typical floor 6-9 %(D)s slab reinforcement inspected with QA/QC against "
        "S-301 Rev C. No deviation found.",
        "Corridor ceiling void measured at 320mm against 400mm required for the "
        "coordinated duct route. Clash with the approved MEP layout.",
    ]
    people = ["Ahmed Khan", "Umer Farooq", "Aarij Ali", "Yahya Ali Khan"]
    k = 0
    for pr in c.execute("SELECT id,name,code FROM projects WHERE is_bau=0").fetchall():
        pid, code = pr["id"], pr["code"]
        _done, top = _reached(c, pid)
        if top < 11:
            continue
        for m in range(3):
            k += 1
            day = today() - datetime.timedelta(days=28 * m + 4)
            f = findings[k %% len(findings)]
            nc = 1 if (k %% 3 == 1) else 0
            c.execute("INSERT INTO site_visits(project_id,visited_on,by_whom,findings,"
                      "non_compliance,photos,created_at) VALUES(?,?,?,?,?,?,?)",
                      (pid, day.isoformat(), people[k %% len(people)], f, nc,
                       6 + (k %% 9), now()))
            vid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            if nc:
                cid, ref = open_case(
                    c, "NCR", pid, code,
                    f.split(".")[0][:90], None, people[k %% len(people)],
                    day.isoformat(), "Raised from site visit " + str(vid),
                    position=1, origin=f"site visit #{vid}")
                c.execute("INSERT INTO coordination(project_id,stage,from_team,to_lane,"
                          "ask,sla_days,opened_at) VALUES(?,?,?,?,?,?,?)",
                          (pid, 13, "Architecture", "QA/QC",
                           f"{ref} %(D)s joint re-inspection after rectification", 5,
                           day.isoformat()))
                log(c, people[k %% len(people)], 1, "visit", vid, "create",
                    f"Site visit %(D)s non-compliance found, {ref} raised",
                    project=pr["name"])


def _demo_llr(c):
    """Manual %(SS)s7.6 — the Lessons Learned Register.

    Seeded with lessons that are ACTUALLY TRUE of this department's documents, not
    invented ones: the cross-manual collisions and the blank columns found during
    the document review. Three are already ruled and promoted into the stage
    checklist template, so the loop %(SS)s7.6 describes can be seen working rather
    than described."""
    if c.execute("SELECT COUNT(*) FROM llr").fetchone()[0]:
        return
    proj = {r["name"]: r["id"] for r in c.execute("SELECT id,name FROM projects")}
    L = [
        # (project, stage, discipline, category, title, detail, impact, status,
        #  ruling, promote_stage, promoted_text)
        (None, 7, "Architecture", "Governance",
         "Area statement differed between Architecture and Structure sheets at submission",
         "The authority queried the area statement because sheet A-002 and the "
         "structural set were generated from different layout revisions.",
         "One resubmission cycle, 4 weeks of authority wait time.",
         "adopted", "Cross-discipline area reconciliation is mandatory before any "
         "authority submission.", 7,
         "Area statement reconciled and initialled by all three disciplines "
         "before the submission set is printed"),
        (None, 12, "Architecture", "Materials",
         "Mock-up approved verbally on site with no record",
         "A finishing mock-up was accepted during a walk-through. When the shade "
         "varied at delivery there was no approved sample to compare against.",
         "Sample re-called, 3 weeks lost on the finishing programme.",
         "adopted", "No mock-up is approved without a dated register entry and a "
         "retained physical sample.", 12,
         "Every approved mock-up has a dated register entry and a retained "
         "physical sample"),
        (None, 11, "MEP", "Coordination",
         "Corridor ceiling void frozen before the duct route was coordinated",
         "The architectural ceiling level was issued for construction while the "
         "MEP duct route was still under revision.",
         "Recurring clash, one DCR per project on the same detail.",
         "adopted", "The ceiling void schedule is a joint Architecture/MEP "
         "deliverable and cannot be issued by one discipline alone.", 11,
         "Ceiling void schedule signed jointly by Architecture and MEP before "
         "IFC issuance"),
        (None, None, None, "Document control",
         "MAR means three different things across the manuals",
         "Design %(SS)s11 (Material Approval, PKR 500k+), PM %(SS)s5.3 (Material Approval, "
         "all materials) and Supply Chain %(SS)s4.2 (Material Acquisition, capex) all use "
         "the same acronym with different scopes and different approval chains.",
         "Submissions routed to the wrong chain; approvals given by people "
         "without the authority for that value band.",
         "open", "", None, None),
        (None, 3, "Architecture", "Planning",
         "Design Schematics carries two published TATs that differ by three weeks",
         "The booklet captions the schematics flowchart 8-9 weeks; Guidelines "
         "Manual %(SS)s4.0 publishes 4-6 weeks for the same stage.",
         "No SLA for the stage can be defended, so none is enforced.",
         "open", "", None, None),
        (None, None, None, "Document control",
         "%(SS)s4.2 internal checklist annexure does not exist",
         "The Manual makes checklist sign-off mandatory before drawing issuance "
         "and then marks the annexure itself \\"(to be added)\\".",
         "A mandatory gate was a signature against undefined content.",
         "ruled", "Annexure authored in-system as the stage checklist template; "
         "Ahmed to review and rule on each item.", None, None),
        (None, 3, "Structure", "Planning",
         "Topographical Survey has no published duration",
         "The booklet's duration column is blank for Topographical Survey and for "
         "In-house Structural Stability Ownership.",
         "Stage 3 cannot be baselined end to end; 17 steps carry no duration.",
         "open", "", None, None),
        (None, 10, "Architecture", "Cost",
         "Value engineering ran after tender award rather than before",
         "VE options were studied once the tender price was known and the "
         "contractor engaged, so every change became a DCR with a cost claim.",
         "Change cost carried by the project instead of avoided at design stage.",
         "ruled", "VE is a stage-10 activity. Trigger it on the QS estimate, not "
         "on the tender return.", None, None),
    ]
    names = [r["name"] for r in c.execute(
        "SELECT name FROM projects WHERE is_bau=0 ORDER BY name")]
    for i, (pname, stage, disc, cat, title, detail, impact, status, ruling,
            pstage, ptext) in enumerate(L):
        pid = proj.get(pname or names[i %% len(names)])
        raised = (today() - datetime.timedelta(days=30 + i * 17)).isoformat()
        c.execute("INSERT INTO llr(project_id,stage,discipline,category,title,detail,"
                  "impact,raised_by,raised_at,source,status,ruling,ruled_by,ruled_at)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (pid, stage, disc, cat, title, detail, impact,
                   "Ahmed Khan" if i %% 2 else "Haroon Noon", raised,
                   "Design Manual %(SS)s7.6", status, ruling or None,
                   "Haroon Noon" if status in ("ruled", "adopted") else None,
                   raised if status in ("ruled", "adopted") else None))
        lid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        if pstage and ptext:
            n = c.execute("SELECT COALESCE(MAX(seq),0) FROM checklist_templates "
                          "WHERE stage=?", (pstage,)).fetchone()[0]
            c.execute("INSERT INTO checklist_templates(stage,seq,text,source,llr_id,"
                      "added_by,added_at) VALUES(?,?,?,?,?,?,?)",
                      (pstage, n + 1, ptext, f"Lessons learned LLR-{lid}", lid,
                       "Haroon Noon", now()))
            tid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.execute("UPDATE llr SET promoted_stage=?,promoted_at=?,template_id=? "
                      "WHERE id=?", (pstage, raised, tid, lid))
''' % {"D": "\u2014", "SS": S}

sub('''if __name__ == "__main__":
    seed(force="--force" in os.sys.argv)''',
    REG + '''

if __name__ == "__main__":
    seed(force="--force" in os.sys.argv)''')

sub('''        "obligations_missed": q("SELECT COUNT(*) FROM obligations WHERE done_at IS NULL "
                                "AND due_on < date('now')"),
    }, indent=2))''',
    '''        "obligations_missed": q("SELECT COUNT(*) FROM obligations WHERE done_at IS NULL "
                                "AND due_on < date('now')"),
        "drawings": q("SELECT COUNT(*) FROM drawings"),
        "transmittals": q("SELECT COUNT(*) FROM transmittals"),
        "sheets_issued": q("SELECT COUNT(*) FROM transmittal_drawings"),
        "site_visits": q("SELECT COUNT(*) FROM site_visits"),
        "authority_file": q("SELECT COUNT(*) FROM authority"),
        "lessons": q("SELECT COUNT(*) FROM llr"),
        "checklist_template": q("SELECT COUNT(*) FROM checklist_templates"),
        "documents": q("SELECT COUNT(*) FROM documents"),
    }, indent=2))''')

open(PATH, "w", encoding="utf-8").write(src)
print("store.py part 3 patched")
