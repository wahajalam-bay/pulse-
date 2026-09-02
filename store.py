#!/usr/bin/env python3
"""ZD PULSE — the store: schema, seed, and the derivation engine.

DESIGN NOTES THAT MATTER

1. THE TWO CLOCKS.  Every task and every case lane carries own_days and wait_days
   separately, split at the moment of handoff rather than computed afterwards.
   This is the single most important invariant in the system. Without it, a team
   waiting eight weeks on a geotech vendor looks exactly like a team that did
   nothing for eight weeks, and Structure gets blamed for the Finance department's
   payment cycle. Bayut Studios never needed this because its work never left the
   building; ZD's work leaves the building constantly.

2. THE CASE ENGINE.  MAR, DCR, RFI, shop-drawing approval and vetting are not five
   features. They are one object with five route definitions (see ROUTES). A lane
   whose owner is outside Arch & Design is marked external and is *stubbed*: it
   holds the clock and records the wait, but nobody signs in to action it. When the
   PM system arrives, the stub becomes a live lane and nothing else changes.

3. DERIVED, NEVER STORED.  Day counts, SLA variance and status are computed on read
   from the typed fields plus the working calendar. Storing a derived figure is how
   a dashboard ends up disagreeing with the data it is drawn from — the same rule
   PULSE's SCHEMA.md argues for, and for the same reason.

4. WORKING DAYS.  tat_days from the booklet are working days. The booklet never says
   so; this is an assumption, flagged in the UI, and the single place to change it if
   Ahmed rules otherwise is WORKDAYS_PER_WEEK / _add_working_days below.
"""
import os, sqlite3, json, datetime, hashlib, secrets

import catalog

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "zd.db")

WORKDAYS_PER_WEEK = 5          # Mon-Fri. See note 4.
PKR_CPC = 500_000              # SC Manual §4.3.2 / §18 — CPC threshold
PKR_CEO = 1_500_000            # SC Manual §18 — Office of CEO
PKR_PETTY = 15_000             # SC Manual §4.5 — petty cash ceiling


# ── case routes ──────────────────────────────────────────────────────────────
# Each lane: (label, owner_lane, sla_days). owner_lane outside TEAMS == stubbed.
# Sources are cited because these routes ARE the manuals; if a manual changes,
# this table changes and nothing else does.
ROUTES = {
    "DCR": {
        "label": "Design Change Request",
        "source": "Design Manual §14",
        "value_routed": True,
        "lanes": [
            ("Raised (RFI / site / scope)", "PM", 0),
            ("Design technical review", "Architecture", 3),
            ("QS cost evaluation", "PM", 5),
            ("Director Projects review", "PM", 2),
            ("Audit review", "Audit", 3),
            ("CFT review", "CFT", 3),
            ("Head ZD approval", "Head ZD", 2),
            ("Revised IFC issuance", "Architecture", 5),
        ],
    },
    "MAR": {
        "label": "Material Approval Request",
        # NOTE: three manuals define MAR differently (Design §11, PM §5.3, SC §4.2).
        # This route implements PM §5.3 — the joint Design/QAQC/PM vetting — because
        # it is the only one that names Design as an actor. Flagged for arbitration.
        "source": "PM Manual §5.3  (conflicts with Design §11 and SC §4.2)",
        "value_routed": True,
        "lanes": [
            ("Contractor submission + data sheets", "Contractor", 0),
            ("Design review", "Architecture", 3),
            ("QA/QC review", "QA/QC", 3),
            ("PM sign-off", "PM", 2),
            ("Procurement / CPC", "Supply Chain", 5),
        ],
    },
    "RFI": {
        "label": "Request For Information",
        "source": "Design Manual §14 initiation",
        "value_routed": False,
        "lanes": [
            ("Raised by contractor / site", "Contractor", 0),
            ("Design technical review", "Architecture", 2),
            ("Coordination with Structure / MEP", "Structure", 2),
            ("Response issued", "Architecture", 1),
        ],
    },
    "SHOP": {
        "label": "Shop Drawing Approval",
        "source": "Design Manual §13",
        "value_routed": False,
        "lanes": [
            ("Contractor submission", "Contractor", 0),
            ("Design review against IFC intent", "Architecture", 5),
            ("QA/QC concurrence", "QA/QC", 3),
            ("Approved / returned for correction", "Architecture", 1),
        ],
    },
    "VET": {
        "label": "Third-Party Vetting Engagement",
        "source": "Design Manual §7 (ZD-002)",
        "value_routed": True,
        "lanes": [
            ("Design request for vetting", "Architecture", 2),
            ("Audit scope finalisation", "Audit", 3),
            ("Head ZD scope approval", "Head ZD", 2),
            ("Vendor identification", "Audit", 5),
            ("Quotes via Supply Chain", "Supply Chain", 7),
            ("CPC final cost approval", "CFT", 3),
            ("Consultant review", "Third Party Vendor", 21),
            ("Design modification & BOQ revision", "Architecture", 10),
        ],
    },
    "VE": {
        "label": "Value Engineering Proposal",
        "source": "Design Manual §8",
        "value_routed": True,
        "stage": 10,
        "lanes": [
            ("VE trigger — tender cost over budget", "PM", 0),
            ("Design option study", "Architecture", 7),
            ("Structure & MEP implication check", "Structure", 3),
            ("QS cost comparison per option", "PM", 5),
            ("CFT review and shortlist", "CFT", 3),
            ("Head ZD decision", "Head ZD", 2),
            ("Incorporated into tender drawings and BOQ", "Architecture", 7),
        ],
    },
    "NCR": {
        "label": "Non-Conformance Report",
        # The one route that starts OUTSIDE the department and ends inside it.
        # A site visit that finds non-compliance raises this automatically.
        "source": "Design Manual §16 (QA/QC coordination)",
        "value_routed": False,
        "stage": 13,
        "lanes": [
            ("Raised on site against approved IFC", "QA/QC", 0),
            ("Design assessment — deviation or acceptable", "Architecture", 2),
            ("Corrective design instruction issued", "Architecture", 3),
            ("Contractor rectification", "Contractor", 10),
            ("Joint re-inspection", "QA/QC", 2),
            ("Close-out and register update", "Architecture", 1),
        ],
    },
    "BOQ": {
        "label": "BOQ Endorsement",
        "source": "Design Manual §10",
        "value_routed": True,
        "stage": 10,
        "lanes": [
            ("QS take-off from the tender set", "PM", 10),
            ("Architecture quantity and specification check", "Architecture", 3),
            ("Structure quantity check", "Structure", 3),
            ("MEP quantity check", "MEP", 3),
            ("Head ZD endorsement", "Head ZD", 2),
            ("Released to Supply Chain for tender", "Supply Chain", 1),
        ],
    },
    "SMP": {
        "label": "Material Sample & Mock-up",
        "source": "Design Manual §12",
        "value_routed": False,
        "stage": 12,
        "lanes": [
            ("Sample submitted by contractor", "Contractor", 0),
            ("Design review against the approved mood board", "Architecture", 3),
            ("Mock-up unit construction", "Contractor", 14),
            ("Joint inspection with QA/QC", "QA/QC", 2),
            ("Approved into the material archive", "Architecture", 1),
        ],
    },
    "CTR": {
        "label": "Cross-Team Request",
        # The gap the review opened with: a case could only travel a route that
        # was decided in advance, so "raise this to Legal" had nowhere to go and
        # the conversation left the system. The route is the same engine; what is
        # new is that two of its lanes are bound to teams CHOSEN WHEN IT IS
        # RAISED. @FROM and @TO are substituted in open_case().
        "source": "Haroon review 1 Sep §2.1 — cross-team collaboration",
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
        # §16: "Collaboration should not be limited to junior employees."
        # An escalation is not a nastier email, it is a case with a named senior
        # person on it and a clock, so the fact that it had to be escalated at
        # all becomes a number.
        "source": "Haroon review 1 Sep §16 — senior-management collaboration",
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
    "ABD": {
        "label": "As-Built & Closeout",
        "source": "Design Manual §18",
        "value_routed": False,
        "stage": 14,
        "lanes": [
            ("As-built markups from contractor", "Contractor", 0),
            ("Architecture as-built compilation", "Architecture", 15),
            ("Structure as-built compilation", "Structure", 10),
            ("MEP as-built compilation", "MEP", 10),
            ("Design verification against site", "Architecture", 5),
            ("QA/QC concurrence", "QA/QC", 3),
            ("Handover to PM and Property Management", "PM", 2),
        ],
    },
}

for _k, _v in ROUTES.items():
    _v.setdefault("stage", 13)

INTERNAL_LANES = set(catalog.TEAMS)


def is_stub(lane):
    """True when the lane belongs to a department whose system does not exist yet."""
    return lane not in INTERNAL_LANES


# ── obligations ──────────────────────────────────────────────────────────────
# The recurring commitments the Manual makes. PULSE has no recurrence concept at
# all, so this is genuinely new. These are what turn the SOP from a PDF into
# something with a due date and a miss count.
OBLIGATIONS = [
    ("weekly_review",  "Weekly Design Review Meeting", "weekly",  "per_project",
     "Design Manual §9"),
    ("site_visit",     "Monthly site visit",            "monthly", "per_project",
     "Design Manual §15"),
    ("compliance",     "Monthly Design Compliance Report", "monthly", "per_project",
     "Design Manual §15"),
    ("material_archive", "Annual approved-material archive", "yearly", "department",
     "Design Manual §12"),
    ("llr_review", "Quarterly lessons-learned review", "quarterly", "department",
     "Design Manual §7.6"),
]


# ── the stage checklist template ─────────────────────────────────────────────
# Manual §4.2 lists an "Internal Checklist Annexure" and then says "(to be
# added)". It does not exist in any document supplied. Sign-off was therefore
# mandatory against content nobody had written — which is how a mandatory gate
# becomes a signature on an empty page.
#
# These are that annexure, authored from what the Manual and the booklet already
# require elsewhere: every item traces to a section or to a step in the swimlane.
# They are a STARTING POSITION for Ahmed and Haroon to edit in-system, not a
# claim about what the department decided. The point is that the gate now has
# content, and that a lesson learned can add to it permanently (§7.6).
CHECKLIST_TEMPLATE = [
 (1,  "Acquisition pack received and logged against the intake table",
      "Manual §3.1"),
 (1,  "Regulatory data, land area and plot size confirmed in writing",
      "Manual §3.1 intake fields 1-2"),
 (2,  "EPC and IRR assumptions recorded with the feasibility owner named",
      "Manual §3"),
 (2,  "Management approval to proceed minuted and dated", "Manual §3.4 gate"),
 (3,  "Site analysis reconciled with the acquisition survey", "Booklet 3.1"),
 (3,  "By-laws and ground coverage checked against the intake regulatory field",
      "Manual §3.1 / Booklet 3.2"),
 (3,  "Zoning confirmed for the intended inventory mix", "Booklet 3.3"),
 (3,  "Initial column grid shared with Structure and acknowledged", "Booklet 3.5"),
 (3,  "Area statement reconciled with the approved inventory mix", "Booklet 3.7"),
 (4,  "Column grid and beam drops received from Structure and incorporated",
      "Booklet 4.2"),
 (4,  "Service and duct routes received from MEP and incorporated", "Booklet 4.3"),
 (4,  "Clash review held with both disciplines and minuted", "Manual §9"),
 (5,  "Basement services layout coordinated with MEP", "Booklet 5.1"),
 (5,  "Elevations and sections consistent with the approved massing", "Booklet 5.6"),
 (5,  "Inventory mix and area calculations re-issued after the final layout",
      "Booklet 5.8"),
 (5,  "Stakeholder feedback log closed with a dated response", "Booklet 5.10"),
 (6,  "Renders match the signed-off design, not a later revision", "Booklet 6.4"),
 (6,  "External render vendor deliverable received and checked", "Booklet 6.5"),
 (7,  "Area statement identical across Architecture, Structure and MEP sheets",
      "Manual §7"),
 (7,  "Every sheet signed and stamped by the licensed professional", "Booklet 7.7"),
 (7,  "In-house structural stability ownership recorded before submission",
      "Booklet Structure 7"),
 (7,  "Submission letter and drawing list filed in the authority register",
      "Manual §7"),
 (8,  "Mood board approved by the stakeholder and dated", "Booklet 8.4"),
 (9,  "Collateral content signed off by Creative and the project lead",
      "Booklet 9"),
 (10, "Specification schedule complete for every finish shown", "Manual §10"),
 (10, "Value engineering decisions incorporated or formally closed",
      "Manual §8"),
 (10, "BOQ endorsed by Head ZD before release to Supply Chain", "Manual §10"),
 (11, "All open RFIs affecting grey structure closed", "Manual §14"),
 (11, "Structure and MEP IFC sets cross-checked against Architecture",
      "Manual §5"),
 (11, "Drawing register updated with the IFC revision of every sheet issued",
      "Manual §5"),
 (11, "IFC Phase I issued before basement commencement", "Manual §5"),
 (12, "Mood board approved and the finishing schedule frozen", "Manual §12"),
 (12, "Mock-up units inspected and approved jointly with QA/QC", "Manual §12"),
 (12, "Approved-material archive updated for every finishing item",
      "Manual §12"),
 (13, "Monthly site visit logged with findings", "Manual §15"),
 (13, "Every NCR raised carries a dated design response", "Manual §16"),
 (13, "Shop drawings reviewed against IFC intent within the published SLA",
      "Manual §13"),
 (14, "As-built set verified against the site condition", "Manual §18"),
 (14, "As-built transmittal issued to PM and Property Management",
      "Manual §18"),
 (14, "O&M manuals and warranty pack acknowledged", "Manual §18"),
 (14, "Lessons learned reviewed and promoted into the stage checklists",
      "Manual §7.6"),
]



# ── settings access ─────────────────────────────────────────────────────────
# Every calculation goes through here. If a number in this system can be
# questioned, the answer has to be "because this setting says so, and here is
# who confirmed it" — not "because it is in the code".
def setting(c, key, default=None):
    r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r and r["value"] is not None else default


def setting_int(c, key, default=0):
    try:
        return int(float(setting(c, key, default)))
    except (TypeError, ValueError):
        return default


def setting_bool(c, key, default=False):
    v = setting(c, key, "1" if default else "0")
    return str(v).strip() in ("1", "true", "yes", "on")


def setting_list(c, key, default=""):
    return [x.strip() for x in (setting(c, key, default) or "").split("|") if x.strip()]


def priorities(c):
    return setting_list(c, "priority.levels", "Critical|High|Medium|Low")


def priority_rank(c, p):
    ps = priorities(c)
    return ps.index(p) if p in ps else len(ps)


def unconfirmed(c):
    """The definitions still waiting on the business. Shown, not hidden."""
    return [dict(r) for r in c.execute(
        "SELECT * FROM settings WHERE confirmed=0 ORDER BY section, key")]


# ── acknowledgement due (§3, and §36 A is why this is not a constant) ────────
def ack_due(c, from_iso=None):
    """When a cross-team request must have been acknowledged by.

    The unit is a SETTING, because the review left it open and the three
    readings give three different answers for anything raised on a Friday.
    """
    start = datetime.datetime.fromisoformat(from_iso) if from_iso else datetime.datetime.now()
    n = setting_int(c, "ack.window_value", 24)
    unit = setting(c, "ack.window_unit", "calendar_hours")
    if unit == "working_days":
        return datetime.datetime.combine(
            _add_working_days(start.date(), max(n // 24, 1)), start.time())
    if unit == "business_hours":
        h0 = setting_int(c, "ack.business_day_start", 9)
        h1 = setting_int(c, "ack.business_day_end", 18)
        span = max(h1 - h0, 1)
        cur, left = start, n
        while left > 0:
            if cur.weekday() < 5 and h0 <= cur.hour < h1:
                step = min(left, h1 - cur.hour)
                cur += datetime.timedelta(hours=step)
                left -= step
            else:
                cur += datetime.timedelta(hours=1)
        return cur
    return start + datetime.timedelta(hours=n)


def ack_overdue(c, row):
    if not row or row["acknowledged_at"] or not row["ack_due_at"]:
        return False
    try:
        return datetime.datetime.fromisoformat(row["ack_due_at"]) < datetime.datetime.now()
    except ValueError:
        return False


# ── delivery time (§29 / §30 / §36 F) ────────────────────────────────────
def delivery_exclusions(c):
    """What comes OUT of delivery time. §30 asked for MD approval to be removed;
    the rest are switches because §36 F says confirm the full list first."""
    out = []
    if setting_bool(c, "delivery.exclude_md_approval", True):
        out.append("md_approval")
    if setting_bool(c, "delivery.exclude_director_approval", False):
        out.append("approval")
    if setting_bool(c, "delivery.exclude_external", True):
        out.append("wait_external")
    if setting_bool(c, "delivery.exclude_hold", True):
        out.append("hold")
    return out


def log_time(c, entity, eid, category, days, from_on=None, to_on=None,
             party=None, note=None, who=None):
    c.execute("INSERT INTO time_log(entity,entity_id,category,days,from_on,to_on,"
              "party,note,who,at) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (entity, eid, category, days, from_on, to_on, party, note, who, now()))


def log_priority(c, entity, eid, old, new, reason, who, tier):
    c.execute("INSERT INTO priority_log(entity,entity_id,old_priority,new_priority,"
              "reason,who,who_tier,at) VALUES(?,?,?,?,?,?,?,?)",
              (entity, eid, old, new, reason, who, tier, now()))


def open_case(c, typ, project_id, code, title, value=None, raised_by="system",
              raised_at=None, note="", position=0, origin=None,
              priority=None, tat_days=None, from_team=None, to_team=None,
              origin_entity=None, origin_id=None, ack=True):
    """Instantiate a case on its route. One function, ten route types.

    Used by the write layer AND by anything that raises a case as a CONSEQUENCE
    of something else — a site visit that finds non-compliance raises an NCR
    here rather than leaving a flag on a row nobody reads.
    """
    route = ROUTES[typ]
    lanes = route["lanes"]
    if route.get("dynamic"):
        # Bind the placeholder lanes to the teams this particular request is
        # between. One route definition, every pair of departments.
        f = from_team or "Architecture"
        t = to_team or "Project Management"
        lanes = [(lbl.replace("@FROM", f).replace("@TO", t),
                  own.replace("@FROM", f).replace("@TO", t), sla)
                 for lbl, own, sla in lanes]
    n = c.execute("SELECT COUNT(*) FROM cases WHERE type=?", (typ,)).fetchone()[0]
    ref = "%s-%s-%d" % (typ, code or "ZD", 100 + n + 1)
    raised_at = raised_at or today().isoformat()
    priority = priority or setting(c, "priority.default", "Medium")
    tat = tat_days if tat_days is not None else sum(
        (l[2] or 0) for l in lanes) or None
    due = _add_working_days(datetime.date.fromisoformat(raised_at[:10]),
                            tat).isoformat() if tat else None
    ackdue = ack_due(c, raised_at if "T" in str(raised_at) else None).isoformat(
        timespec="seconds") if ack else None
    c.execute("INSERT INTO cases(ref,type,project_id,title,value_pkr,position,status,"
              "raised_by,raised_at,note,priority,tat_days,due_on,from_team,to_team,"
              "ack_due_at,origin_entity,origin_id) "
              "VALUES(?,?,?,?,?,?,'open',?,?,?,?,?,?,?,?,?,?,?)",
              (ref, typ, project_id, title, value, position, raised_by, raised_at, note,
               priority, tat, due, from_team, to_team, ackdue,
               origin_entity, origin_id))
    cid = c.execute("SELECT id FROM cases WHERE ref=?", (ref,)).fetchone()["id"]
    d = datetime.date.fromisoformat(raised_at[:10])
    for idx, (label, owner, sla) in enumerate(lanes):
        entered, left, outcome = None, None, None
        if idx < position:
            entered = d.isoformat()
            d = _add_working_days(d, max(sla or 1, 1))
            left, outcome = d.isoformat(), "passed"
        elif idx == position:
            entered = d.isoformat()
        c.execute("INSERT INTO case_lanes(case_id,idx,label,owner_lane,sla_days,"
                  "is_stub,entered_at,left_at,outcome) VALUES(?,?,?,?,?,?,?,?,?)",
                  (cid, idx, label, owner, sla, int(is_stub(owner)),
                   entered, left, outcome))
    if origin:
        c.execute("INSERT INTO notes(entity,entity_id,body,who,at) VALUES(?,?,?,?,?)",
                  ("case", cid, "Raised automatically from " + origin, raised_by, now()))
    return cid, ref


# ── the definitions that are NOT allowed to be constants ─────────────────────
# Haroon's review, §36: "The following points should not be hard-coded until the
# business definition is confirmed." Eight of them. So they live in the `settings`
# table, every calculation reads them, and each one ships carrying the QUESTION it
# is waiting on and `confirmed=0`. The screen says UNCONFIRMED until someone
# answers, which is the honest state — a number nobody has agreed is worse than a
# blank, because a blank does not get quoted in a board pack.
#
# (key, value, kind, section, label, question / note, options, doc_ref)
DEFINITIONS = [
 ("ack.window_value", "24", "int", "Acknowledgement",
  "Acknowledgement window",
  "How long a receiving team has to acknowledge a cross-team request.",
  "", "§3 / §36 A"),
 ("ack.window_unit", "calendar_hours", "choice", "Acknowledgement",
  "The window is measured in",
  "THE OPEN QUESTION: does 24 hours mean calendar hours, business hours, or "
  "working days? A request raised 4pm Friday is due 4pm Saturday on the first "
  "reading and Monday afternoon on the third. Nothing else in the system can be "
  "trusted until this is answered.",
  "calendar_hours|business_hours|working_days", "§36 A"),
 ("ack.business_day_start", "9", "int", "Acknowledgement",
  "Business day starts (hour)", "Only used if the window is business hours.",
  "", "§36 A"),
 ("ack.business_day_end", "18", "int", "Acknowledgement",
  "Business day ends (hour)", "Only used if the window is business hours.",
  "", "§36 A"),

 ("priority.levels", "Critical|High|Medium|Low", "list", "Priority",
  "Priority levels",
  "THE OPEN QUESTION: is this the right ladder? The review asked for configurable "
  "levels and gave this as an example, not a decision.",
  "", "§3 / §36 B"),
 ("priority.default", "Medium", "choice", "Priority",
  "Default priority for a new item", "",
  "Critical|High|Medium|Low", "§36 B"),
 ("priority.change_needs_reason", "1", "bool", "Priority",
  "Changing priority requires a stated reason",
  "The review asked for the historical record to survive a priority change. A "
  "change with no reason cannot be reviewed later.",
  "", "§3"),
 ("priority.who_can_change", "1", "int", "Priority",
  "Minimum tier that may change priority",
  "0 head → 1 senior manager → 2 lead → 3 member.",
  "", "§36 B"),

 ("scope.sla_applies_to", "External commitments — dates promised outside the department",
  "text", "SLA vs TAT",
  "SLA means", "THE OPEN QUESTION (§36 C): establish exactly where SLA applies.",
  "", "§36 C"),
 ("scope.tat_applies_to", "Internal turnaround — how long a team takes on its own step",
  "text", "SLA vs TAT",
  "TAT means",
  "§21 of the review: cross-team task timelines are TAT, not SLA. The wording is "
  "now TAT everywhere it describes a turnaround.",
  "", "§36 C / §21"),

 ("time.inprogress_definition",
  "Time the responsible team was actively working on the item",
  "text", "Time model", "In Progress means",
  "§27 of the review.", "", "§36 D"),
 ("time.wait_definition",
  "Time the item was waiting on another person, team or action",
  "text", "Time model", "Wait means", "§27 of the review.", "", "§36 D"),
 ("time.hold_definition",
  "Time progress was intentionally or externally blocked",
  "text", "Time model", "Hold / Blocking means", "§27 of the review.", "",
  "§36 D"),
 ("time.wait_counts_as_inprogress", "0", "bool", "Time model",
  "Count Wait as part of In Progress",
  "THE OPEN QUESTION, raised directly in §27: it was suggested Wait may need to "
  "count inside In Progress for some reporting. Off means SLA is judged on active "
  "execution only — the current behaviour. Turning it on changes every variance "
  "figure in the system, which is why it is a switch and not an opinion.",
  "", "§36 D"),
 ("time.own_time_means", "active_execution", "choice", "Time model",
  "Own Time represents",
  "THE OPEN QUESTION (§28 / §36 E): is Own Time active execution, or does it "
  "include time the item sat with us untouched? If the second, it overlaps Hold and "
  "the two must not be summed.",
  "active_execution|all_time_held_by_us", "§36 E"),

 ("delivery.exclude_md_approval", "1", "bool", "Delivery cycle",
  "Exclude MD approval time from Delivery Time",
  "§30 of the review asked for this specifically. Default on.",
  "", "§33 / §36 F"),
 ("delivery.exclude_director_approval", "0", "bool", "Delivery cycle",
  "Exclude Director approval time from Delivery Time",
  "§29: a Director's sign-off timing currently lands on the senior manager's "
  "delivery figure. Unresolved — the review did not say to exclude it, only that "
  "the calculation must distinguish it.",
  "", "§36 F"),
 ("delivery.exclude_external", "1", "bool", "Delivery cycle",
  "Exclude external dependency time from Delivery Time",
  "Time held by the Authority, a contractor or a vendor.", "", "§36 F"),
 ("delivery.exclude_hold", "1", "bool", "Delivery cycle",
  "Exclude Hold / blocking time from Delivery Time", "", "", "§36 F"),

 ("baseline.source", "booklet", "choice", "SLA baseline",
  "Which document is the TAT baseline",
  "THE BLOCKING ONE (§22 / §26 / §36 G). Booklet Vol.1 and Guidelines Manual "
  "§4.0 disagree on six of the ten architecture stages, and the Manual disagrees "
  "with its own flowcharts on three. Ahmed rules. Until then this records the "
  "working assumption and the Workflow Catalogue rail shows every conflict. "
  "NOTE: changing this does not retrospectively re-baseline existing tasks — "
  "planned dates are stamped when a stage is initiated.",
  "booklet|manual", "§26 / §36 G"),

 ("escalation.levels", "Line Manager|Senior Manager|Department Head", "list",
  "Escalation", "Escalation ladder",
  "§16 of the review: collaboration cannot be limited to junior staff. This is "
  "who a missed acknowledgement climbs to, in order.",
  "", "§4 / §16"),
 ("escalation.on_ack_missed", "1", "bool", "Escalation",
  "Escalate automatically when the acknowledgement window is missed", "", "",
  "§4"),
 ("escalation.on_tat_breach", "1", "bool", "Escalation",
  "Escalate automatically when TAT is breached", "", "", "§4"),

 ("lessons.notify_head", "1", "bool", "Lessons learned",
  "A raised lesson is visible to the department head",
  "§11 of the review: Lesson → Head visibility → Audit visibility → repository.",
  "", "§15"),
 ("lessons.notify_audit", "1", "bool", "Lessons learned",
  "A raised lesson is visible to Audit / IA",
  "Audit is a named control in all four manuals.", "", "§15"),
 ("lessons.audit_from_status", "ruled", "choice", "Lessons learned",
  "Audit sees a lesson from this status onward",
  "Whether Audit sees raw lessons or only ruled ones is a governance choice.",
  "open|ruled|adopted", "§15"),
]


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS people (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, team TEXT NOT NULL,
  designation TEXT, email TEXT, role TEXT NOT NULL DEFAULT 'member',
  tier INTEGER NOT NULL DEFAULT 3, active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, code TEXT,
  kind TEXT, city TEXT, status TEXT NOT NULL DEFAULT 'Active',
  is_bau INTEGER NOT NULL DEFAULT 0, created_at TEXT
);

-- the spine. one row per (project, stage).
CREATE TABLE IF NOT EXISTS project_stages (
  project_id INTEGER NOT NULL REFERENCES projects(id),
  stage INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'not_started',   -- not_started|running|hold|done
  planned_start TEXT, planned_end TEXT,
  actual_start TEXT, actual_end TEXT,
  own_days INTEGER NOT NULL DEFAULT 0,          -- clock while ZD held it
  wait_days INTEGER NOT NULL DEFAULT 0,         -- clock while someone else held it
  wait_ext_days INTEGER NOT NULL DEFAULT 0,     -- #29: of which, outside ZD
  hold_days INTEGER NOT NULL DEFAULT 0,         -- #27: intentionally blocked
  expected_days INTEGER,                        -- #24: published TAT for the stage
  note TEXT,
  PRIMARY KEY (project_id, stage)
);

-- the catalog, imported from catalog.py. never hand-edited.
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY, team TEXT NOT NULL, workflow TEXT NOT NULL,
  stage INTEGER NOT NULL, seq INTEGER NOT NULL, step TEXT NOT NULL,
  tat_days INTEGER, lane TEXT NOT NULL, is_external INTEGER NOT NULL DEFAULT 0,
  maker INTEGER DEFAULT 0, checker INTEGER DEFAULT 0, rework INTEGER DEFAULT 0,
  variable INTEGER DEFAULT 0, gate INTEGER DEFAULT 0,
  tat_booklet TEXT, tat_manual TEXT, source TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  product_id INTEGER REFERENCES products(id),
  team TEXT NOT NULL, workflow TEXT, stage INTEGER, seq INTEGER,
  title TEXT NOT NULL, person_id INTEGER REFERENCES people(id),
  lane TEXT, is_external INTEGER NOT NULL DEFAULT 0,
  baseline_days INTEGER,
  planned_sd TEXT, planned_ed TEXT, actual_sd TEXT, actual_ed TEXT,
  own_days INTEGER NOT NULL DEFAULT 0, wait_days INTEGER NOT NULL DEFAULT 0,
  -- Backlog #28/#29: the matrix has to separate these. wait_days stays the
  -- total; wait_ext is the part held outside the department, so internal delay
  -- is wait_days - wait_ext_days and nobody is charged for the wrong one.
  wait_ext_days INTEGER NOT NULL DEFAULT 0,
  hold_days INTEGER NOT NULL DEFAULT 0,
  revision INTEGER NOT NULL DEFAULT 0,          -- the "Changes Required" loop
  status TEXT NOT NULL DEFAULT 'queued',        -- queued|running|waiting|hold|done
  priority TEXT NOT NULL DEFAULT 'Medium',      -- #5: not a substitute for TAT
  due_on TEXT,
  hold_reason TEXT, held_at TEXT,
  external_system TEXT, external_ref TEXT, external_url TEXT,   -- #24
  origin_entity TEXT, origin_id INTEGER,                        -- #36 linkage
  note TEXT, created_at TEXT, updated_at TEXT
);

-- the case engine: one table, five route types. see ROUTES.
CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY, ref TEXT UNIQUE,
  type TEXT NOT NULL, project_id INTEGER REFERENCES projects(id),
  title TEXT NOT NULL, value_pkr REAL,
  position INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'open',          -- open|approved|rejected|withdrawn
  raised_by TEXT, raised_at TEXT, closed_at TEXT, note TEXT,

  -- Backlog #5/#6: priority is business importance. TAT is time. They are NOT
  -- the same field and one must never stand in for the other.
  priority TEXT NOT NULL DEFAULT 'Medium',
  tat_days INTEGER, due_on TEXT,

  -- Backlog #1/#2/#3/#4/#20: a case can be raised AT another team, has to be
  -- acknowledged, can be talked about without being closed, and escalates when
  -- the acknowledgement is missed.
  from_team TEXT, to_team TEXT, to_person_id INTEGER REFERENCES people(id),
  line_manager_id INTEGER REFERENCES people(id),
  ack_due_at TEXT, acknowledged_at TEXT, ack_by TEXT,
  escalation_level INTEGER NOT NULL DEFAULT 0,
  escalated_at TEXT, escalated_to TEXT, escalated_by TEXT, escalation_reason TEXT,

  -- Backlog #24: the hook for PM/Asana. Nothing syncs yet, but an item can be
  -- pointed at its counterpart so the link is not recreated by hand later.
  external_system TEXT, external_ref TEXT, external_url TEXT,
  origin_entity TEXT, origin_id INTEGER            -- what produced this case
);

-- Backlog #2: the back-and-forth. "The receiving team should be able to provide
-- updates without closing the case." An update is therefore a message, not a
-- status change, and the thread is part of the case timeline.
CREATE TABLE IF NOT EXISTS case_messages (
  id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id),
  kind TEXT NOT NULL DEFAULT 'update',   -- update|question|answer|ack|escalation|decision
  body TEXT NOT NULL, who TEXT, who_team TEXT, who_tier INTEGER,
  at TEXT NOT NULL, seen_by TEXT
);

-- Backlog #5: priority changes during the lifecycle and the history survives.
CREATE TABLE IF NOT EXISTS priority_log (
  id INTEGER PRIMARY KEY, entity TEXT NOT NULL, entity_id INTEGER NOT NULL,
  old_priority TEXT, new_priority TEXT NOT NULL, reason TEXT,
  who TEXT, who_tier INTEGER, at TEXT NOT NULL
);

-- §36: the business definitions, editable, each carrying its own question.
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY, value TEXT, kind TEXT, section TEXT,
  label TEXT, note TEXT, options TEXT, doc_ref TEXT,
  confirmed INTEGER NOT NULL DEFAULT 0,
  confirmed_by TEXT, confirmed_at TEXT, updated_at TEXT, updated_by TEXT
);

-- Backlog #18: the organisation, so a lesson or a finding can belong to Legal.
CREATE TABLE IF NOT EXISTS departments (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1, head_person_id INTEGER REFERENCES people(id)
);

-- Backlog #7/#8/#9/#10: one visit, many findings. The review was explicit —
-- "a visit should not become one large unstructured record." Each finding is
-- independently categorised, evidenced, owned, timed and resolvable, and each
-- can become an RFI or a task without the visit itself moving.
CREATE TABLE IF NOT EXISTS findings (
  id INTEGER PRIMARY KEY,
  visit_id INTEGER REFERENCES site_visits(id),
  project_id INTEGER NOT NULL REFERENCES projects(id),
  seq INTEGER, category TEXT, title TEXT NOT NULL,
  description TEXT, location TEXT,
  responsible_team TEXT, person_id INTEGER REFERENCES people(id),
  priority TEXT NOT NULL DEFAULT 'Medium',
  tat_days INTEGER, due_on TEXT,
  status TEXT NOT NULL DEFAULT 'open',   -- open|assigned|in_progress|resolved|closed
  non_compliance INTEGER NOT NULL DEFAULT 0,
  raised_by TEXT, raised_at TEXT,
  resolution TEXT, resolved_by TEXT, resolved_at TEXT,
  case_id INTEGER REFERENCES cases(id),      -- became an RFI / NCR
  task_id INTEGER REFERENCES tasks(id),      -- became a task
  llr_id INTEGER REFERENCES llr(id),         -- became a lesson
  recurrence_of INTEGER REFERENCES findings(id)   -- #10: seen before
);

-- Backlog #27/#28/#30/#31: the time model, auditable. Columns carry the
-- rollup; this carries how it got there, so a disputed figure can be walked
-- back to the transition that produced it.
CREATE TABLE IF NOT EXISTS time_log (
  id INTEGER PRIMARY KEY, entity TEXT NOT NULL, entity_id INTEGER NOT NULL,
  category TEXT NOT NULL,   -- in_progress|wait_internal|wait_external|hold|approval|md_approval
  days REAL, from_on TEXT, to_on TEXT,
  party TEXT, note TEXT, who TEXT, at TEXT
);
CREATE TABLE IF NOT EXISTS case_lanes (
  id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id),
  idx INTEGER NOT NULL, label TEXT NOT NULL, owner_lane TEXT NOT NULL,
  sla_days INTEGER, is_stub INTEGER NOT NULL DEFAULT 0,
  entered_at TEXT, left_at TEXT, actor TEXT, outcome TEXT, note TEXT
);

-- cross-team asks. a VIEW over reality, but stored because the ask itself is the
-- object: who owes whom, since when. this is the ledger nobody has today.
CREATE TABLE IF NOT EXISTS coordination (
  id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id),
  stage INTEGER, from_team TEXT NOT NULL, to_lane TEXT NOT NULL,
  ask TEXT NOT NULL,
  -- Backlog #21/#25: this column is a TURNAROUND, so it is TAT. `sla_days` is
  -- kept as the physical name only because every existing row and query uses
  -- it; everything a person reads says TAT. Renaming the column is a migration
  -- for its own change, not a silent one buried in a feature.
  sla_days INTEGER,
  priority TEXT NOT NULL DEFAULT 'Medium',
  ack_due_at TEXT, acknowledged_at TEXT, ack_by TEXT,
  escalation_level INTEGER NOT NULL DEFAULT 0, escalated_at TEXT, escalated_to TEXT,
  opened_at TEXT NOT NULL, closed_at TEXT, closed_by TEXT, outcome TEXT,
  task_id INTEGER, case_id INTEGER
);

CREATE TABLE IF NOT EXISTS obligations (
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL,
  cadence TEXT NOT NULL, project_id INTEGER REFERENCES projects(id),
  due_on TEXT NOT NULL, done_at TEXT, done_by TEXT, evidence TEXT,
  source TEXT
);

-- append-only. "keep an eye on each action."
CREATE TABLE IF NOT EXISTS changes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, who TEXT, tier INTEGER,
  entity TEXT NOT NULL, entity_id INTEGER, action TEXT NOT NULL,
  summary TEXT, project TEXT, team TEXT, blocked INTEGER NOT NULL DEFAULT 0
);


-- ── the work surface: things people CREATE, not just read ──────────────────

-- Manual §3.1 — the intake table, field for field, each with a named source.
CREATE TABLE IF NOT EXISTS intake (
  project_id INTEGER PRIMARY KEY REFERENCES projects(id),
  regulatory TEXT, land_area TEXT, height TEXT, basements TEXT,
  inventory TEXT, seismic TEXT, mep TEXT,
  updated_at TEXT, updated_by TEXT
);

-- Manual §4.1 — mandatory per-stage checklist. §4.2's annexure is "(to be added)",
-- so the engine ships and the department authors the items in-system.
CREATE TABLE IF NOT EXISTS checklists (
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
  stage INTEGER NOT NULL, created_at TEXT, signed_at TEXT, signed_by TEXT
);
CREATE TABLE IF NOT EXISTS checklist_items (
  id INTEGER PRIMARY KEY, checklist_id INTEGER NOT NULL REFERENCES checklists(id),
  seq INTEGER, text TEXT NOT NULL, source TEXT,
  done INTEGER NOT NULL DEFAULT 0, done_by TEXT, done_at TEXT, note TEXT
);

-- Manual §5 — the drawing register and the transmittal. We track the register and
-- the ISSUANCE EVENT, not the files: file storage is a different product and they
-- already have a drive. The transmittal is the contractual fact.
CREATE TABLE IF NOT EXISTS drawings (
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
  number TEXT NOT NULL, title TEXT NOT NULL, discipline TEXT,
  revision TEXT NOT NULL DEFAULT 'A', status TEXT NOT NULL DEFAULT 'draft',
  link TEXT, stage INTEGER, superseded_by INTEGER,
  created_at TEXT, created_by TEXT
);
CREATE TABLE IF NOT EXISTS transmittals (
  id INTEGER PRIMARY KEY, ref TEXT UNIQUE,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  phase TEXT NOT NULL, issued_to TEXT NOT NULL, drawing_count INTEGER,
  note TEXT, issued_at TEXT, issued_by TEXT
);

-- Manual §15 — the monthly site visit, and the non-compliance it finds. This is
-- what the Monthly Design Compliance Report is generated FROM.
CREATE TABLE IF NOT EXISTS site_visits (
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
  visited_on TEXT NOT NULL, by_whom TEXT, findings TEXT,
  non_compliance INTEGER NOT NULL DEFAULT 0, photos INTEGER DEFAULT 0,
  created_at TEXT
);

-- comments on anything. the thing that currently lives in WhatsApp.
CREATE TABLE IF NOT EXISTS notes (
  id INTEGER PRIMARY KEY, entity TEXT NOT NULL, entity_id INTEGER NOT NULL,
  body TEXT NOT NULL, who TEXT, at TEXT
);


-- ── the registers the Manual assumes exist ─────────────────────────────────

-- Manual §4.2's annexure is "(to be added)". So the department authors it once,
-- per stage, HERE, and every project's checklist is stamped from the template at
-- stage initiation. A lesson promoted out of the LLR lands in this table, which
-- is what makes "we learned something" change what the next project is checked
-- against. That loop is the whole point of §7.6.
CREATE TABLE IF NOT EXISTS checklist_templates (
  id INTEGER PRIMARY KEY, stage INTEGER NOT NULL, seq INTEGER,
  text TEXT NOT NULL, source TEXT, llr_id INTEGER,
  added_by TEXT, added_at TEXT, active INTEGER NOT NULL DEFAULT 1
);

-- Manual §7.6 — the Lessons Learned Register. PM §8.3 defines a competing
-- process and neither document references the other; that conflict is recorded
-- on the entry rather than silently resolved.
CREATE TABLE IF NOT EXISTS llr (
  id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id),
  stage INTEGER, discipline TEXT, category TEXT,
  title TEXT NOT NULL, detail TEXT, impact TEXT,
  raised_by TEXT, raised_at TEXT, source TEXT,
  origin_entity TEXT, origin_id INTEGER,        -- what the lesson came out of
  status TEXT NOT NULL DEFAULT 'open',          -- open|ruled|adopted|rejected
  ruling TEXT, ruled_by TEXT, ruled_at TEXT,
  promoted_stage INTEGER, promoted_at TEXT, template_id INTEGER,

  -- Backlog #17: "SLA/TAT took too long" has to be answerable. Why, where, whose,
  -- internal or external, was there a dependency, what changes. A lesson that
  -- records only the symptom cannot drive an improvement.
  root_cause TEXT,
  delay_owner TEXT,          -- which team or party caused it
  delay_kind TEXT,           -- internal | external | dependency | process | none
  delay_days INTEGER,        -- how much TAT was lost
  dependency TEXT,
  preventive_action TEXT,
  improvement_status TEXT NOT NULL DEFAULT 'proposed',  -- proposed|agreed|in_progress|done|dropped
  improvement_owner TEXT, improvement_due TEXT, improvement_closed_at TEXT,

  -- Backlog #15: Lesson -> Head visibility -> Audit visibility -> repository
  head_dept TEXT, head_notified_at TEXT, audit_notified_at TEXT,
  origin_finding_id INTEGER REFERENCES findings(id),
  priority TEXT NOT NULL DEFAULT 'Medium'
);

-- The honest answer to "file upload": a link register that attaches to ANY
-- entity, versioned, with who attached it. They already have a drive; what they
-- do not have is a record of which file is the current one and what it belongs to.
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY, entity TEXT NOT NULL, entity_id INTEGER NOT NULL,
  project_id INTEGER REFERENCES projects(id),
  title TEXT NOT NULL, kind TEXT, link TEXT, revision TEXT DEFAULT 'A',
  superseded_by INTEGER, added_by TEXT, added_at TEXT
);

-- Manual §7 and §17 — the authority file. Submission, the wait, the
-- observations, the conditions attached to an approval. The clock on the
-- Authority is the longest one in the department and nobody totals it today.
CREATE TABLE IF NOT EXISTS authority (
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
  authority TEXT NOT NULL, kind TEXT NOT NULL,      -- submission|inspection|noc
  ref TEXT, title TEXT, stage INTEGER,
  submitted_on TEXT, submitted_by TEXT,
  status TEXT NOT NULL DEFAULT 'submitted',         -- submitted|observations|approved|rejected
  responded_on TEXT, observations TEXT, conditions TEXT, note TEXT,
  coordination_id INTEGER
);

-- Drawing revision history, and what was actually in each transmittal. A
-- transmittal with a COUNT on it is a number; a transmittal with the sheet list
-- and the revision of each sheet is the contractual fact §5 is talking about.
CREATE TABLE IF NOT EXISTS drawing_revs (
  id INTEGER PRIMARY KEY, drawing_id INTEGER NOT NULL REFERENCES drawings(id),
  revision TEXT NOT NULL, status TEXT, link TEXT, note TEXT,
  at TEXT, by_whom TEXT
);
CREATE TABLE IF NOT EXISTS transmittal_drawings (
  transmittal_id INTEGER NOT NULL REFERENCES transmittals(id),
  drawing_id INTEGER NOT NULL REFERENCES drawings(id),
  revision TEXT,
  PRIMARY KEY (transmittal_id, drawing_id)
);

CREATE INDEX IF NOT EXISTS ix_doc ON documents(entity, entity_id);
CREATE INDEX IF NOT EXISTS ix_find ON findings(project_id, status);
CREATE INDEX IF NOT EXISTS ix_find_visit ON findings(visit_id);
CREATE INDEX IF NOT EXISTS ix_msg ON case_messages(case_id);
CREATE INDEX IF NOT EXISTS ix_tlog ON time_log(entity, entity_id);
CREATE INDEX IF NOT EXISTS ix_plog ON priority_log(entity, entity_id);
CREATE INDEX IF NOT EXISTS ix_llr_pr ON llr(project_id, status);
CREATE INDEX IF NOT EXISTS ix_auth ON authority(project_id, status);
CREATE INDEX IF NOT EXISTS ix_tpl ON checklist_templates(stage, active);

CREATE INDEX IF NOT EXISTS ix_note ON notes(entity, entity_id);
CREATE INDEX IF NOT EXISTS ix_dwg ON drawings(project_id);

CREATE INDEX IF NOT EXISTS ix_task_proj ON tasks(project_id, stage);
CREATE INDEX IF NOT EXISTS ix_case_proj ON cases(project_id, status);
CREATE INDEX IF NOT EXISTS ix_coord_open ON coordination(closed_at);
"""


def conn():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def today():
    return datetime.date.today()


def _add_working_days(d, n):
    """Advance d by n working days. The one place the Mon-Fri assumption lives."""
    if n is None:
        return d
    out, added = d, 0
    while added < n:
        out += datetime.timedelta(days=1)
        if out.weekday() < 5:
            added += 1
    return out


def days_between(a, b):
    """Plain calendar days between two dates.

    Deliberately distinct from working_days_between: whether an overdue
    figure counts calendar or business days is one of the open definitions
    (§36-A), so neither silently stands in for the other.
    """
    if not a or not b:
        return None
    if isinstance(a, str): a = datetime.date.fromisoformat(a[:10])
    if isinstance(b, str): b = datetime.date.fromisoformat(b[:10])
    return max(0, (b - a).days)


def working_days_between(a, b):
    if not a or not b:
        return None
    if isinstance(a, str): a = datetime.date.fromisoformat(a[:10])
    if isinstance(b, str): b = datetime.date.fromisoformat(b[:10])
    if b < a:
        return 0
    n, cur = 0, a
    while cur < b:
        cur += datetime.timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return n


def log(c, who, tier, entity, entity_id, action, summary,
        project=None, team=None, blocked=0):
    c.execute("INSERT INTO changes(at,who,tier,entity,entity_id,action,summary,"
              "project,team,blocked) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (now(), who, tier, entity, entity_id, action, summary,
               project, team, blocked))


# ── seed ─────────────────────────────────────────────────────────────────────
# The eight named projects are the on-ground developments shown on the booklet's
# own cover page. The booklet says "12 On-ground Projects"; the remaining four are
# not named anywhere in the documents supplied, so they are NOT invented here.
# Confirming them is question 12 on the list for Haroon.
PROJECTS = [
    ("Zameen Opal",        "ZO",  "Residential", "Lahore"),
    ("Mall 35",            "M35", "Mixed Use",   "Islamabad"),
    ("Zameen Aurum",       "ZA",  "Residential", "Lahore"),
    ("Zameen Neo",         "ZN",  "Residential", "Lahore"),
    ("Zameen Jade",        "ZJ",  "Residential", "Lahore"),
    ("Zameen Quadrangle",  "ZQ",  "Mixed Use",   "Islamabad"),
    ("Grande Palladium",   "GP",  "Commercial",  "Lahore"),
    ("Golf View (Rumanza)","GV",  "Residential", "Multan"),
]

PEOPLE = [
    # (name, team, designation, tier)  tier 0 = head, 1 = sr manager, 2 = lead, 3 = member
    ("Haroon Noon", "Architecture", "Head of Architecture & Design", 0),
    ("Ahmed Khan", "Architecture", "Sr. Manager Architecture", 1),
    ("Umer Farooq", "Architecture", "Architect", 2),
    ("Ayesha Irshad", "Architecture", "Architect", 3),
    ("Wasiqa Tayyab", "Architecture", "Architect", 3),
    ("Khansa Nazir", "Architecture", "Architect", 3),
    ("Iqra Nadeem", "Architecture", "Architect", 3),
    ("Hammad Asghar", "Architecture", "Architect", 3),
    ("Arslan Aryan", "Architecture", "Architect", 3),
    ("Usman Akram", "Architecture", "Architect", 3),
    ("Haseeb Amjad", "Architecture", "Architect", 3),
    ("Talha Tajik", "Architecture", "Architect", 3),
    ("Kashif Aslam", "Architecture", "Draftsman", 3),
    ("Khurram Shahzad", "Architecture", "Draftsman", 3),
    ("Abdul Rehman", "Architecture", "Draftsman", 3),
    ("Waris Sadiq", "Architecture", "Draftsman", 3),
    ("Qamar Ali", "Architecture", "Draftsman", 3),
    ("Akhter Ud Din", "Architecture", "Draftsman", 3),
    ("Zaheer Azeem", "Architecture", "Draftsman", 3),
    ("Ikram Alivi", "Architecture", "Draftsman", 3),
    ("Nabeel Hamz A", "Architecture", "Draftsman", 3),

    ("Yahya Ali Khan", "MEP", "Sr. Manager MEP", 1),
    ("Muhammad Umar Khan", "MEP", "Lead Engineer", 2),
    ("Muhammad Ali Hassan", "MEP", "Project Design Engineer", 2),
    ("Rehan Shahid", "MEP", "Design Engineer", 3),
    ("Adeel Ahmad", "MEP", "Design Engineer", 3),
    ("Shahzeb Sarwar", "MEP", "Design Engineer", 3),
    ("Azhar Iqbal", "MEP", "Design Engineer", 3),
    ("Fahad Aziz", "MEP", "Design Engineer", 3),
    ("Mian Muhammad Adil Naeem", "MEP", "Design Engineer", 3),
    ("Waqas Aslam", "MEP", "Draftsman", 3),
    ("Muhammad Salman Athar", "MEP", "Draftsman", 3),
    ("Ayesha Nadeem", "MEP", "Design Engineer", 3),
    ("Muhammad Irfan", "MEP", "Draftsman", 3),

    ("Hafiz Rashid Khalid", "Structure", "Sr. Manager Structure", 1),
    ("Aarij Ali", "Structure", "Lead Engineer", 2),
    ("Tanveer Ahmed", "Structure", "Structural Engineer", 3),
    ("Istehsan Ur Rahim", "Structure", "Structural Engineer", 3),
    ("Muhammad Faisal", "Structure", "Structural Engineer", 3),
    ("Tanveer Shahid", "Structure", "Draftsman", 3),
    ("Rafaqat Ali", "Structure", "Draftsman", 3),

    ("Ali Aslam", "Creative", "Creative Lead", 1),
    ("Safina Sultan", "Creative", "Content Manager", 2),
    ("Basil Sohail Butt", "Creative", "Designer", 3),
    ("Maham Zahir Kayani", "Creative", "Content Writer", 3),
]


def seed(force=False):
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    fresh = force or not os.path.exists(DB)
    if force and os.path.exists(DB):
        os.remove(DB)
    c = conn()
    c.executescript(SCHEMA)
    if not fresh and c.execute("SELECT COUNT(*) FROM products").fetchone()[0]:
        c.commit(); c.close(); return

    # people
    for name, team, desig, tier in PEOPLE:
        first = name.split()[0].lower()
        c.execute("INSERT OR IGNORE INTO people(name,team,designation,email,role,tier)"
                  " VALUES(?,?,?,?,?,?)",
                  (name, team, desig, f"{first}@zameen.com",
                   "head" if tier == 0 else "manager" if tier <= 1 else
                   "lead" if tier == 2 else "member", tier))

    # projects
    for name, code, kind, city in PROJECTS:
        c.execute("INSERT OR IGNORE INTO projects(name,code,kind,city,status,created_at)"
                  " VALUES(?,?,?,?,'Active',?)", (name, code, kind, city, now()))
    # BAU carrier. Seven of Creative's twelve workflows have no building attached
    # (Zameen Times, campaigns, blogs, corporate branding, website, templates,
    # legal docs). tasks.project_id is NOT NULL, so rather than loosen the schema
    # for one team, department-level work hangs off one explicit BAU project. This
    # is a placeholder for a real decision — question 3 for Haroon.
    c.execute("INSERT OR IGNORE INTO projects(name,code,kind,city,status,is_bau,created_at)"
              " VALUES('Department BAU','BAU','Business as Usual','Lahore','Active',1,?)",
              (now(),))

    # catalog
    for r in catalog.flatten():
        c.execute("INSERT INTO products(team,workflow,stage,seq,step,tat_days,lane,"
                  "is_external,maker,checker,rework,variable,gate,tat_booklet,"
                  "tat_manual,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (r["team"], r["workflow"], r["stage"], r["seq"], r["step"],
                   r["tat_days"], r["lane"], int(r["is_external"]), int(r["maker"]),
                   int(r["checker"]), int(r["rework"]), int(r["variable"]),
                   int(r["gate"]), r["tat_booklet"], r["tat_manual"], r["source"]))

    # the spine: every real project gets all 13 stations
    for (pid,) in c.execute("SELECT id FROM projects WHERE is_bau=0").fetchall():
        for stage, _n, _p, _d in catalog.STAGES:
            c.execute("INSERT OR IGNORE INTO project_stages(project_id,stage) VALUES(?,?)",
                      (pid, stage))

    # §36 — the business definitions, every one shipped UNCONFIRMED
    for key, val, kind, section, label, note, opts, ref in DEFINITIONS:
        c.execute("INSERT OR IGNORE INTO settings(key,value,kind,section,label,note,"
                  "options,doc_ref,confirmed,updated_at,updated_by) "
                  "VALUES(?,?,?,?,?,?,?,?,0,?,?)",
                  (key, val, kind, section, label, note, opts, ref, now(), "system"))

    # #18 — the organisation, so a finding or a lesson can belong to Legal
    for name, kind in catalog.DEPARTMENTS:
        c.execute("INSERT OR IGNORE INTO departments(name,kind,active) VALUES(?,?,1)",
                  (name, kind))

    # the §4.2 annexure, authored once and stamped onto every stage checklist
    for stage, text, source in CHECKLIST_TEMPLATE:
        n = c.execute("SELECT COALESCE(MAX(seq),0) FROM checklist_templates "
                      "WHERE stage=?", (stage,)).fetchone()[0]
        c.execute("INSERT INTO checklist_templates(stage,seq,text,source,added_by,"
                  "added_at) VALUES(?,?,?,?,?,?)",
                  (stage, n + 1, text, source, "system", now()))

    log(c, "system", 0, "system", None, "seed",
        f"Seeded {len(PROJECTS)} projects, {len(PEOPLE)} people, "
        f"{len(catalog.flatten())} catalog steps, "
        f"{len(CHECKLIST_TEMPLATE)} stage-checklist template items, "
        f"{len(DEFINITIONS)} business definitions (all UNCONFIRMED), "
        f"{len(catalog.DEPARTMENTS)} departments")
    c.commit(); c.close()


# ── demo state ───────────────────────────────────────────────────────────────
def demo(c):
    """Put the 8 projects at believable, DIFFERENT points on the spine.

    Explicitly demo data, not real progress — every project here is marked so on
    screen. It exists so the stage matrix, the coordination ledger and the case
    inbox have something to show tomorrow rather than rendering empty.
    """
    if c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]:
        return

    # (project, stage reached, stage currently running)
    POS = {
        "Zameen Opal":        (12, 13),
        "Mall 35":            (10, 11),
        "Zameen Aurum":       (13, 13),
        "Zameen Neo":         (7,  8),
        "Zameen Jade":        (5,  5),
        "Zameen Quadrangle":  (3,  4),
        "Grande Palladium":   (11, 12),
        "Golf View (Rumanza)":(2,  3),
    }
    people = {r["team"]: [] for r in c.execute("SELECT DISTINCT team FROM people")}
    for r in c.execute("SELECT id,team FROM people WHERE tier>=2"):
        people.setdefault(r["team"], []).append(r["id"])

    prods = [dict(r) for r in c.execute("SELECT * FROM products")]
    start = today() - datetime.timedelta(days=420)
    rr = 0

    for r in c.execute("SELECT id,name FROM projects WHERE is_bau=0").fetchall():
        pid, pname = r["id"], r["name"]
        done_to, running = POS.get(pname, (3, 4))
        cursor = start

        for stage, sname, phase, _d in catalog.STAGES:
            if stage > running:
                break
            st = "done" if stage <= done_to else "running"
            steps = [p for p in prods if p["stage"] == stage]
            if not steps:
                c.execute("UPDATE project_stages SET status=?,actual_start=? "
                          "WHERE project_id=? AND stage=?",
                          (st, cursor.isoformat(), pid, stage))
                continue

            s_start, own, wait = cursor, 0, 0
            for p in steps:
                rr += 1
                base = p["tat_days"]
                psd = cursor
                ped = _add_working_days(psd, base or 2)
                ext = bool(p["is_external"])

                if st == "done":
                    # deliberate, deterministic drift so the SLA view has signal
                    drift = (rr % 7) - 2                    # -2..+4 days
                    asd = psd
                    aed = _add_working_days(ped, max(drift, -1))
                    took = working_days_between(asd, aed) or 0
                    if ext:
                        wait += took
                    else:
                        own += took
                    tstat, rev = "done", (1 if p["rework"] and rr % 5 == 0 else 0)
                else:
                    asd = psd if rr % 3 else None
                    aed = None
                    tstat = ("waiting" if ext else "running") if asd else "queued"
                    rev = 0
                    if asd:
                        took = working_days_between(asd, today()) or 0
                        if ext: wait += took
                        else:   own += took

                pool = people.get(p["team"]) or [None]
                c.execute(
                    "INSERT INTO tasks(project_id,product_id,team,workflow,stage,seq,"
                    "title,person_id,lane,is_external,baseline_days,planned_sd,planned_ed,"
                    "actual_sd,actual_ed,own_days,wait_days,revision,status,created_at,updated_at)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (pid, p["id"], p["team"], p["workflow"], stage, p["seq"], p["step"],
                     None if ext else pool[rr % len(pool)], p["lane"], int(ext),
                     base, psd.isoformat(), ped.isoformat(),
                     asd.isoformat() if asd else None,
                     aed.isoformat() if aed else None,
                     0 if ext else (working_days_between(asd, aed or today()) or 0) if asd else 0,
                     (working_days_between(asd, aed or today()) or 0) if (ext and asd) else 0,
                     rev, tstat, now(), now()))

                # an unclosed external step IS an open coordination ask
                if ext and tstat == "waiting":
                    c.execute("INSERT INTO coordination(project_id,stage,from_team,"
                              "to_lane,ask,sla_days,opened_at) VALUES(?,?,?,?,?,?,?)",
                              (pid, stage, p["team"], p["lane"], p["step"], base,
                               asd.isoformat()))
                cursor = aed or ped

            c.execute("UPDATE project_stages SET status=?,planned_start=?,planned_end=?,"
                      "actual_start=?,actual_end=?,own_days=?,wait_days=? "
                      "WHERE project_id=? AND stage=?",
                      (st, s_start.isoformat(), cursor.isoformat(),
                       s_start.isoformat(),
                       cursor.isoformat() if st == "done" else None,
                       own, wait, pid, stage))

    _demo_expected(c)
    _demo_intake(c)
    _demo_cases(c)
    _demo_obligations(c)
    _demo_registers(c)
    _demo_visits(c)
    _demo_llr(c)
    _demo_priorities(c)
    _demo_crossteam(c)
    c.commit()



def _demo_expected(c):
    """#24 of the review: the matrix must separate EXPECTED from actual. The
    expected duration is the catalog's own published TAT for the stage, summed
    over its steps — not a number anyone typed."""
    exp = {}
    for r in c.execute("SELECT stage, SUM(COALESCE(tat_days,0)) d FROM products "
                       "GROUP BY stage"):
        exp[r["stage"]] = r["d"] or None
    for stage, days in exp.items():
        c.execute("UPDATE project_stages SET expected_days=? WHERE stage=?",
                  (days, stage))


# ── the findings that used to be one paragraph ───────────────────────────────
# The review, §4.2: "During one visit, 5 separate problems may be identified."
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
            p = "Critical" if i % 2 == 0 else "High"
        elif r["type"] in ("DCR", "VE", "BOQ"):
            p = "High" if (r["value_pkr"] or 0) >= PKR_CPC else "Medium"
        else:
            p = order[(i + 2) % len(order)]
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
           "No — DCR-ZJ-104 is corridor ceiling, not the ramp. Basement "
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
                      (cid, "Escalated to " + levels[min(esc, 2) - 1] + " — no "
                       "acknowledgement inside the window.", "Haroon Noon",
                       "Architecture", now()))


def _demo_intake(c):
    """Manual §3.1. A project that is past stage 3 got through the §3.4 gate, so its
    intake is complete — leaving it blank would show a gate that had never fired.
    The two projects still at stages 2-4 keep an incomplete intake on purpose: that is
    where the refusal can be seen, and it is the truthful state for them."""
    seed = {
        "regulatory": "LDA by-laws 2019 · ground coverage 60% · FAR 1:5.5",
        "land_area":  "Plot 4 kanal 12 marla · 23,850 sq ft",
        "height":     "G+12 · 44.5 m to parapet",
        "basements":  "2 · raft at -8.4 m",
        "inventory":  "Apartments 1-3 bed + ground-floor retail",
        "seismic":    "Zone 2B (Lahore) · BCP SP-2007",
        "mep":        "Central chilled water · 2 × 1250 kVA · wet riser + sprinklers",
    }
    for r in c.execute("SELECT id,name FROM projects WHERE is_bau=0").fetchall():
        done, top = _reached(c, r["id"])
        cur = c.execute("SELECT * FROM intake WHERE project_id=?", (r["id"],)).fetchone()
        if cur:
            continue
        if top >= 5:
            c.execute("INSERT INTO intake(project_id,regulatory,land_area,height,"
                      "basements,inventory,seismic,mep,updated_at,updated_by) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (r["id"], seed["regulatory"], seed["land_area"], seed["height"],
                       seed["basements"], seed["inventory"], seed["seismic"],
                       seed["mep"], now(), "Acquisition / Legal"))
        else:
            # partial — the state the §3.4 gate actually refuses on
            c.execute("INSERT INTO intake(project_id,regulatory,land_area,updated_at,"
                      "updated_by) VALUES(?,?,?,?,?)",
                      (r["id"], seed["regulatory"], seed["land_area"], now(),
                       "Acquisition / Legal"))


def _demo_cases(c):
    rows = c.execute("SELECT id,name,code FROM projects WHERE is_bau=0").fetchall()
    seeds = [
        ("MAR", "Façade cladding — aluminium composite", 2_400_000, 1),
        ("MAR", "Lobby marble — Botticino", 780_000, 2),
        ("MAR", "Sanitary fixtures — apartment bathrooms", 410_000, 1),
        ("DCR", "Basement 2 ramp gradient revision", 1_650_000, 3),
        ("DCR", "Corridor ceiling height — MEP clash", 340_000, 1),
        ("DCR", "Facade fin spacing per VE proposal", 920_000, 5),
        ("RFI", "Column C-14 rebar congestion at raft", None, 1),
        ("RFI", "Waterproofing detail at planter junction", None, 2),
        ("RFI", "Door schedule mismatch — Type D3", None, 0),
        ("SHOP", "Aluminium window fabrication drawings", None, 1),
        ("SHOP", "MEP combined services — Level 7", None, 2),
        ("VET", "Structural superstructure vetting — IFC I&II", 3_500_000, 2),
    ]
    for i, (typ, title, val, pos) in enumerate(seeds):
        pr = rows[i % len(rows)]
        route = ROUTES[typ]
        ref = f"{typ}-{pr['code']}-{100+i}"
        raised = (today() - datetime.timedelta(days=6 + i * 3)).isoformat()
        c.execute("INSERT INTO cases(ref,type,project_id,title,value_pkr,position,"
                  "status,raised_by,raised_at) VALUES(?,?,?,?,?,?,'open',?,?)",
                  (ref, typ, pr["id"], title, val, pos, "Site / Contractor", raised))
        cid = c.execute("SELECT id FROM cases WHERE ref=?", (ref,)).fetchone()[0]
        d = datetime.date.fromisoformat(raised)
        for idx, (label, owner, sla) in enumerate(route["lanes"]):
            ent = d.isoformat() if idx <= pos else None
            left = None
            if idx < pos:
                d = _add_working_days(d, max(sla, 1))
                left = d.isoformat()
            c.execute("INSERT INTO case_lanes(case_id,idx,label,owner_lane,sla_days,"
                      "is_stub,entered_at,left_at,outcome) VALUES(?,?,?,?,?,?,?,?,?)",
                      (cid, idx, label, owner, sla, int(is_stub(owner)),
                       ent, left, "passed" if idx < pos else None))


def _demo_obligations(c):
    projs = c.execute("SELECT id FROM projects WHERE is_bau=0").fetchall()
    t = today()
    for kind, label, cadence, scope, src in OBLIGATIONS:
        if scope == "department":
            c.execute("INSERT INTO obligations(kind,label,cadence,project_id,due_on,source)"
                      " VALUES(?,?,?,NULL,?,?)",
                      (kind, label, cadence,
                       datetime.date(t.year, 12, 31).isoformat(), src))
            continue
        for n, p in enumerate(projs):
            if cadence == "weekly":
                for w in range(4):
                    due = t - datetime.timedelta(days=t.weekday() + 7 * w)
                    done = None if (w == 0 or (n + w) % 6 == 0) else \
                        (due + datetime.timedelta(days=1)).isoformat()
                    c.execute("INSERT INTO obligations(kind,label,cadence,project_id,"
                              "due_on,done_at,source) VALUES(?,?,?,?,?,?,?)",
                              (kind, label, cadence, p["id"], due.isoformat(), done, src))
            else:
                for m in range(3):
                    mm = (t.month - m - 1) % 12 + 1
                    yy = t.year - (1 if t.month - m - 1 < 0 else 0)
                    due = datetime.date(yy, mm, 28)
                    done = None if (m == 0 or (n + m) % 5 == 0) else \
                        (due + datetime.timedelta(days=2)).isoformat()
                    c.execute("INSERT INTO obligations(kind,label,cadence,project_id,"
                              "due_on,done_at,source) VALUES(?,?,?,?,?,?,?)",
                              (kind, label, cadence, p["id"], due.isoformat(), done, src))




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
    ("A-201", "Elevations — north and east",                 "Architecture", 5),
    ("A-202", "Sections A-A and B-B",                       "Architecture", 5),
    ("A-901", "Authority submission set",                   "Architecture", 7),
    ("A-301", "Core, staircase and lift details",           "Architecture", 10),
    ("A-401", "Finishing schedule and internal elevations", "Architecture", 12),
    ("S-101", "Raft foundation layout",                     "Structure", 5),
    ("S-201", "Column layout and schedule",                 "Structure", 5),
    ("S-301", "Typical slab reinforcement",                 "Structure", 10),
    ("S-401", "Retaining wall and ramp details",            "Structure", 11),
    ("E-101", "Power layout — typical floor",                "MEP", 4),
    ("M-101", "HVAC layout — typical floor",                 "MEP", 4),
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

        # ── the authority file (§7 / §17) ──
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
                       "Building plan approval — full submission set", 7,
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
    """Manual §15 and Haroon's review §4-§6.

    The old shape put every observation from a visit into one `findings` text
    column. The review killed it in one line: "A visit should not become one large
    unstructured record." Five problems found on one walk were one row, with one
    owner, one status and one clock — so four of them could not be assigned,
    timed or closed, and none could be shown to have happened before.

    Now: a visit is a container with a date and a person. Each finding is its own
    record with a category, a location, an owner, a priority, a TAT and evidence,
    and any finding can become an NCR or a task on its own. The visit summary is
    derived from its findings rather than being the place they hide.
    """
    if c.execute("SELECT COUNT(*) FROM site_visits").fetchone()[0]:
        return
    people = {}
    for r in c.execute("SELECT id,name,team FROM people WHERE tier<=2"):
        people.setdefault(r["team"], []).append((r["id"], r["name"]))
    visitors = ["Ahmed Khan", "Umer Farooq", "Aarij Ali", "Yahya Ali Khan"]

    k = 0
    for pr in c.execute("SELECT id,name,code FROM projects WHERE is_bau=0").fetchall():
        pid, code = pr["id"], pr["code"]
        _done, top = _reached(c, pid)
        if top < 11:
            continue
        seen = {}          # (category, location) -> earliest finding id, for #10
        for m in range(3):
            k += 1
            day = today() - datetime.timedelta(days=28 * m + 4)
            # The review's own example: "During one visit, 5 separate problems
            # may be identified." The most recent visit on the furthest-along
            # project is that visit.
            n_find = 5 if (m == 0 and top >= 13) else (1 + (k % 4))
            picks = [FINDING_SET[(k * 3 + i) % len(FINDING_SET)] for i in range(n_find)]
            nc_total = sum(1 for p in picks if p[6])
            c.execute("INSERT INTO site_visits(project_id,visited_on,by_whom,findings,"
                      "non_compliance,photos,created_at) VALUES(?,?,?,?,?,?,?)",
                      (pid, day.isoformat(), visitors[k % len(visitors)],
                       f"{n_find} finding{'s' if n_find != 1 else ''} recorded"
                       + (f", {nc_total} non-compliant" if nc_total else
                          ", none non-compliant"),
                       1 if nc_total else 0, 4 + (k % 11), now()))
            vid = c.execute("SELECT last_insert_rowid()").fetchone()[0]

            for i, (cat, title, desc, loc, team, prio, nc) in enumerate(picks):
                tat = {"Critical": 3, "High": 7, "Medium": 14, "Low": 21}[prio]
                due = _add_working_days(day, tat)
                pool = people.get(team) or [(None, None)]
                pid_person, _pname = pool[(k + i) % len(pool)]
                # oldest visits are mostly closed out; the newest are live
                if m >= 2:
                    st, res = "closed", "Rectified and verified on the following visit."
                elif m == 1:
                    st, res = ("resolved", "Contractor rectified; awaiting joint "
                               "re-inspection.") if i % 2 == 0 else ("in_progress", None)
                else:
                    st, res = ("assigned" if pid_person else "open"), None
                prev = seen.get((cat, loc))
                c.execute("INSERT INTO findings(visit_id,project_id,seq,category,title,"
                          "description,location,responsible_team,person_id,priority,"
                          "tat_days,due_on,status,non_compliance,raised_by,raised_at,"
                          "resolution,resolved_by,resolved_at,recurrence_of) "
                          "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (vid, pid, i + 1, cat, title, desc, loc, team, pid_person,
                           prio, tat, due.isoformat(), st, nc,
                           visitors[k % len(visitors)], day.isoformat(),
                           res, "Ahmed Khan" if res else None,
                           (day + datetime.timedelta(days=tat)).isoformat()
                           if res else None, prev))
                fid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                seen.setdefault((cat, loc), fid)

                # #8 — evidence stays attached to the FINDING, not the visit
                for kind, label in (("Photo set", "Site photographs"),
                                    ("Report", "Inspection note")):
                    if kind == "Report" and prio in ("Medium", "Low"):
                        continue
                    _add_doc(c, "finding", fid, pid,
                             f"{label} — {title[:44]}", kind,
                             f"https://drive.zameen.com/zd/{code}/visits/"
                             f"{day.isoformat()}/F{fid}-{kind.split()[0].lower()}.pdf",
                             who=visitors[k % len(visitors)])

                # #9 — a non-compliant finding becomes an NCR on the §16 route,
                # raised FROM the finding, so the chain is walkable both ways
                if nc and st in ("open", "assigned", "in_progress"):
                    cid, ref = open_case(
                        c, "NCR", pid, code, title, None,
                        visitors[k % len(visitors)], day.isoformat(),
                        f"{cat} — {loc}. {desc}", position=1,
                        origin=f"finding #{fid} on site visit #{vid}",
                        priority=prio, tat_days=tat,
                        from_team="Architecture", to_team=team,
                        origin_entity="finding", origin_id=fid)
                    c.execute("UPDATE findings SET case_id=? WHERE id=?", (cid, fid))
                    c.execute("INSERT INTO coordination(project_id,stage,from_team,"
                              "to_lane,ask,sla_days,priority,opened_at) "
                              "VALUES(?,?,?,?,?,?,?,?)",
                              (pid, 13, "Architecture", "QA/QC",
                               f"{ref} — joint re-inspection after rectification",
                               5, prio, day.isoformat()))
                    log(c, visitors[k % len(visitors)], 1, "finding", fid, "create",
                        f"Non-compliance — {title[:60]} — {ref} raised",
                        project=pr["name"])


def _demo_llr(c):
    """Manual §7.6 — the Lessons Learned Register.

    Seeded with lessons that are ACTUALLY TRUE of this department's documents, not
    invented ones: the cross-manual collisions and the blank columns found during
    the document review. Three are already ruled and promoted into the stage
    checklist template, so the loop §7.6 describes can be seen working rather
    than described."""
    if c.execute("SELECT COUNT(*) FROM llr").fetchone()[0]:
        return
    proj = {r["name"]: r["id"] for r in c.execute("SELECT id,name FROM projects")}
    # (project, stage, discipline, category, title, detail, impact, status,
    #  ruling, promote_stage, promoted_text, root_cause, delay_kind, delay_owner,
    #  delay_days, preventive_action, improvement_status)
    #
    # Backlog #17: "SLA/TAT took too long" has to be answerable — why, where,
    # whose, internal or external, was there a dependency, what changes. Every
    # entry below carries that, because a lesson that records only the symptom
    # cannot drive an improvement and will be raised again next project.
    RC = {
     0: ("Two disciplines generated the submission set from different layout "
         "revisions and no reconciliation step existed before printing.",
         "internal", "Architecture / Structure", 20,
         "Add a joint area-statement reconciliation, initialled by all three "
         "disciplines, as a gate before the submission set is printed.", "done"),
     1: ("Approval was given verbally on a site walk. There was no register "
         "entry and no retained sample to compare the delivery against.",
         "process", "Architecture", 15,
         "No mock-up is approved without a dated register entry and a retained "
         "physical sample.", "done"),
     2: ("The architectural ceiling level was issued for construction while the "
         "MEP duct route was still under revision. Neither discipline owned the "
         "void dimension.",
         "dependency", "Architecture / MEP", 12,
         "Make the ceiling void schedule a joint deliverable that neither "
         "discipline can issue alone.", "done"),
     3: ("Three manuals define MAR with different scopes and different approval "
         "chains, and no document arbitrates between them.",
         "process", "Cross-manual governance", None,
         "One owner per acronym. Publish a single definitions annexure across "
         "the four manuals.", "proposed"),
     4: ("Two source documents publish different overall TATs for the same "
         "stage and neither is marked as superseding the other.",
         "process", "Document control", None,
         "Ahmed to rule which document is canonical, then re-baseline. Until "
         "then no stage SLA is enforceable.", "agreed"),
     5: ("The annexure the Manual makes mandatory was never written, so the "
         "gate existed but had no content behind it.",
         "process", "Document control", None,
         "Author the annexure per stage in-system and put it under the same "
         "change control as the Manual.", "in_progress"),
     6: ("The booklet's duration column is blank for these steps and no "
         "estimate was ever substituted.",
         "process", "Structure", None,
         "Every catalog step carries a duration or an explicit 'variable, "
         "depends on <party>' — never a blank.", "proposed"),
     7: ("VE was triggered on the tender return rather than on the QS estimate, "
         "so options were studied after the contractor was engaged.",
         "process", "Project Management", 30,
         "Trigger VE on the QS estimate at stage 10. A VE case raised after "
         "tender award must state why it was not raised earlier.", "agreed"),
    }
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
         "Design §11 (Material Approval, PKR 500k+), PM §5.3 (Material Approval, "
         "all materials) and Supply Chain §4.2 (Material Acquisition, capex) all use "
         "the same acronym with different scopes and different approval chains.",
         "Submissions routed to the wrong chain; approvals given by people "
         "without the authority for that value band.",
         "open", "", None, None),
        (None, 3, "Architecture", "Planning",
         "Design Schematics carries two published TATs that differ by three weeks",
         "The booklet captions the schematics flowchart 8-9 weeks; Guidelines "
         "Manual §4.0 publishes 4-6 weeks for the same stage.",
         "No SLA for the stage can be defended, so none is enforced.",
         "open", "", None, None),
        (None, None, None, "Document control",
         "§4.2 internal checklist annexure does not exist",
         "The Manual makes checklist sign-off mandatory before drawing issuance "
         "and then marks the annexure itself \"(to be added)\".",
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
        pid = proj.get(pname or names[i % len(names)])
        raised = (today() - datetime.timedelta(days=30 + i * 17)).isoformat()
        rc, dkind, downer, ddays, prev, istat = RC.get(
            i, (None, None, None, None, None, "proposed"))
        # #15 — the moment a lesson is raised the head sees it, and Audit sees it
        # from whichever status the governance setting says.
        head_seen = raised + "T17:00:00" if setting_bool(
            c, "lessons.notify_head", True) else None
        audit_gate = setting(c, "lessons.audit_from_status", "ruled")
        rank = {"open": 0, "ruled": 1, "adopted": 2}
        audit_seen = (raised + "T17:05:00"
                      if setting_bool(c, "lessons.notify_audit", True)
                      and rank.get(status, 0) >= rank.get(audit_gate, 1) else None)
        c.execute("INSERT INTO llr(project_id,stage,discipline,category,title,detail,"
                  "impact,raised_by,raised_at,source,status,ruling,ruled_by,ruled_at,"
                  "root_cause,delay_kind,delay_owner,delay_days,preventive_action,"
                  "improvement_status,improvement_owner,head_dept,head_notified_at,"
                  "audit_notified_at,priority)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (pid, stage, disc, cat, title, detail, impact,
                   "Ahmed Khan" if i % 2 else "Haroon Noon", raised,
                   "Design Manual §7.6", status, ruling or None,
                   "Haroon Noon" if status in ("ruled", "adopted") else None,
                   raised if status in ("ruled", "adopted") else None,
                   rc, dkind, downer, ddays, prev, istat,
                   "Haroon Noon" if istat in ("agreed", "in_progress", "done") else None,
                   disc or "Architecture", head_seen, audit_seen,
                   "Critical" if (ddays or 0) >= 20 else
                   "High" if ddays else "Medium"))
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


if __name__ == "__main__":
    seed(force="--force" in os.sys.argv)
    c = conn(); demo(c)
    q = lambda s: c.execute(s).fetchone()[0]
    print(json.dumps({
        "projects": q("SELECT COUNT(*) FROM projects"),
        "people": q("SELECT COUNT(*) FROM people"),
        "catalog_steps": q("SELECT COUNT(*) FROM products"),
        "stage_rows": q("SELECT COUNT(*) FROM project_stages"),
        "tasks": q("SELECT COUNT(*) FROM tasks"),
        "open_cases": q("SELECT COUNT(*) FROM cases WHERE status='open'"),
        "open_coordination": q("SELECT COUNT(*) FROM coordination WHERE closed_at IS NULL"),
        "obligations": q("SELECT COUNT(*) FROM obligations"),
        "obligations_missed": q("SELECT COUNT(*) FROM obligations WHERE done_at IS NULL "
                                "AND due_on < date('now')"),
        "drawings": q("SELECT COUNT(*) FROM drawings"),
        "transmittals": q("SELECT COUNT(*) FROM transmittals"),
        "sheets_issued": q("SELECT COUNT(*) FROM transmittal_drawings"),
        "site_visits": q("SELECT COUNT(*) FROM site_visits"),
        "authority_file": q("SELECT COUNT(*) FROM authority"),
        "lessons": q("SELECT COUNT(*) FROM llr"),
        "checklist_template": q("SELECT COUNT(*) FROM checklist_templates"),
        "documents": q("SELECT COUNT(*) FROM documents"),
    }, indent=2))
    c.close()
