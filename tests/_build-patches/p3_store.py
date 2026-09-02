"""Backlog #1 (cross-team route, lanes bound at raise time) + every new seed."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\store.py"
src = open(PATH, encoding="utf-8").read()
S = "\u00a7"
D = "\u2014"
RA = "\u2192"


def sub(old, new):
    global src
    assert old in src, "anchor: " + old[:70]
    src = src.replace(old, new, 1)


# ══════════════════════════════════════════════════════════════════════════
# 1 · the cross-team request. Backlog #1/#2/#3/#4/#16/#20.
# ══════════════════════════════════════════════════════════════════════════
sub('''    "ABD": {''',
'''    "CTR": {
        "label": "Cross-Team Request",
        # The gap the review opened with: a case could only travel a route that
        # was decided in advance, so "raise this to Legal" had nowhere to go and
        # the conversation left the system. The route is the same engine; what is
        # new is that two of its lanes are bound to teams CHOSEN WHEN IT IS
        # RAISED. @FROM and @TO are substituted in open_case().
        "source": "Haroon review 1 Sep %(S)s2.1 %(D)s cross-team collaboration",
        "value_routed": False,
        "stage": 13,
        "dynamic": True,
        "lanes": [
            ("Raised", "@FROM", 0),
            ("Acknowledgement", "@TO", 1),
            ("Investigation / response", "@TO", 3),
            ("Back to requestor", "@FROM", 1),
            ("Agreed and closed", "@FROM", 1),
        ],
    },
    "ESC": {
        "label": "Senior-Management Escalation",
        # %(S)s16: "Collaboration should not be limited to junior employees."
        # An escalation is not a nastier email, it is a case with a named senior
        # person on it and a clock, so the fact that it had to be escalated at
        # all becomes a number.
        "source": "Haroon review 1 Sep %(S)s16 %(D)s senior-management collaboration",
        "value_routed": False,
        "stage": 13,
        "dynamic": True,
        "lanes": [
            ("Raised by @FROM", "@FROM", 0),
            ("@TO line manager", "@TO", 1),
            ("@TO senior manager", "@TO", 2),
            ("Department heads", "Head ZD", 2),
            ("Resolved", "@FROM", 1),
        ],
    },
    "ABD": {''' % {"S": S, "D": D})

# bind @FROM / @TO when the case is instantiated
sub('''    route = ROUTES[typ]
    n = c.execute("SELECT COUNT(*) FROM cases WHERE type=?", (typ,)).fetchone()[0]''',
'''    route = ROUTES[typ]
    lanes = route["lanes"]
    if route.get("dynamic"):
        # Bind the placeholder lanes to the teams this particular request is
        # between. One route definition, every pair of departments.
        f = from_team or "Architecture"
        t = to_team or "Project Management"
        lanes = [(lbl.replace("@FROM", f).replace("@TO", t),
                  own.replace("@FROM", f).replace("@TO", t), sla)
                 for lbl, own, sla in lanes]
    n = c.execute("SELECT COUNT(*) FROM cases WHERE type=?", (typ,)).fetchone()[0]''')

sub('''    tat = tat_days if tat_days is not None else sum(
        (l[2] or 0) for l in route["lanes"]) or None''',
'''    tat = tat_days if tat_days is not None else sum(
        (l[2] or 0) for l in lanes) or None''')

sub('''    for idx, (label, owner, sla) in enumerate(route["lanes"]):
        entered, left, outcome = None, None, None''',
'''    for idx, (label, owner, sla) in enumerate(lanes):
        entered, left, outcome = None, None, None''')

# ══════════════════════════════════════════════════════════════════════════
# 2 · seed settings and departments
# ══════════════════════════════════════════════════════════════════════════
sub('''    # the §4.2 annexure, authored once and stamped onto every stage checklist''',
'''    # §36 — the business definitions, every one shipped UNCONFIRMED
    for key, val, kind, section, label, note, opts, ref in DEFINITIONS:
        c.execute("INSERT OR IGNORE INTO settings(key,value,kind,section,label,note,"
                  "options,doc_ref,confirmed,updated_at,updated_by) "
                  "VALUES(?,?,?,?,?,?,?,?,0,?,?)",
                  (key, val, kind, section, label, note, opts, ref, now(), "system"))

    # #18 — the organisation, so a finding or a lesson can belong to Legal
    for name, kind in catalog.DEPARTMENTS:
        c.execute("INSERT OR IGNORE INTO departments(name,kind,active) VALUES(?,?,1)",
                  (name, kind))

    # the §4.2 annexure, authored once and stamped onto every stage checklist''')

sub('''        f"{len(catalog.flatten())} catalog steps, "
        f"{len(CHECKLIST_TEMPLATE)} stage-checklist template items")''',
'''        f"{len(catalog.flatten())} catalog steps, "
        f"{len(CHECKLIST_TEMPLATE)} stage-checklist template items, "
        f"{len(DEFINITIONS)} business definitions (all UNCONFIRMED), "
        f"{len(catalog.DEPARTMENTS)} departments")''')

# ══════════════════════════════════════════════════════════════════════════
# 3 · expected_days per stage (#24 of the review: expected vs actual)
# ══════════════════════════════════════════════════════════════════════════
sub('''    _demo_intake(c)
    _demo_cases(c)''',
'''    _demo_expected(c)
    _demo_intake(c)
    _demo_cases(c)''')

# ══════════════════════════════════════════════════════════════════════════
# 4 · findings, priorities, threads
# ══════════════════════════════════════════════════════════════════════════
sub('''    _demo_registers(c)
    _demo_visits(c)
    _demo_llr(c)
    c.commit()''',
'''    _demo_registers(c)
    _demo_visits(c)
    _demo_llr(c)
    _demo_priorities(c)
    _demo_crossteam(c)
    c.commit()''')


NEW = '''

def _demo_expected(c):
    """#24 of the review: the matrix must separate EXPECTED from actual. The
    expected duration is the catalog's own published TAT for the stage, summed
    over its steps %(D)s not a number anyone typed."""
    exp = {}
    for r in c.execute("SELECT stage, SUM(COALESCE(tat_days,0)) d FROM products "
                       "GROUP BY stage"):
        exp[r["stage"]] = r["d"] or None
    for stage, days in exp.items():
        c.execute("UPDATE project_stages SET expected_days=? WHERE stage=?",
                  (days, stage))


# ── the findings that used to be one paragraph ───────────────────────────────
# The review, %(S)s4.2: "During one visit, 5 separate problems may be identified."
# Before this a visit carried a single `findings` text blob, so five problems
# were one row, with one owner and one status, and nothing could be assigned or
# closed independently. These are the same site observations, structured.
# (category, title, description, location, team, priority, nc)
FINDING_SET = [
 ("Structural", "Column C-14 rebar congestion at raft level",
  "Bar spacing at the raft/column junction is tighter than S-201 Rev C allows. "
  "Vibrator cannot pass; risk of honeycombing.",
  "Basement 2, grid C-14", "Structure", "Critical", 1),
 ("MEP coordination", "Corridor ceiling void 320mm against 400mm required",
  "The coordinated duct route needs 400mm. As built the void is 320mm, so the "
  "main supply duct cannot pass at the corridor crossing.",
  "Level 7, corridor at grid F", "MEP", "High", 1),
 ("Architectural finish", "Lobby marble joint width and shade variation",
  "Laid joint is 3mm against the 1.5mm approved mock-up, and shade varies "
  "visibly across three crates.",
  "Ground floor lobby", "Architecture", "High", 1),
 ("Waterproofing", "Planter junction detail not per approved drawing",
  "Membrane is terminated flush instead of being turned up 150mm at the planter "
  "upstand, per detail A-401/7.",
  "Level 3 terrace planter", "Architecture", "High", 1),
 ("Safety", "Edge protection missing at slab perimeter",
  "No handrail or toe board along the eastern slab edge where the facade is not "
  "yet installed.",
  "Level 9, east elevation", "Architecture", "Critical", 0),
 ("Dimensional", "Shear wall thickness 250mm against 300mm on drawing",
  "Measured thickness is 250mm. S-401 Rev B shows 300mm for this wall.",
  "Basement 1, core wall W-3", "Structure", "Critical", 1),
 ("Material", "Sanitary fixtures delivered are not the approved model",
  "Delivered fixtures differ from the MAR-approved model. No variation was raised.",
  "Level 4-6 apartment bathrooms", "MEP", "Medium", 1),
 ("Documentation", "Two MEP service penetrations not shown on the issued set",
  "Penetrations exist on site but appear on no issued drawing, so the as-built "
  "will not reconcile.",
  "Basement 1 blockwork", "MEP", "Medium", 0),
 ("Architectural finish", "Plaster undulation exceeds tolerance",
  "Straight-edge check shows more than 5mm deviation over 2m on several bays.",
  "Level 5, unit 502", "Architecture", "Low", 0),
 ("Structural", "Slab reinforcement inspected, no deviation found",
  "Joint inspection with QA/QC against S-301 Rev C. Cover, spacing and laps all "
  "within tolerance.",
  "Level 6-9 typical slab", "Structure", "Low", 0),
]


def _demo_priorities(c):
    """#5/#6: priority is business importance, separate from TAT. Deterministic
    spread so the queue has something to sort by, weighted by what the item is:
    an open NCR outranks a mood-board step."""
    order = ["Critical", "High", "Medium", "Low"]
    for i, r in enumerate(c.execute("SELECT id,type,status,value_pkr FROM cases").fetchall()):
        if r["type"] == "NCR":
            p = "Critical" if i %% 2 == 0 else "High"
        elif r["type"] in ("DCR", "VE", "BOQ"):
            p = "High" if (r["value_pkr"] or 0) >= PKR_CPC else "Medium"
        else:
            p = order[(i + 2) %% len(order)]
        c.execute("UPDATE cases SET priority=? WHERE id=?", (p, r["id"]))
    # tasks: late ones matter more, external ones are not ours to prioritise
    c.execute("UPDATE tasks SET priority='High' WHERE is_external=0 AND status!='done' "
              "AND baseline_days IS NOT NULL AND own_days > baseline_days")
    c.execute("UPDATE tasks SET priority='Low' WHERE is_external=1")
    c.execute("UPDATE tasks SET due_on=planned_ed WHERE due_on IS NULL")
    for r in c.execute("SELECT id,sla_days FROM coordination").fetchall():
        c.execute("UPDATE coordination SET priority=? WHERE id=?",
                  ("High" if (r["sla_days"] or 99) <= 3 else "Medium", r["id"]))


def _demo_crossteam(c):
    """#1/#2/#3/#4: cross-team requests, with a real thread and a real
    escalation, because an empty collaboration surface proves nothing."""
    if c.execute("SELECT COUNT(*) FROM cases WHERE type='CTR'").fetchone()[0]:
        return
    pr = {r["name"]: (r["id"], r["code"]) for r in
          c.execute("SELECT id,name,code FROM projects WHERE is_bau=0")}
    asks = [
        ("Zameen Opal", "Project Management", "High", 3,
         "Confirm basement commencement date so IFC Phase I can be sequenced",
         "We need the date to sequence the IFC Phase I release. Without it the "
         "contractor is working to a superseded programme.",
         [("update", "Project Management",
           "Received. Checking with the contractor's programme team."),
          ("question", "Project Management",
           "Is the ramp gradient DCR going to change the basement sequence?"),
          ("answer", "Architecture",
           "No %(D)s DCR-ZJ-104 is corridor ceiling, not the ramp. Basement "
           "sequence is unaffected.")], 1, 0),
        ("Mall 35", "Legal", "Critical", 5,
         "Title and easement confirmation for the eastern boundary setback",
         "The authority has queried the setback. We need the easement position "
         "confirmed in writing before we can respond.",
         [("update", "Legal", "Pulling the title documents from the file.")], 1, 0),
        ("Grande Palladium", "Supply Chain", "High", 5,
         "Vendor quotes for the third-party structural vetting engagement",
         "VET-GP-101 cannot move to CPC without three quotes.",
         [], 0, 2),
        ("Zameen Aurum", "QA/QC", "Medium", 3,
         "Joint re-inspection of the lobby marble mock-up after rectification",
         "Contractor reports rectification complete. Need a joint inspection "
         "before the finding can be closed.",
         [("update", "QA/QC", "Booked for Thursday with the site engineer.")], 1, 0),
        ("Zameen Neo", "Finance", "Medium", 5,
         "Budget confirmation for the additional 3D render package",
         "Zameen Studios have quoted for the extra 4K exteriors. Need the budget "
         "line confirmed.",
         [], 0, 1),
    ]
    for i, (pname, to_team, prio, tat, title, body, thread, acked, esc) in enumerate(asks):
        pid, code = pr[pname]
        raised = (today() - datetime.timedelta(days=4 + i * 3)).isoformat()
        cid, ref = open_case(c, "CTR", pid, code, title, None, "Ahmed Khan",
                             raised, body, position=1 if acked else 1,
                             priority=prio, tat_days=tat,
                             from_team="Architecture", to_team=to_team)
        if acked:
            when = (datetime.date.fromisoformat(raised)
                    + datetime.timedelta(days=1)).isoformat() + "T11:20:00"
            c.execute("UPDATE cases SET acknowledged_at=?,ack_by=? WHERE id=?",
                      (when, to_team + " coordinator", cid))
            c.execute("INSERT INTO case_messages(case_id,kind,body,who,who_team,"
                      "who_tier,at) VALUES(?,'ack',?,?,?,?,?)",
                      (cid, "Acknowledged.", to_team + " coordinator", to_team, 2, when))
        for k, (kind, team, msg) in enumerate(thread):
            c.execute("INSERT INTO case_messages(case_id,kind,body,who,who_team,"
                      "who_tier,at) VALUES(?,?,?,?,?,?,?)",
                      (cid, kind, msg, team + " lead" if team != "Architecture"
                       else "Ahmed Khan", team, 2,
                       (datetime.date.fromisoformat(raised)
                        + datetime.timedelta(days=2 + k)).isoformat() + "T14:05:00"))
        if esc:
            levels = ["Line Manager", "Senior Manager", "Department Head"]
            c.execute("UPDATE cases SET escalation_level=?,escalated_at=?,escalated_to=?,"
                      "escalated_by=?,escalation_reason=? WHERE id=?",
                      (esc, now(), levels[min(esc, 2) - 1] + ", " + to_team,
                       "Haroon Noon",
                       "No acknowledgement inside the agreed window and the item is "
                       "blocking a stage gate.", cid))
            c.execute("INSERT INTO case_messages(case_id,kind,body,who,who_team,"
                      "who_tier,at) VALUES(?,'escalation',?,?,?,0,?)",
                      (cid, "Escalated to " + levels[min(esc, 2) - 1] + " %(D)s no "
                       "acknowledgement inside the window.", "Haroon Noon",
                       "Architecture", now()))
''' % {"S": S, "D": D}

sub("\ndef _demo_intake(c):", NEW + "\n\ndef _demo_intake(c):")

open(PATH, "w", encoding="utf-8").write(src)
print("store.py: CTR + ESC routes, dynamic lanes, settings/dept/priority/thread seeds")
