"""Bring PROJECT-MEMORY.md and README.md up to date with the v2 build."""
import io, os
ROOT = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch"


def patch(fn, pairs, append=None):
    p = os.path.join(ROOT, fn)
    s = open(p, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, fn + " MISSING: " + old[:60]
        s = s.replace(old, new, 1)
    if append:
        s += append
    open(p, "w", encoding="utf-8").write(s)
    print("updated", fn)


# ══════════════════════════════════════════════════════════════ PROJECT-MEMORY
patch("PROJECT-MEMORY.md", [
 ("> **Updated: 2026-08-27.** Keep this current — it survives conversation compaction.",
  "> **Updated: 2026-09-01.** Keep this current — it survives conversation compaction.\n"
  "> See §11 for the 1 Sep build: 14 stations, 46 workflows, 10 routes, 33 write actions,\n"
  "> the entity drawer, search, notifications, and the §7.6 → §4.2 loop."),

 ("### The spine — 13 stations, 3 phases",
  "### The spine — 14 stations, 3 phases  *(13 until 1 Sep; §18 closeout added)*"),

 ("- **C · Construction Support** — 13 (Manual §§5–18, runs for years)",
  "- **C · Construction Support** — 13 (Manual §§5–17, runs for years), "
  "14 Closeout & Handover (§18)\n\n"
  "  Station 14 was added on 1 Sep. Before it, stage 13 ran forever and a project could "
  "never be finished — the lifecycle had no end, and §18 had nowhere to live."),

 ("""```
catalog.py       39 workflows / 296 steps — THE source of truth, one file to edit
store.py         schema (14 tables), seed, two-clock derivation, ROUTES, obligations
actions.py       THE WRITE LAYER — 17 handlers, every mutation, all gates
server.py        stdlib HTTP + JSON API (reads) + dispatch to actions.py
js/forms.js      modal + field renderer + F.act() + override-with-reason handling
js/app.js        router + 11 read rails
js/ui-actions.js My Queue, Drawings, and every action button (UI.*)
css/zd.css       ZD navy on PULSE grammar + modal/form layer
data/zd.db       SQLite — delete + rerun to rebuild
start.sh      MSYS_NO_PATHCONV=1 PORT=4010 MOUNT=/zd python server.py
```""",
  """```
catalog.py       46 workflows / 350 steps / 14 stations — THE source of truth
                 39 from Booklet Vol.1 + 7 transcribed from the Manual's prose.
                 Every entry carries `source`; _unpack() keeps 6- and 7-tuples valid
                 so adding the Manual workflows touched no transcribed line.
store.py         schema (20 tables), seed, two-clock derivation, ROUTES (10),
                 CHECKLIST_TEMPLATE (the §4.2 annexure), open_case(), register seeds
actions.py       THE WRITE LAYER — 28 handlers, every mutation, all gates
server.py        stdlib HTTP + JSON API + /api/entity, /api/search, /api/notifications
js/forms.js      modal + field renderer + F.act() + override-with-reason handling
js/app.js        router (hash deep links) + read rails, every row clickable
js/ui-actions.js every action button (UI.*) + the Site and Lessons rails
js/entity.js     THE ENTITY LAYER — one drawer for any record, command palette,
                 computed notifications. This is what made the system navigable.
css/zd.css       ZD navy on PULSE grammar + modal/form layer
css/zd-ui.css    drawer, palette, notification panel, clickable-row grammar
data/zd.db       SQLite — `python store.py --force` to rebuild
start.sh      MSYS_NO_PATHCONV=1 PORT=4010 MOUNT=/zd python server.py
```"""),

 ("""### Seeded numbers
39 workflows · 296 steps · 46 rework loops · 10 gates · 13 stations · 45 people ·
8 projects · 1,261 tasks · 12 cases · 18 coordination asks · 15 missed obligations ·
**23.7% of elapsed time = waiting outside the department**

### Real vs demo
**Real:** catalog, spine, routes+sources, PKR thresholds, TAT conflicts, people, project names
**Demo:** task progress, case positions, obligation history — flagged on screen""",
  """### Seeded numbers  *(1 Sep)*
46 workflows · 350 steps · 50 rework loops · 19 gates · **14 stations** · 45 people ·
8 projects · 1,385 tasks · 16 cases · 26 coordination asks · **109 drawings** ·
**20 transmittals / 307 sheet-issuances** · 12 site visits · 7 authority records ·
8 lessons · **44 checklist-template items** · 25 documents

### Real vs demo
**Real:** catalog and its provenance, spine, 10 routes + sources, PKR thresholds,
TAT conflicts, people, project names, the §4.2 template (authored from the Manual),
the lessons that came out of the document review.
**Seeded operating history:** stage positions, and every register **derived from them** —
drawings exist because the project reached the stage that produces them, transmittals
carry the sheets that existed at issuance, the authority file starts where stage 7 did.
The registers and the spine cannot disagree, which is why nothing on screen is a
free-floating number."""),

 ("""### Still NOT built (be honest about these)
§8 Value Engineering · §10 BOQ endorsement · §12 finishing items & sampling ·
§16 QA/QC coordination · §17 regulatory visit support · §18 closeout / as-built ·
notifications · search · file upload · LLR library""",
  """### Still NOT built (be honest about these)
*(most of this list was closed on 1 Sep — see §11. What remains:)*
- **Real file storage.** Documents are a versioned LINK register attached to any
  entity, not upload. Deliberate: they have a drive; what they lacked was a record of
  which file is current and what it belongs to. Confirm this is acceptable (question 8).
- **Notifications are in-app only.** Computed on read, never stored — so they cannot
  drift — but there is no email or WhatsApp push. PM §8.2.3 mandates WhatsApp groups.
- **No external portal.** Contractor, consultant and Authority lanes hold the clock
  and record the wait; nobody outside ZD can sign in (question 9).
- **SAGE and Primavera** — no integration, no decision (questions 14–15).
- **Mobile.** Site visits are logged on the same desktop shell (question 10)."""),
], append=r"""

---

## 11 · The 1 Sep build — "more clickable, no dummy things"

User asked for two things: make it navigable, and add the most important missing
workflows. Both were fair. What was wrong, and what was done:

### The problem with v2 as it stood
1. **Every table was a terminus.** A task named a workflow you could not open; a case
   named a project you could not reach; a drawing had a revision letter and no history.
   You could press a button next to a number; you could not FOLLOW anything.
2. **Three rails were live buttons over empty tables.** `drawings`, `transmittals` and
   `site_visits` had zero rows. The register existed as a schema, not as a thing.
3. **Stage 13 was a dead end by construction.** One label — "Construction Support" —
   carrying an RFI, a mock-up, an NCR, an authority inspection and a handover. The
   booklet never drew a swimlane for any of it, so the catalog had almost nothing there,
   and that is where a project spends its last three years.
4. **§4.2 made checklist sign-off mandatory against content nobody had written.** The
   annexure is marked "(to be added)". A mandatory gate was a signature on an empty page.

### What was added

**Seven workflows from the Manual's prose** (marked `source`, never passed off as
booklet): §8 Value Engineering · §10 BOQ Endorsement · §12 Finishing Items & Sampling ·
§16 QA/QC Site Coordination · §17 Regulatory Inspection Support · §18 Project Closeout
& As-Built · §7.6 Lessons Learned Review. **Station 14** so the lifecycle can end.

**Five case routes** — VE, NCR, BOQ, SMP, ABD. The engine did not change; only the
ROUTES table. That was the point of the primitive and it held.

**Five registers** — `checklist_templates` (the §4.2 annexure, authored, 44 items,
every one citing a section or a swimlane step), `llr`, `documents`, `authority`,
`drawing_revs` + `transmittal_drawings`.

**Eleven write verbs** — 17 → 28: drawing/revise, authority/submit, authority/respond,
llr/create, llr/rule, llr/promote, document/add, template/add, template/retire,
project/close, case/withdraw.

**The entity layer** (`js/entity.js` + `/api/entity/<kind>/<id>`) — one drawer behind
every row, for 12 record kinds, each with the record, its project, its notes, its
documents and its slice of the ledger, plus the actions that record can take. A
breadcrumb stack, so you can walk case → project → stage → checklist and back.
Deep links (`#/e/case/13`) so a finding can be sent as a URL.

**Search** (`Ctrl/⌘+K`, or `/`) over 11 registers, and **notifications** computed on
read — never stored, so they cannot drift out of date.

### The connections that make it a system rather than screens

- A **site visit** that finds non-compliance **raises an NCR** on the §16 route, at the
  design-assessment lane, and opens the QA/QC re-inspection clock. Not a boolean column.
- **Authority observations** come back as a **real task** on the design team, and
  answering closes the coordination clock that submitting opened.
- A **transmittal** carries the **sheet list with each sheet's revision**, and issuing
  for construction moves those sheets to IFC in the register and writes a revision row.
- **Initiating a stage stamps the §4.2 template** onto the new checklist, so the
  mandatory gate arrives with content.
- **A lesson (§7.6), once ruled on, is adopted into that template** — and lands
  immediately on every unsigned checklist for the stage. That closes the loop:
  *site visit → NCR → lesson → ruling → checklist item → the gate that blocks the next
  transmittal.* A lessons register that cannot change the checklist is a diary.

### Verified, not assumed
`scratchpad/e2e.py` drives all of the above through the HTTP API: **50/50 passing** on a
fresh database. The app was then driven in headless Chrome — 15 rails, 14-station matrix
(112 cells), the drawer opening a case with its 5 route lanes, the palette — with
**zero console errors**.

### Watch out for
- `DEMO-WALKTHROUGH.html` was written against the 27 Aug build and is now stale
  (13 stations, 17 actions, 39 workflows). Rewrite it before the next demo.
- `backup-pre-v2/` holds the 27 Aug copies of every file changed. There is still no git
  repo here — that is the only undo.
- Everyone still shares one password. Rotate before this leaves a laptop.
""")

# ══════════════════════════════════════════════════════════════════════ README
patch("README.md", [
 ("""```bash
python server.py                       # http://127.0.0.1:4010/zd/
PORT=4010 MOUNT=/zd python server.py   # explicit
python store.py --force                # rebuild the database from scratch
python catalog.py                      # print catalog stats + TAT conflicts
```""",
  """```bash
python server.py                       # http://127.0.0.1:4010/zd/
PORT=4010 MOUNT=/zd python server.py   # explicit
python store.py --force                # rebuild the database from scratch
python catalog.py                      # print catalog stats + TAT conflicts
```

46 workflows · 350 steps · **14 stations** · 10 case routes · 33 write actions ·
15 rails. `Ctrl+K` searches every register; every row opens a record."""),

 ("## What you can DO in it — 17 write actions",
  "## What you can DO in it — 33 write actions"),

 ("""| Add a note to anything | replaces WhatsApp |""",
  """| Add a note to anything | replaces WhatsApp |
| **Revise a drawing** · issue a transmittal with its **sheet list** | §5 — the register keeps every revision |
| **Log an authority submission** · record what came back | §7 / §17 — the longest clock the department carries |
| **Raise a lesson** · rule on it · **adopt it into the stage checklist** | §7.6 → §4.2 — the loop |
| Author, retire and version the **§4.2 checklist template** | the annexure the Manual marks "(to be added)" |
| Attach a document to anything | a versioned link register, not file storage |
| Withdraw a case · **close a project out** | §18 — the lifecycle finally has an end |

### The seven workflows the booklet never drew

Volume 1 stops at the drawing. These are transcribed from the Manual's prose and are
tagged as such everywhere they appear — provenance is never blurred:

| Workflow | Section | Why it matters |
|---|---|---|
| Value Engineering | §8 | VE ran after tender award, so every change became a DCR with a cost claim |
| BOQ Endorsement | §10 | The gate between the tender set and Supply Chain |
| Finishing Items & Sampling | §12 | Mock-ups were approved verbally with no record |
| QA/QC Site Coordination | §16 | Non-compliance had nowhere to go |
| Regulatory Inspection Support | §17 | The authority clock was never totalled |
| Project Closeout & As-Built | §18 | **Station 14** — before it, stage 13 ran forever |
| Lessons Learned Review | §7.6 | The loop that changes the next project |

### The connections (this is the part that matters)

- A **site visit** finding non-compliance **raises an NCR** on the §16 route and starts
  the QA/QC re-inspection clock — not a checkbox on a row nobody reads.
- **Authority observations** come back as a **task on the design team**; answering them
  closes the clock that submitting opened.
- A **transmittal** carries the sheet list with each sheet's revision, and issuing for
  construction updates the register.
- **Initiating a stage stamps the §4.2 template** onto its checklist, so the mandatory
  gate arrives with content instead of blank.
- **A ruled lesson is adopted into that template** and lands on every unsigned checklist
  for the stage — so the checklist that blocks the next transmittal is one the last
  project's mistake wrote."""),
])
