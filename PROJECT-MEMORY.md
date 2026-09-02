# ZD PULSE — project memory

> Working state for the Zameen Developments Arch & Design system.
> **Updated: 2026-09-02.** Keep this current — it survives conversation compaction.
> §12 is the build against Haroon's 1 Sep review. **§13 is a concurrency incident —
> read it before running two agents on this folder again.**
> See §11 for the 1 Sep build: 14 stations, 46 workflows, 10 routes, 33 write actions,
> the entity drawer, search, notifications, and the §7.6 → §4.2 loop.

---

## 1 · The ask

**Muhammad Ashhad** (BSE, `muhammad.ashhad@bayut.sa`) is building the **ZD Universe** —
individual systems for Zameen Developments' three departments that will later connect.

**Haroon Noon** (Head of Architecture & Design) asked for *"the same as PULSE, same view,
same flow, but for my department, covering all of it."*

Not a dashboard. **An OS** — a workstation where the department's work actually happens,
input and output both, replacing sheets + email + Drive + WhatsApp + notes + third-party tools.

Approach agreed with the user: **build first, demo, then customise** — they have sufficient
documentation, so don't gather requirements first.

---

## 2 · Cast

| Person | Role |
|---|---|
| **Haroon Noon** | Head of Architecture & Design — the client |
| **Ahmed Khan** | Sr. Manager Architecture — owns the workflow booklet, rules on TAT |
| Yahya Ali Khan | Sr. Manager MEP |
| Hafiz Rashid Khalid | Sr. Manager Structure |
| Ali Aslam | Creative Lead |
| **Khurram Saleem** | Sr Manager BSE — sent the original brief email |
| **Zergham Haider** | Built Bayut Studios PULSE; has a partial ZD build (not yet seen) |

---

## 3 · Source documents received

1. **Design – Workflow Booklet Vol.1** — 39 workflows, ~296 process steps, swimlanes
2. **Architecture & Design Manual** — 18 sections, the governing SOP
3. **Project Management Manual** — PM's SOP. **§8.2.1 names "ZD UNIVERSE" as a mandate**
4. **Supply Chain Manual** — vendors, RFQ, PO, CPC, thresholds
5. **Stores & Logistics Manual** — MRF, GRN, inventory, scrap
6. **Bayut Studios PULSE source** (`../pulse final/`) — the system to mirror

---

## 4 · Key findings (do not re-derive these)

### The killer fact
**PM Manual §8.2.1 already mandates ZD Universe**: *"the primary central hub… All project
personnel must use this system as the single source of truth."* It doesn't exist. You are
delivering a system their own signed SOP already requires.

### The structural insight
**Bayut Studios is a job shop; ZD Arch & Design is a project lifecycle.**
Bayut: 388 short parallel projects. ZD: 12 projects running for *years* through sequential
gated stages. So the pipeline view had to be **redesigned from a list into a stage matrix**.

### The department
4 teams / 44 people: Architecture 20 · MEP 13 · Structure 7 · Creative 4. Haroon on top.

### The spine — 14 stations, 3 phases  *(13 until 1 Sep; §18 closeout added)*
- **A · Acquisition** — 1 Data Gathering, 2 Feasibility (Manual §3)
- **B · Design** — 3 Schematics, 4 Internal Coordination, 5 Design Dev, 6 3D, 7 Authority,
  8 Mood Board, 9 Marketing Collateral, 10 Tender, 11 IFC I&II, 12 IFC III
- **C · Construction Support** — 13 (Manual §§5–17, runs for years), 14 Closeout & Handover (§18)

  Station 14 was added on 1 Sep. Before it, stage 13 ran forever and a project could never be finished — the lifecycle had no end, and §18 had nowhere to live.

All four teams' workflows map onto this one spine as lanes.

### ⚠️ The 6 TAT conflicts (BLOCKING — Ahmed must rule)
| Stage | Booklet | Manual §4.0 |
|---|---|---|
| 3 Design Schematics | 8–9 wk | **4–6 wk** |
| 5 Design Development | 9 wk | 8–10 wk |
| 8 Mood Board | 1 wk | 1–2 wk |
| 10 Tender Drawings | 8 wk | 8–9 wk |
| 11 IFC I & II | 9–10 wk | **11–12 wk** |
| 12 IFC Phase III | **16 wk** | 12–14 wk |

The Manual also contradicts **its own flowcharts** on stages 5, 11, 12.
Neither document states whether "days" are working or calendar, or whether external wait
is included. **Both values are stored; `TAT_SOURCE` in `catalog.py` applies the ruling.**

### ⚠️ Cross-manual collisions
- **MAR means 3 different things** — Design §11 (Material *Approval*, PKR 500k+),
  PM §5.3 (Material *Approval*, all materials), SC §4.2 (Material *Acquisition*, capex).
  Different scopes, different approval chains. **Implemented PM §5.3.**
- **CFT means 2 things** — Cross-Functional Team (SC §4.4, Design §14) vs
  Competitive Final Tender (Stores §14.4)
- **Two LLR processes** — Design §7.6 and PM §8.3, neither references the other

### Shared governance kernel (all four manuals)
PKR **15,000** petty · **500,000** CPC · **1,500,000** CEO Office · CPC meets **Thursdays** ·
**Head ZD** approves all design changes · **Audit/IA** is a control in every manual

### Existing systems — integrate, don't replace
- **SAGE** — the ERP. PR/PO/GRN/stock/vendor master. *Biggest unknown: API access?*
- **Primavera P6 / MS Project** — PM's master schedule
- WhatsApp progress groups are **mandated** in PM §8.2.3

### Document gaps
- Design §4.2 Internal Checklist Annexure — *"(to be added)"*
- PM Annexure — 10 checklists listed, **none included**
- SC §2.3.3 Vendor Performance Form — *"[to be inserted]"*
- Stores p.40 — inspection chart *"[to be inserted]"* ×2
- 14 booklet steps have a **blank duration column** (Topographical Survey, Structural Stability)

---

## 5 · The architecture (agreed)

### Five primitives — everything else is configuration
1. **The Case** — typed request + ordered lanes + clocks + ledger.
   MAR/DCR/RFI/SHOP/VET are **route definitions, not features**.
2. **The Two Clocks** — `own_days` vs `wait_days`, split at every handoff.
   *SLA is judged on own time only.* The single most important invariant.
3. **The Gate** — preconditions on transitions. **Log blocked attempts** — highest-signal data.
4. **Value Routing** — one PKR threshold table, all departments. Falls out: split-PO detection.
5. **The Ledger** — append-only, records the *authority* acted with.

### Layers
```
L5 Executive · L4 Dept apps · L3 Shared processes · L2 Registers
L1 Spine · L0 Kernel · L-1 SAGE + Primavera (sync, never replace)
```

### The principle that makes "Design first" safe
> **Build the whole pipe, light up one segment at a time.**

Cases carry ALL lanes. Design's lane is live; PM/QA-QC/Supply Chain lanes are **stubbed** —
they hold the clock and record the wait. When those systems ship, the stub becomes a live
lane, no migration. *The stub data is the business case for building them.*

---

## 6 · What is built

**CANONICAL LOCATION: `Desktop\pulsearch\`** (copied 27 Aug 2026 — work from here.
`Downloads/pulse final/zd-pulse/` is now a stale copy; delete it once you are confident.)

Launch: double-click **START.bat**, or `./start.sh`, or `python server.py`.


```
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
```

**Run:** `./start.sh` → http://127.0.0.1:4010/zd/
**Login:** `haroon@zameen.com` / `ahmed@` / `rashid@` / `yahya@` / `ali@` — pw `ZDesign!2026`

### Seeded numbers  *(1 Sep)*
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
free-floating number.

---

## 7 · Critical correction taken (2026-08-27)

User challenged: *"where are all the actions and activities happening, isn't this just
reporting? does this cater all their workflows?"*

**They were right.** v1 had only **5 write verbs** (start/finish/revise task, advance case,
close coordination). Everything else was seeded. Could not raise a MAR, create a project,
assign work, reject anything, or complete an obligation.

**FIXED — `actions.py` now has 17 write handlers, all tested:**

| Endpoint | Manual |
|---|---|
| `project/create` · `intake/save` | §3 / §3.1 (7 fields, each with a named source) |
| `stage/initiate` · `stage/signoff` | generates tasks from catalog; gated |
| `task/create` · `task/assign` | ad-hoc work + assignment (team-checked) |
| `case/create` · `case/decide` | §11 §14 §13 §7 — approve / **reject** / **return** |
| `coordination/create` | raise a cross-team ask with a clock |
| `obligation/complete` | §9 §15 — evidence required |
| `visit/create` | §15 — auto-closes the monthly obligation |
| `drawing/create` · `transmittal/issue` | §5 — register + contractual issuance |
| `checklist/add` · `tick` · `sign` | §4.1 / §4.2 — author the annexure in-system |
| `note/add` | comments — replaces WhatsApp |

**Gates verified firing (all logged as blocked attempts):**
intake incomplete blocks Stage 3 · previous stage unsigned blocks next · empty checklist
can't sign · unticked checklist can't sign · unsigned checklist blocks transmittal (§4.1) ·
reject/return without reason refused · wrong-team assignment refused · external lane refused ·
PKR ≥500k needs CPC, ≥1.5m needs CEO · obligation without evidence refused ·
finish-before-start refused.

**Soft gates + logged override.** Every refusal offers "Override & proceed" with a mandatory
reason that goes in the ledger. Hard blocks just push work back to paper.

**2 new rails:** My Queue (default landing) · Drawings & Issuance. Now 13 rails.

### Still NOT built (be honest about these)
*(most of this list was closed on 1 Sep — see §11. What remains:)*
- **Real file storage.** Documents are a versioned LINK register attached to any
  entity, not upload. Deliberate: they have a drive; what they lacked was a record of
  which file is current and what it belongs to. Confirm this is acceptable (question 8).
- **Notifications are in-app only.** Computed on read, never stored — so they cannot
  drift — but there is no email or WhatsApp push. PM §8.2.3 mandates WhatsApp groups.
- **No external portal.** Contractor, consultant and Authority lanes hold the clock
  and record the wait; nobody outside ZD can sign in (question 9).
- **SAGE and Primavera** — no integration, no decision (questions 14–15).
- **Mobile.** Site visits are logged on the same desktop shell (question 10).

---

## 8 · THE QUESTION LIST — for Haroon (keep intact)

### Blocking
1. **TAT authority** — booklet vs Manual, 6 stages disagree, Manual self-contradicts on 3
2. **Working or calendar days?** Does TAT include external wait? Parallel branches collapsed?

### Scope
3. **Is Creative in?** 7 of 12 workflows have no project — parked on "Department BAU" carrier
4. **Does the spine cover Phase A and C?** Manual's matrix is stages 3–12 only
5. **Volume 2 of the booklet** — does it exist?
6. **§4.2 checklist annexure "(to be added)"** — who writes it, by when?

### Product behaviour
7. **Hard or soft gates?** *(Built soft + logged override — confirm)*
8. **Files: store or link?** *(Built register + link — confirm)*
9. **External access** — contractors, consultants, Authority: portal or internal-only?
10. **Mobile for site visits?**

### Organisation
11. **Name the authorities** — Head ZD, Director Design/Projects, Audit head, SCM head, CPC
12. **Real project list** — booklet says 12, cover names 8. *4 unnamed, not invented.*
13. **Zergham's partial ZD build** — start from it or fork clean?

### Universe level
14. **SAGE access** — API, DB, or nothing? *(program-shaping)*
15. **Primavera** — import milestones or schedule in-system?
16. **Does "ZD Universe" already exist?** PM §8.2.1 mandates it as if it does
17. **MAR / CFT / LLR collisions** — who arbitrates cross-manual conflicts?
18. **Does the CPC queue move into the system?** Thursdays, all depts, >500k — biggest quick win
19. **Audit/IA access** — read-everything across all four?
20. **One platform, four tenants — or four systems?** *(§8.2.1 argues for one.
    THE decision everything hangs on.)*

---

## 9 · Build sequence (agreed)

| Phase | Ships |
|---|---|
| 0 | Kernel — five primitives, spine, projects, org, ledger, registers |
| 1 | Design catalog · stage matrix · tasks · My Queue ✅ |
| 2 | Coordination ledger · **stubbed cases** · approvals inbox · intake ✅ |
| 3 | Obligations · site visits · checklists · LLR *(in progress)* |
| 4 | **PM OS** — stub lanes go live |
| 5 | Procurement + Stores (heavy SAGE integration) |
| 6 | Head ZD / CEO cockpit |

**Stubs land in phase 2 deliberately** — they accumulate the number that funds phases 4–6.

---

## 10 · Working notes

- Environment is **Windows + Git Bash**. `MSYS_NO_PATHCONV=1` is required or `/zd` becomes
  `C:/Program Files/Git/zd`. Same trap bit us with Bayut PULSE's `/pulse`.
- Bayut PULSE runs on **:4003** (`../pulse final/`), ZD on **:4010**.
- Bayut test accounts added: `test.admin@bayut.sa` etc, pw `PulseTest!2026`,
  backup at `data/users.json.bak-before-testaccounts`.
- PULSE reusables: `plan_requests`/`project_holds`/`task_pauses` = an unused case engine.
  `changes` table already logs `tier`. `deptmap.py` = the alias pattern for naming drift.
- User's style: wants substance and honesty over polish. Called out the reporting-layer
  gap correctly — **do not oversell what is built.**


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
`tests/e2e.py` drives all of the above through the HTTP API: **51/51** on a fresh
database — `python tests/run-all.py`. The app was then driven in headless Chrome — 15 rails, 14-station matrix
(112 cells), the drawer opening a case with its 5 route lanes, the palette — with
**zero console errors**.

### Watch out for
- **Rail labels cannot be a `::after`.** `.rail-nav` needs `overflow-y:auto` to scroll
  at 15 rails, and an overflow that is not `visible` clips on BOTH axes — you cannot
  scroll vertically and overflow horizontally. A pseudo-element cannot leave its
  scrolling ancestor, so the label is one `.railtip` element on `<body>`, positioned
  `fixed` from the button's rect by `railTips()` in `app.js`. Same trap applies to
  anything else that must overflow the rail.
- Headless Chrome with `--virtual-time-budget` **does not advance CSS transitions** —
  a faded-in element reads `opacity: 0` forever and never appears in a screenshot.
  Set `style.transition = "none"` before measuring or capturing, or the check lies.
- `DEMO-WALKTHROUGH.html` was written against the 27 Aug build and is now stale
  (13 stations, 17 actions, 39 workflows). Rewrite it before the next demo.
- `backup-pre-v2/` holds the 27 Aug copies of every file changed. There is still no git
  repo here — that is the only undo.
- Everyone still shares one password. Rotate before this leaves a laptop.

---

## v3 — Haroon's review of 1 Sep 2026

Source: `HAROON-REGISTER-1SEP.docx` (also extracted to `.txt` beside it).
36 numbered backlog items plus 8 definitions (§36) that must NOT be
hard-coded until Arch & Design agrees them.

### The governing decision

Every one of the 8 open definitions lives in **`definitions.py`** as a
provisional default with an `OPEN` flag. Nothing is hard-coded in logic.
The system therefore runs today, and each affected number is tagged
*provisional* in the UI so a placeholder is never mistaken for a baseline.
When a definition is agreed, change it in that one file.

### Delivered (schema + API + UI)

| # | Item | Where |
|---|------|-------|
| 1 | Cross-team case routing | `cases.to_dept/from_dept`, `POST /api/case/raise-crossteam` |
| 2 | Back-and-forth without closing | `case_thread`, `POST /api/case/message` |
| 3 | 24h acknowledgement | `cases.ack_due_at/acked_at`, `POST /api/case/acknowledge` |
| 4 | Escalation | `escalations`, `POST /api/escalate`, 4-step ladder |
| 5 | Priority levels | `priority` on cases/tasks/coordination/llr/findings |
| 6 | Priority separate from TAT | `priority_history`; changing priority never touches `tat_days` |
| 7 | Multiple findings per visit | `visit_findings` |
| 8 | Evidence on findings | `finding_evidence` — photo/report/video/document |
| 9 | Finding to relevant team as RFI | `POST /api/finding/to-rfi` creates the case and links it |
| 10 | Historical visit data | `GET /api/project/<id>/visit-history`, recurrence detection |
| 11 | "Open a Project" to "Add a Project" | renamed in UI and in the refusal message |
| 12/17 | Root cause on lessons | `llr.root_cause` + 6 fields, `POST /api/llr/root-cause` |
| 13 | "What should I do today?" | `GET /api/today`, new first nav item |
| 15 | Lesson head/audit visibility | `llr.head_visible/audit_visible` |
| 16 | Learning Summary page | `GET /api/learning`, new nav item |
| 18 | Departments incl. Legal | `departments` table, 14 depts from `definitions.DEPARTMENTS` |
| 19 | Cross-module collaboration | `entity_links`, `POST /api/link` |
| 25 | SLA to TAT terminology | task/lane/coordination columns now read TAT |
| 33 | Who is waiting on whom | both directions in `/api/today` |
| 36 | Tasks linked to origin | `tasks.origin_kind/origin_id` |

### Blocked on Arch & Design, by design (§36)

These are NOT missing work. They are running on provisional defaults and
flagged in the UI. Hard-coding any of them now would bake in a wrong answer:

- **§36-A** 24h = calendar or business hours?  (`ACK_CLOCK`)
- **§36-B** exact priority ladder + who may change it
- **§36-C** which workflows carry an SLA rather than only a TAT
- **§36-D** Wait / Hold / In-Progress definitions — and whether Wait counts
  inside In Progress (§27). Both readings are computed; the flag picks one.
- **§36-E** Own Time — active execution only, or execution plus own wait?
- **§36-F** Delivery Time exclusions. Only MD approval (§30) is agreed.
- **§36-G** the SLA baseline discrepancy — CRITICAL, nothing may be locked
- **§36-H** workflow catalogue validation against the 15 required fields

### Still to build

- #21/#22 Executive view: department-level facts and workload bifurcation
  over time (§18 — Arch & Design is front-heavy in the first six months)
- #24 Asana/PM interaction model (§20, §31)
- #28/#29 stage matrix split of expected / actual / wait / hold / delay,
  and internal vs external attribution — blocked on §36-D
- #32/#33 delivery-cycle recalculation — blocked on §36-F
- #34 Approval Inbox enrichment

### Migration scripts

`migrate_v3.py` (schema, idempotent) then `backfill_v3.py [--reset]` (data).
The backfill parses each visit's free-text findings into structured rows.
It deliberately does not split on semicolons (they join clauses of one
finding), it classifies "No deviation found" as a passed observation rather
than an open issue, and it does not invent findings from bare
non-compliance counts. 12 visits produced 9 open findings and 3
observations.


---

## 12 · The 2 Sep build — Haroon's 1 Sep review

### The document
`ARCH AND DESIGN (1).docx` in the project root. **It is not the Architecture & Design
SOP** — it is byte-identical (MD5 `6e7b5c45…`) to `HAROON-REGISTER-1SEP.docx`, the
register of the review meeting held against the built system on Tue 1 Sep 2026. A
36-item change backlog plus 8 business definitions marked *"should not be hard-coded
until the business definition is confirmed"*. Tracked in **`BACKLOG.md`** — keep that
file as the status of record.

**The real SOP is still not on this machine.** The seven Manual-sourced workflows added
on 1 Sep cite §8–§18 correctly by section, but their step lists are a reconstruction,
not a transcription. Get the Manual before anyone treats them as authoritative.

### The organising idea
§36 forbids hard-coding eight definitions. So they are **rows in a `settings` table**,
every calculation reads them, and each ships `confirmed=0` carrying the question it is
waiting on. The screen says UNCONFIRMED until a named person answers. *A number nobody
has agreed is worse than a blank, because a blank does not get quoted in a board pack.*
This is also why `time.wait_counts_as_inprogress` is a switch: flipping it moves the
late-task count from 114 to 138, and that is a business decision, not a code one.

### What landed
- **Collaboration (#1–#4, #16, #20).** Two new routes — `CTR` cross-team request and
  `ESC` senior escalation — whose lanes are **bound to the chosen teams at raise time**
  (`@FROM` / `@TO` substituted in `open_case`). One route definition, every pair of
  departments. Plus `case_messages` (an update that does **not** close the case),
  acknowledgement against a configurable window, and a logged escalation ladder.
- **Priority separated from TAT (#5, #6).** Own column on cases/tasks/findings/
  coordination/llr, levels from settings, and `priority_log` so a change keeps its
  old value and reason.
- **Findings (#7–#10, #23).** `findings` table. A visit is now a **container**; each
  finding has its own category, place, owner, priority, TAT, evidence and outcome, and
  can become an NCR/RFI/task/lesson on its own. Recurrence is detected on
  (project, category, location) — the difference between "a marble complaint" and "the
  fourth marble complaint in the same lobby".
- **Lessons root cause (#15, #17).** why / where / whose / internal-external-dependency
  / days lost / preventive action, plus head and Audit visibility as settings, plus a
  separate improvement lifecycle.
- **New rails (19 total).** `today` (the landing surface), `settings`, `learning`,
  `delivery`; `exec`, `matrix` and `site` rewritten in `js/v3.js`.
- **Time model (#27–#31).** `wait_ext_days` and `hold_days` on tasks and stages,
  `expected_days` per stage from the catalog, a `time_log`, and task hold/resume.

### Files
`js/v3.js` is the review layer — it **overrides** `VIEWS.exec/matrix/site` and extends
`E.body.case/llr` rather than editing the earlier files, so the change reads as one
thing. `store.DEFINITIONS` is the §36 list. `catalog.DEPARTMENTS` is the 26-department
org (#18, Legal included).

### Verification
`python tests/run-all.py` — **51/51**, **63/63**, and `tests/v3check.py` renders
19 rails in headless Chrome with **0 console errors**. It rebuilds the database and
kills every stray listener first, because both suites assume a fresh database and
Windows will let two servers share the port. See `tests/README.md`.

---

## 13 · Concurrency incident, 2 Sep — read this

**Two Claude sessions edited this folder at the same time and both lost work.**

What it looked like: `server.py` ended up with two `_today`, two `_findings` and two
`_learning` methods and two route blocks, one of them dead code after an earlier
`return`; `actions.py` had two `case_message` and two `finding_resolve`; a `js/v3.js`
and a `definitions.py` appeared that this session never wrote, wired into
`index.html`. Their code queried a `visit_findings` table and a `grp` column that no
longer existed, because this session's write of `store.py` had replaced their schema.
`/api/today` and `/api/findings` returned 500; `/api/settings` returned 404.

Recovery: snapshot the whole folder first (`Desktop/pulsearch-COLLISION-SNAPSHOT-*`),
then excise the other line cleanly — their contributions were contiguous and marked
with a `v3 — Haroon register` banner, so 348 lines came out of `server.py` and 365 out
of `actions.py` in one cut each. Their `store.py` schema was unrecoverable, which is
what decided which line survived.

**Do not run two agents on this folder.** And:

- **There is still no git repo here.** That is the whole reason this was expensive.
  `git init` before anything else. It is the single highest-value thing left undone.
- **`Server.allow_reuse_address = True` lets two servers bind :4010 on Windows.** For
  half an hour the probes were hitting the *other* session's server while the file on
  disk was correct. Kill **every** listener, not "the" listener:
  `for PID in $(netstat -ano | grep ":4010 " | grep LISTENING | awk '{print $5}' | sort -u); do taskkill //PID $PID //F; done`
  then check the count is 1.
