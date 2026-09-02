"""Patch store.py part 2: the §4.2 checklist template, open_case(), register seeds."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\store.py"
src = open(PATH, encoding="utf-8").read()

S = "\u00a7"
DASH = "\u2014"


def sub(old, new):
    global src
    assert old in src, "anchor missing: " + old[:70]
    src = src.replace(old, new, 1)


# ══════════════════════════════════════════════════════════════════════════
# A · the §4.2 annexure, authored
# ══════════════════════════════════════════════════════════════════════════
TEMPLATE = '''

# ── the stage checklist template ─────────────────────────────────────────────
# Manual %(S)s4.2 lists an "Internal Checklist Annexure" and then says "(to be
# added)". It does not exist in any document supplied. Sign-off was therefore
# mandatory against content nobody had written — which is how a mandatory gate
# becomes a signature on an empty page.
#
# These are that annexure, authored from what the Manual and the booklet already
# require elsewhere: every item traces to a section or to a step in the swimlane.
# They are a STARTING POSITION for Ahmed and Haroon to edit in-system, not a
# claim about what the department decided. The point is that the gate now has
# content, and that a lesson learned can add to it permanently (%(S)s7.6).
CHECKLIST_TEMPLATE = [
 (1,  "Acquisition pack received and logged against the intake table",
      "Manual %(S)s3.1"),
 (1,  "Regulatory data, land area and plot size confirmed in writing",
      "Manual %(S)s3.1 intake fields 1-2"),
 (2,  "EPC and IRR assumptions recorded with the feasibility owner named",
      "Manual %(S)s3"),
 (2,  "Management approval to proceed minuted and dated", "Manual %(S)s3.4 gate"),
 (3,  "Site analysis reconciled with the acquisition survey", "Booklet 3.1"),
 (3,  "By-laws and ground coverage checked against the intake regulatory field",
      "Manual %(S)s3.1 / Booklet 3.2"),
 (3,  "Zoning confirmed for the intended inventory mix", "Booklet 3.3"),
 (3,  "Initial column grid shared with Structure and acknowledged", "Booklet 3.5"),
 (3,  "Area statement reconciled with the approved inventory mix", "Booklet 3.7"),
 (4,  "Column grid and beam drops received from Structure and incorporated",
      "Booklet 4.2"),
 (4,  "Service and duct routes received from MEP and incorporated", "Booklet 4.3"),
 (4,  "Clash review held with both disciplines and minuted", "Manual %(S)s9"),
 (5,  "Basement services layout coordinated with MEP", "Booklet 5.1"),
 (5,  "Elevations and sections consistent with the approved massing", "Booklet 5.6"),
 (5,  "Inventory mix and area calculations re-issued after the final layout",
      "Booklet 5.8"),
 (5,  "Stakeholder feedback log closed with a dated response", "Booklet 5.10"),
 (6,  "Renders match the signed-off design, not a later revision", "Booklet 6.4"),
 (6,  "External render vendor deliverable received and checked", "Booklet 6.5"),
 (7,  "Area statement identical across Architecture, Structure and MEP sheets",
      "Manual %(S)s7"),
 (7,  "Every sheet signed and stamped by the licensed professional", "Booklet 7.7"),
 (7,  "In-house structural stability ownership recorded before submission",
      "Booklet Structure 7"),
 (7,  "Submission letter and drawing list filed in the authority register",
      "Manual %(S)s7"),
 (8,  "Mood board approved by the stakeholder and dated", "Booklet 8.4"),
 (9,  "Collateral content signed off by Creative and the project lead",
      "Booklet 9"),
 (10, "Specification schedule complete for every finish shown", "Manual %(S)s10"),
 (10, "Value engineering decisions incorporated or formally closed",
      "Manual %(S)s8"),
 (10, "BOQ endorsed by Head ZD before release to Supply Chain", "Manual %(S)s10"),
 (11, "All open RFIs affecting grey structure closed", "Manual %(S)s14"),
 (11, "Structure and MEP IFC sets cross-checked against Architecture",
      "Manual %(S)s5"),
 (11, "Drawing register updated with the IFC revision of every sheet issued",
      "Manual %(S)s5"),
 (11, "IFC Phase I issued before basement commencement", "Manual %(S)s5"),
 (12, "Mood board approved and the finishing schedule frozen", "Manual %(S)s12"),
 (12, "Mock-up units inspected and approved jointly with QA/QC", "Manual %(S)s12"),
 (12, "Approved-material archive updated for every finishing item",
      "Manual %(S)s12"),
 (13, "Monthly site visit logged with findings", "Manual %(S)s15"),
 (13, "Every NCR raised carries a dated design response", "Manual %(S)s16"),
 (13, "Shop drawings reviewed against IFC intent within the published SLA",
      "Manual %(S)s13"),
 (14, "As-built set verified against the site condition", "Manual %(S)s18"),
 (14, "As-built transmittal issued to PM and Property Management",
      "Manual %(S)s18"),
 (14, "O&M manuals and warranty pack acknowledged", "Manual %(S)s18"),
 (14, "Lessons learned reviewed and promoted into the stage checklists",
      "Manual %(S)s7.6"),
]


def open_case(c, typ, project_id, code, title, value=None, raised_by="system",
              raised_at=None, note="", position=0, origin=None):
    """Instantiate a case on its route. One function, ten route types.

    Used by the write layer AND by anything that raises a case as a CONSEQUENCE
    of something else — a site visit that finds non-compliance raises an NCR
    here rather than leaving a flag on a row nobody reads.
    """
    route = ROUTES[typ]
    n = c.execute("SELECT COUNT(*) FROM cases WHERE type=?", (typ,)).fetchone()[0]
    ref = "%%s-%%s-%%d" %% (typ, code or "ZD", 100 + n + 1)
    raised_at = raised_at or today().isoformat()
    c.execute("INSERT INTO cases(ref,type,project_id,title,value_pkr,position,status,"
              "raised_by,raised_at,note) VALUES(?,?,?,?,?,?,'open',?,?,?)",
              (ref, typ, project_id, title, value, position, raised_by, raised_at, note))
    cid = c.execute("SELECT id FROM cases WHERE ref=?", (ref,)).fetchone()["id"]
    d = datetime.date.fromisoformat(raised_at[:10])
    for idx, (label, owner, sla) in enumerate(route["lanes"]):
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
''' % {"S": S}

sub("\n\nSCHEMA = \"\"\"", TEMPLATE + "\n\nSCHEMA = \"\"\"")

open(PATH, "w", encoding="utf-8").write(src)
print("store.py part 2 patched")
