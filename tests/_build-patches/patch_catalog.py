"""Patch catalog.py: station 14, Manual-sourced workflows, provenance."""
import sys

PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\catalog.py"
src = open(PATH, encoding="utf-8").read()


def sub(old, new):
    global src
    assert old in src, "anchor missing: " + old[:70]
    src = src.replace(old, new, 1)


# ── 1 · the spine gains station 14. The lifecycle had no end before this. ──
sub('    (13, "Construction Support",    "C", "RFIs, MAR, shop drawings, site visits, as-built"),\n]',
    '    (13, "Construction Support",    "C", "RFIs, MAR, shop drawings, sampling, site visits"),\n'
    '    (14, "Closeout & Handover",     "C", "As-built, O&M handover, archive, lessons learned"),\n]')

# ── 2 · external lanes the Manual names but the Booklet never did ──
sub('    "Authority", "Zameen Studios", "Bayut", "Stakeholders", "Higher Management",\n]',
    '    "Authority", "Zameen Studios", "Bayut", "Stakeholders", "Higher Management",\n'
    '    "Contractor", "QA/QC", "CFT", "Audit", "Head ZD", "Acquisition",\n]')

NEW = '''
# ═══════════════ FROM THE GUIDELINES MANUAL, NOT THE BOOKLET ═══════════════
# Volume 1 of the booklet stops at the drawing. These seven workflows are the
# department's own Manual sections that the booklet never drew a swimlane for —
# and they cover where a project spends its last three years. Stage 13 used to be
# one label carrying everything from an RFI to a handover, which is exactly why it
# read as a dead end. Each entry carries its section number as `source`, so the
# provenance stays honest: transcribed from the Manual's prose, not a swimlane.

("Architecture", "Value Engineering", 10, "3-4 Weeks", None, [
    (1, "VE trigger — tender cost over approved budget", 1, "PM", "X"),
    (2, "VE workshop with Structure, MEP and QS", 2, "", "M"),
    (3, "Option study — specification, system and layout alternates", 7, "", "M"),
    (4, "Structural implication check", 3, "Structure", "C"),
    (5, "MEP implication check", 3, "MEP", "C"),
    (6, "QS cost comparison per option", 5, "PM", "CX"),
    (7, "VE proposal pack issued to CFT", 2, "", "M"),
    (8, "CFT review and shortlist", 3, "CFT", "CRX"),
    (9, "Head ZD decision on adopted options", 2, "Head ZD", "CG"),
    (10, "Incorporation into tender drawings and BOQ", 7, "", "M"),
], "Design Manual \\u00a78"),

("Architecture", "BOQ Endorsement", 10, "2 Weeks", None, [
    (1, "Tender drawing set released to PM", 1, "", ""),
    (2, "QS quantity take-off and BOQ preparation", 10, "PM", "X"),
    (3, "Architecture quantity and specification check", 3, "", "C"),
    (4, "Structure quantity check", 3, "Structure", "C"),
    (5, "MEP quantity check", 3, "MEP", "C"),
    (6, "Discrepancy log returned to QS", 2, "PM", "RX"),
    (7, "Head ZD endorsement of BOQ", 2, "Head ZD", "CG"),
    (8, "Endorsed BOQ released to Supply Chain for tender", 1, "Supply Chain", "GX"),
], "Design Manual \\u00a710"),

("Architecture", "Finishing Items & Sampling", 12, "6 Weeks", None, [
    (1, "Finishing schedule per inventory type", 5, "", "M"),
    (2, "Sample call issued to contractor", 1, "Contractor", ""),
    (3, "Sample receipt and register entry", 3, "Contractor", "X"),
    (4, "Design review against the approved mood board", 3, "", "C"),
    (5, "Mock-up unit construction", 14, "Contractor", "X"),
    (6, "Joint mock-up inspection with QA/QC", 2, "QA/QC", "CX"),
    (7, "Approval or rejection with a recorded reason", 2, "", "CR"),
    (8, "Entry in the annual approved-material archive", 1, "", "G"),
], "Design Manual \\u00a712"),

("Architecture", "QA/QC Site Coordination", 13, "Continuous", None, [
    (1, "QA/QC raises a site observation against IFC", 1, "QA/QC", "X"),
    (2, "Design assessment — deviation or acceptable", 2, "", "C"),
    (3, "Classification as NCR, RFI or design change", 1, "", "C"),
    (4, "Corrective design instruction issued", 3, "", "M"),
    (5, "Contractor rectification on site", None, "Contractor", "X"),
    (6, "Joint re-inspection", 2, "QA/QC", "CX"),
    (7, "NCR close-out and register update", 1, "", "G"),
], "Design Manual \\u00a716"),

("Architecture", "Regulatory Inspection Support", 13, "2-3 Weeks", None, [
    (1, "Inspection notice received from the authority", 1, "Authority", "X"),
    (2, "Compile the approved drawing set and NOC file", 3, "", "M"),
    (3, "Structure and MEP compliance inputs", 3, "Structure", "C"),
    (4, "Site walk with the authority inspector", 1, "Authority", "X"),
    (5, "Observations register and gap analysis", 2, "", "C"),
    (6, "Compliance response and rectification drawings", 5, "", "MR"),
    (7, "Completion / occupancy certificate issued", None, "Authority", "GX"),
], "Design Manual \\u00a717"),

("Architecture", "Project Closeout & As-Built", 14, "8 Weeks", None, [
    (1, "As-built markups received from contractor", None, "Contractor", "X"),
    (2, "Architecture as-built compilation", 15, "", "M"),
    (3, "Structure as-built compilation", 10, "Structure", "M"),
    (4, "MEP as-built compilation", 10, "MEP", "M"),
    (5, "Design verification against site condition", 5, "", "C"),
    (6, "QA/QC concurrence on the as-built set", 3, "QA/QC", "CX"),
    (7, "As-built transmittal to PM and Property Management", 2, "PM", "GX"),
    (8, "O&M manuals and warranty pack handover", 5, "PM", "X"),
    (9, "Drawing archive and register closure", 2, "", "G"),
], "Design Manual \\u00a718"),

("Architecture", "Lessons Learned Review", 14, "1 Week", None, [
    (1, "Collect LLR entries raised through the project", 1, "", ""),
    (2, "Discipline review — Architecture, Structure, MEP", 2, "", "C"),
    (3, "Root cause and repeat-risk assessment", 2, "", "M"),
    (4, "Ruling by Head ZD on the adopted lessons", 1, "Head ZD", "C"),
    (5, "Promotion into stage checklists and standards", 1, "", "G"),
], "Design Manual \\u00a77.6 \\u00b7 PM Manual \\u00a78.3 defines a competing process \\u2014 unarbitrated"),
]
'''

anchor = '    (8, "Artworks management and transferring to vendor", 1, "", ""),\n]),\n]\n'
assert anchor in src, "catalog tail anchor not found"
src = src.replace(anchor, anchor[:-2] + NEW, 1)

# ── 3 · flatten / workflows / conflicts / stats learn about `source` ──
sub('''def flatten():
    """One row per process step — what the importer writes to `products`."""
    out = []
    for team, wf, stage, tb, tm, steps in CATALOG:
        for seq, name, days, lane, flags in steps:''',
    '''BOOKLET = "Design Workflow Booklet Vol.1"


def _unpack(entry):
    """A catalog entry is a 6-tuple (booklet) or a 7-tuple (Manual-sourced).

    Kept variadic rather than rewriting all 39 booklet entries, so the change that
    added the Manual workflows does not touch a single transcribed line.
    """
    team, wf, stage, tb, tm, steps = entry[:6]
    return team, wf, stage, tb, tm, steps, (entry[6] if len(entry) > 6 else BOOKLET)


def flatten():
    """One row per process step — what the importer writes to `products`."""
    out = []
    for entry in CATALOG:
        team, wf, stage, tb, tm, steps, source = _unpack(entry)
        for seq, name, days, lane, flags in steps:''')

sub('''                "rework": "R" in flags, "variable": "X" in flags, "gate": "G" in flags,
                "tat_booklet": tb, "tat_manual": tm,
            })
    return out''',
    '''                "rework": "R" in flags, "variable": "X" in flags, "gate": "G" in flags,
                "tat_booklet": tb, "tat_manual": tm, "source": source,
            })
    return out


def workflows():
    """The catalog, one row per workflow — what the Workflow Catalog rail lists."""
    out = []
    for entry in CATALOG:
        team, wf, stage, tb, tm, steps, source = _unpack(entry)
        out.append({
            "team": team, "workflow": wf, "stage": stage,
            "tat_booklet": tb, "tat_manual": tm, "source": source,
            "steps": len(steps),
            "sum_days": sum(d for _s, _n, d, _l, _f in steps if d),
            "unknown": sum(1 for _s, _n, d, _l, _f in steps if d is None),
            "external": sum(1 for _s, _n, _d, l, _f in steps if l and l not in TEAMS),
            "conflict": bool(tm and tb and tm.strip() != tb.strip()),
        })
    return out''')

sub('''    out = []
    for team, wf, stage, tb, tm, steps in CATALOG:
        if tm and tb and tm.strip() != tb.strip():''',
    '''    out = []
    for entry in CATALOG:
        team, wf, stage, tb, tm, steps, _src = _unpack(entry)
        if tm and tb and tm.strip() != tb.strip():''')

sub('''    return {
        "workflows": len(CATALOG),
        "steps": len(rows),''',
    '''    return {
        "workflows": len(CATALOG),
        "from_booklet": sum(1 for w in workflows() if w["source"] == BOOKLET),
        "from_manual": sum(1 for w in workflows() if w["source"] != BOOKLET),
        "stations": len(STAGES),
        "steps": len(rows),''')

open(PATH, "w", encoding="utf-8").write(src)
print("catalog.py patched")
