# ZD PULSE — implementation backlog

Source: **Haroon's review, Tuesday 1 September 2026** — `ARCH AND DESIGN (1).docx`
(byte-identical to `HAROON-REGISTER-1SEP.docx`; the `.txt` is the same content).

> This file is the tracker for §35 "Consolidated Change List" and §36 "Items
> Requiring Definition Before Final Development". Update the Status column as
> items land. Do not delete rows — a rejected item is as interesting as a done one.

**A note on what this document is.** It is not the Architecture & Design SOP. It is
the register of a review meeting held against the built system. That matters for
provenance: the 46-workflow catalog is still sourced from Booklet Vol.1 + the
Guidelines Manual, and nothing in this file changes those citations.

---

## §36 · Business definitions — MUST NOT be hard-coded

Haroon's instruction is explicit: these are not to be fixed in code until the
business confirms them. They are therefore implemented as **editable settings that
ship marked UNCONFIRMED**, every one carrying the question that has to be answered
and the name of whoever answers it. Every calculation reads the setting; nothing
reads a constant.

| Ref | Definition | Status |
|---|---|---|
| A | 24-hour acknowledgement — calendar, business hours, or working days? | ⚙ configurable · UNCONFIRMED |
| B | Priority levels and the rules for changing priority | ⚙ configurable · UNCONFIRMED |
| C | Where SLA applies vs where TAT applies | ⚙ configurable · UNCONFIRMED |
| D | Formal definitions and calculation rules for Wait / Hold / In Progress | ⚙ configurable · UNCONFIRMED |
| E | Whether Own Time is active execution time or something else | ⚙ configurable · UNCONFIRMED |
| F | All exclusions from Delivery Time, including MD approval | ⚙ configurable · UNCONFIRMED |
| G | The SLA baseline discrepancy — booklet vs Manual §4.0 | ⚙ surfaced, unresolved · needs Ahmed |
| H | Consolidate and validate the Workflow Catalogue before it is the baseline | ⚙ built, needs validation |

---

## §35 · Consolidated change list

| # | Area | Required update | Priority | Status |
|---|---|---|---|---|
| 1 | Raise a Case | Cross-team case/request routing | High | ✅ done |
| 2 | Cross-Team Communication | Back-and-forth communication | High | ✅ done |
| 3 | Acknowledgement | Track first response within 24 hours | High | ✅ done (window configurable — §36 A) |
| 4 | Escalation | Escalate when response is missed | High | ✅ done |
| 5 | Priority | Configurable priority levels | High | ✅ done |
| 6 | TAT/SLA | Separate Priority from TAT/SLA | High | ✅ done |
| 7 | Visit | Support multiple structured findings | High | ✅ done |
| 8 | Visit Evidence | Attach pictures, reports, video, documents | High | ✅ done (link register) |
| 9 | Visit → RFI | Assign individual findings to relevant teams | High | ✅ done |
| 10 | Historical Data | Show previous visit/finding history | High | ✅ done (incl. recurrence) |
| 11 | Project | Rename "Open a Project" → "Add a Project" | Medium | ✅ done |
| 12 | Decisions | Add TAT and due-date visibility | High | ✅ done |
| 13 | Daily Actions | "What should I do today?" view | High | ✅ done |
| 14 | Lessons Learned | Dedicated Lessons Learned functionality | High | ✅ done (1 Sep build) |
| 15 | Lessons Learned | Push visibility to Heads and Audit | High | ✅ done |
| 16 | Learning | Learning Summary page | High | ✅ done |
| 17 | Root Cause | Capture why TAT/SLA took too long | High | ✅ done |
| 18 | Departments | Expand discipline/department list, incl. Legal | Medium | ✅ done |
| 19 | Collaboration | Cross-module/system collaboration | High | ✅ done (linked records) |
| 20 | Senior Management | Senior-level cross-department collaboration | High | ✅ done |
| 21 | Executive View | Department-level overview/facts | High | ✅ done |
| 22 | Executive View | Workload/department bifurcation over time | High | ✅ done |
| 23 | Site Compliance | Attach evidence to non-compliance | High | ✅ done |
| 24 | PM/Asana | Account for existing PM/Asana workflow | Medium | ⛔ needs Asana API access — see below |
| 25 | Cross-Team Tasks | Change SLA terminology to TAT | Medium | ✅ done |
| 26 | SLA Baseline | Resolve baseline discrepancy | **Critical** | ⚙ surfaced, needs Ahmed's ruling |
| 27 | Workflow Catalogue | Consolidate all workflows | **Critical** | ◐ partial — see below |
| 28 | Project Stage Matrix | Stage timing through heatmap | High | ✅ done (5 time categories) |
| 29 | Delay Analysis | Separate internal vs external waiting | High | ✅ done |
| 30 | Time Definitions | Define Wait, Hold, In Progress | **Critical** | ⚙ configurable · UNCONFIRMED |
| 31 | Own Time | Clarify relationship with Hold/Blocking | **Critical** | ⚙ configurable · UNCONFIRMED |
| 32 | Delivery Cycle | Refine calculation logic | **Critical** | ✅ done, exclusions configurable |
| 33 | MD Approval | Exclude MD approval from Delivery Time | High | ✅ done (default excluded, configurable) |
| 34 | Approval Inbox | Strengthen action-oriented information | Medium | ✅ done |
| 35 | Coordination Ledger | Show who is waiting on whom | High | ✅ done |
| 36 | Task Management | Link tasks to originating workflows | High | ✅ done |

### #27 — what the catalogue has, and what it still lacks

§23 lists fifteen attributes per workflow. Eleven are now derived from the catalog
itself, so they cannot drift from the steps they describe: **name, trigger** (its first
step), **receiving team** (the external lanes it touches), **stages, TAT, dependencies,
completion criteria** (its gate), **management visibility, gates, rework points** and
**source**. Four are still missing because they are editorial, not derivable, and
nobody has written them:

- **Purpose** — one line per workflow. Needs Ahmed.
- **Requestor** — currently the owning team; the real answer is a role.
- **Priority** — no per-workflow default; priority is currently per item.
- **Escalation rules** — currently one global ladder, not per workflow.

The doc says the catalogue must be *"consolidated and validated"* before it is the
development baseline (§36 H). It is consolidated. It is **not** validated.

### Not done, and why

- **#24 PM / Asana integration.** Cannot be built without Asana API credentials and a
  decision on direction of truth (does ZD push tasks to Asana, read them, or both?).
  The groundwork is in: every case, task and finding carries an `external_ref` and an
  `external_system` field, so a PM item can be pointed at its Asana task today and
  synced when access exists. Question for Haroon: **who owns the task once it is in
  both systems?**
- **#7 (§7 of the doc) Drive / Excel as backup.** No migration or archival strategy has
  been agreed. Nothing in this build deletes or supersedes an existing source; the
  document register links to Drive rather than replacing it.
- **#26 / §36 G — the SLA baseline.** Still six stages where Booklet Vol.1 and
  Guidelines Manual §4.0 disagree. Both values are stored and the conflict is shown on
  the Workflow Catalogue rail and on the lessons register. **This is Ahmed's ruling to
  make and the doc says not to lock the baseline until it is made.**

---

## §37 · The target operating model, as the doc states it

```
Request / Issue / Visit / Project Activity
  → Structured Workflow → Responsible Team
  → TAT + Priority + SLA
  → Communication / Collaboration → Escalation where required
  → Resolution / Approval → Historical Record
  → Performance Measurement → Lesson Learned
  → Management Insight / Process Improvement
```

Every arrow in that chain is now a real transition in the system with a clock on it.
The one that was missing entirely before this build is
**Communication / Collaboration → Escalation**, which is why §38 Priority 3 was the
largest single piece of work.

---

## Verification

Two suites drive every flow above through the HTTP API against a freshly rebuilt
database, and the app is then driven in headless Chrome:

| Suite | Covers | Result |
|---|---|---|
| `tests/e2e.py` | the 1 Sep build — visit→NCR, template stamping, the §7.6 loop, transmittal sheet lists, drawing revisions, the authority clock, closeout gates, search, the drawer | **51/51** |
| `tests/e2e_v3.py` | this build — cross-team routing, acknowledgement, threads, escalation, priority history, five findings on one visit, recurrence, finding→RFI, root cause, hold, and every §36 setting actually changing the numbers | **63/63** |
| `tests/v3check.py` | 19 rails rendered in Chrome, the cross-team drawer, the finding drawer, the definitions rail | **0 console errors** |

The §36 switches are tested by flipping them and asserting the figures move:
turning on "count Wait as In Progress" changed the late-task count from 114 to 138.
That is the point of them being settings — the number is not an opinion held in code.
