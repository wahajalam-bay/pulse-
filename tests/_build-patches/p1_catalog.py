"""Backlog #18: the discipline/department list is wider than the four design teams."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\catalog.py"
src = open(PATH, encoding="utf-8").read()
S = "\u00a7"


def sub(old, new):
    global src
    assert old in src, "anchor: " + old[:60]
    src = src.replace(old, new, 1)


sub('TEAMS = ["Architecture", "Structure", "MEP", "Creative"]',
    '''TEAMS = ["Architecture", "Structure", "MEP", "Creative"]

# ── the organisation, not just this department ───────────────────────────────
# Backlog #18. The discipline picker was limited to the four design teams, so a
# lesson caused by Legal or a finding owned by Property Management had nowhere to
# sit. `kind` is what drives behaviour, not the name:
#   design      — a ZD Arch & Design team. Signs in. Owns work.
#   internal    — another Zameen department. Signs in once its system connects;
#                 until then it holds the clock and the wait is recorded.
#   governance  — an approval body, not a team. Appears in routes, never assigned.
#   external    — outside Zameen entirely. Never signs in.
DEPARTMENTS = [
    ("Architecture",         "design"),
    ("Structure",            "design"),
    ("MEP",                  "design"),
    ("Creative",             "design"),
    ("Project Management",   "internal"),
    ("QA/QC",                "internal"),
    ("Supply Chain",         "internal"),
    ("Finance",              "internal"),
    ("Legal",                "internal"),      # named explicitly in the review
    ("Audit / IA",           "internal"),
    ("Property Management",  "internal"),
    ("Sales",                "internal"),
    ("Marketing / CPML",     "internal"),
    ("Stores & Logistics",   "internal"),
    ("HR",                   "internal"),
    ("IT",                   "internal"),
    ("Head ZD",              "governance"),
    ("CPC",                  "governance"),
    ("CEO Office",           "governance"),
    ("Contractor",           "external"),
    ("Consultant",           "external"),
    ("Authority",            "external"),
    ("Third Party Vendor",   "external"),
    ("Zameen Studios",       "external"),
    ("Bayut",                "external"),
    ("Stakeholders",         "external"),
]


def departments(kind=None):
    return [n for n, k in DEPARTMENTS if not kind or k == kind]


def dept_kind(name):
    for n, k in DEPARTMENTS:
        if n == name:
            return k
    # lanes in the booklet use short forms; map the ones that differ
    alias = {"PM": "internal", "Property Mgmt": "internal", "CPML": "internal",
             "Audit": "internal", "CFT": "governance", "Higher Management": "governance",
             "Design Team": "design", "Call Center": "internal",
             "Production": "internal", "CPML ": "internal"}
    return alias.get(name, "external")''')

open(PATH, "w", encoding="utf-8").write(src)
print("catalog.py: 26 departments, 4 kinds")
