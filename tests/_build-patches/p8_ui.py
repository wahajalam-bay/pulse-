"""Rails for the new surfaces, plus #11 (Add a Project) and #25 (SLA -> TAT)."""
import io
ROOT = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch"


def patch(fn, pairs):
    p = ROOT + "\\" + fn
    s = open(p, encoding="utf-8").read()
    done = skipped = 0
    for old, new in pairs:
        if old not in s:
            # already applied on an earlier run, or superseded — only tolerate
            # it when the intended result is demonstrably already there
            assert new in s, fn + " ANCHOR MISSING: " + old[:70]
            skipped += 1
            continue
        s = s.replace(old, new, 1)
        done += 1
    print(f"  {fn}: {done} applied, {skipped} already in place")
    open(p, "w", encoding="utf-8").write(s)


# ══════════════════════════════════════════════════════════════════════════
# app.js — four new rails, and today becomes the landing surface
# ══════════════════════════════════════════════════════════════════════════
patch("js/app.js", [
 # icons
 ("""  llr:'<path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2Z"/>',
};""",
  """  llr:'<path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2Z"/>',
  today:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/><path d="M12 2v2M22 12h-2M12 22v-2M2 12h2"/>',
  learning:'<path d="M3 7l9-4 9 4-9 4Z"/><path d="M7 10v5c0 1.7 2.2 3 5 3s5-1.3 5-3v-5"/>',
  delivery:'<path d="M3 17h2l2-9h9l2 5h3v4h-2"/><circle cx="7.5" cy="18.5" r="1.8"/><circle cx="17.5" cy="18.5" r="1.8"/>',
  settings:'<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>',
};"""),
 # nav order: today first, then the existing rails, with the new analysis rails
 ("""const NAV = [
  {k:"queue",   t:"My Queue",           h:"MY QUEUE"},
  {k:"exec",    t:"Executive Summary",   h:"EXECUTIVE SUMMARY"},""",
  """const NAV = [
  {k:"today",   t:"What should I do today?", h:"WHAT SHOULD I DO TODAY?"},
  {k:"queue",   t:"My Queue",           h:"MY QUEUE"},
  {k:"exec",    t:"Executive View",      h:"EXECUTIVE VIEW"},"""),
 ("""  {k:"llr",     t:"Lessons & Standards", h:"LESSONS & STANDARDS"},
  {k:"catalog", t:"Workflow Catalog",    h:"WORKFLOW CATALOG"},""",
  """  {k:"llr",     t:"Lessons & Standards", h:"LESSONS & STANDARDS"},
  {k:"learning",t:"Learning Summary",    h:"LEARNING SUMMARY"},
  {k:"delivery",t:"Delivery Cycle",      h:"DELIVERY CYCLE"},
  {k:"catalog", t:"Workflow Catalogue",  h:"WORKFLOW CATALOGUE"},"""),
 ("""  {k:"people",  t:"People",              h:"PEOPLE"},
];""",
  """  {k:"people",  t:"People",              h:"PEOPLE"},
  {k:"settings",t:"Definitions & TAT",   h:"BUSINESS DEFINITIONS"},
];"""),
 # subtitles
 ("""  queue:"Everything waiting on you — tasks, decisions, obligations. Start here.",""",
  """  today:"Action-oriented: what needs doing today, why it is here, and what the action is.",
  queue:"Everything waiting on you — tasks, decisions, obligations, in full detail.",
  learning:"Lessons turned into institutional knowledge — root cause, recurrence, improvement.",
  delivery:"Team execution vs waiting vs approval. MD approval excluded — §30 of the review.",
  settings:"The eight definitions Haroon's review said not to hard-code until confirmed.","""),
 ("""  exec:"Arch & Design at a glance — the spine, the queue, and where the time goes.",""",
  """  exec:"Department facts, workload bifurcation, and where the time actually goes.","""),
 ("""  matrix:"Every project against all 14 stations. Click a cell to open the project.",""",
  """  matrix:"Expected vs actual vs waiting vs hold, and whose delay it is.","""),
 ("""  catalog:"Design Workflow Booklet Vol.1 as data, conflicts included.",""",
  """  catalog:"46 workflows with purpose, trigger, TAT, gates and dependencies — §23.","""),
 # land on today
 ('  return NAV.some(n => n.k === h[0]) ? h[0] : "queue";',
  '  return NAV.some(n => n.k === h[0]) ? h[0] : "today";'),
 ('if (h[0] === "e" && h[1] && h[2]) { E.open(h[1], +h[2]); return NAV.some(n => n.k === TAB) ? TAB : "queue"; }',
  'if (h[0] === "e" && h[1] && h[2]) { E.open(h[1], +h[2]); return NAV.some(n => n.k === TAB) ? TAB : "today"; }'),
 ('let BOOT = null, TAB = "queue", CACHE = {};',
  'let BOOT = null, TAB = "today", CACHE = {};'),
])

# ══════════════════════════════════════════════════════════════════════════
# ui-actions.js — #11 wording, #25 SLA -> TAT, priority on the queue
# ══════════════════════════════════════════════════════════════════════════
patch("js/ui-actions.js", [
 ('<button class="btn" id="aProj">+ Open a project</button>',
  '<button class="btn" id="aProj">+ Add a project</button>'),
 # #25 — the cross-team timeline is a turnaround, so it reads TAT
 ('''  F.field("sla_days", "SLA (working days)", {type: "number", value: 3}) +''',
  '''  F.field("sla_days", "TAT (working days)", {type: "number", value: 3,
    hint: "§21 of the review: a cross-team timeline is a turnaround, so it is TAT."}) +
  F.field("priority", "Priority", {options: priOpts(), value: BOOT.priority_default}) +'''),
 ('''  <div class="actbar"><button class="btn pri" id="kNew">+ Ask another team</button></div>''',
  '''  <div class="actbar"><button class="btn pri" id="kNew">+ Ask another team</button>
    <button class="btn" id="kCTR">+ Raise a request to a team</button></div>'''),
 ('''  $("#kNew").onclick = () => UI.newAsk();
  UI.bind(p);
}''',
  '''  $("#kNew").onclick = () => UI.newAsk();
  $("#kCTR").onclick = () => UI.crossTeam();
  UI.bind(p);
}'''),
 # the coordination table header says TAT now
 ('''    <thead><tr><th>Project</th><th>Stage</th><th>From</th><th>Waiting on</th><th>Ask</th>
      <th class="num">SLA</th><th class="num">Age</th><th></th></tr></thead><tbody>''',
  '''    <thead><tr><th>Project</th><th>Stage</th><th>From</th><th>Waiting on</th><th>Ask</th>
      <th class="num">TAT</th><th class="num">Age</th><th></th></tr></thead><tbody>'''),
 ('''      <span class="mut">${b.n} open · <b>${b.days}d</b> ${b.over ? `· <span style="color:var(--bad)">${b.over} past SLA</span>` : ""}</span>''',
  '''      <span class="mut">${b.n} open · <b>${b.days}d</b> ${b.over ? `· <span style="color:var(--bad)">${b.over} past TAT</span>` : ""}</span>'''),
 # hold / resume on the task rail
 ('''        ${t.status === "queued" ? `<button class="btn sm" data-act="start" data-id="${t.id}">Start</button>` : ""}
        ${t.status !== "queued" && t.status !== "done" ? `<button class="btn sm" data-act="finish" data-id="${t.id}">Finish</button>` : ""}
        <button class="btn sm" data-note="task:${t.id}">Note</button>''',
  '''        ${t.status === "queued" ? `<button class="btn sm" data-act="start" data-id="${t.id}">Start</button>` : ""}
        ${t.status !== "queued" && t.status !== "done" && t.status !== "hold" ? `<button class="btn sm" data-act="finish" data-id="${t.id}">Finish</button>` : ""}
        ${t.status === "hold" ? `<button class="btn sm" data-act="resume" data-id="${t.id}">Resume</button>`
          : t.status !== "done" && t.status !== "queued" ? `<button class="btn sm" data-hold="${t.id}">Hold</button>` : ""}
        <button class="btn sm" data-note="task:${t.id}">Note</button>'''),
 ('''  root.querySelectorAll("[data-close]").forEach(b => b.onclick = async (ev) => {''',
  '''  root.querySelectorAll("[data-hold]").forEach(b => b.onclick = (ev) => {
    ev.stopPropagation(); UI.hold(+b.dataset.hold);
  });
  root.querySelectorAll("[data-close]").forEach(b => b.onclick = async (ev) => {'''),
])

# ══════════════════════════════════════════════════════════════════════════
# index.html — load the review layer
# ══════════════════════════════════════════════════════════════════════════
patch("index.html", [
 ('<script src="js/entity.js"></script>',
  '<script src="js/entity.js"></script>\n<script src="js/v3.js"></script>'),
])

# ══════════════════════════════════════════════════════════════════════════
# css — priority chips, heat cells, delay attribution, finding blocks
# ══════════════════════════════════════════════════════════════════════════
CSS = """

/* ── the 1 Sep review layer ─────────────────────────────────────────────── */

/* priority is not TAT, so it does not look like a status (#5 / #6) */
.chip.pri{font-weight:800;letter-spacing:.04em;text-transform:uppercase;font-size:9.5px}

/* a figure whose definition is still open says so, every time it appears */
.prov.warnprov{background:var(--st-late-t);color:#7C271D;cursor:pointer}
.prov.warnprov:hover{background:#F2D5D0}

/* settings values read as values, not prose */
code.setval{font-family:Consolas,ui-monospace,monospace;font-size:11.5px;
  background:var(--card-3);padding:2px 7px;border-radius:6px;display:inline-block;
  max-width:100%;overflow-wrap:anywhere}

/* workload heat (#22) — one channel, opacity, so it reads in both themes */
.cell.heat{background:color-mix(in srgb,var(--st-run) calc(var(--h) * 78%),var(--card-3));
  color:var(--ink);cursor:default;min-height:30px}
.cell.heat b{font-size:10.5px;font-weight:700;opacity:.85}
:root[data-theme="dark"] .cell.heat{color:#EAEEF3}

/* whose delay it is (#29) — a bar under the cell, not another colour on it */
.cell{position:relative}
.cell.own-internal:after,.cell.own-external:after,.cell.own-hold:after{
  content:"";position:absolute;left:5px;right:5px;bottom:2px;height:2.5px;
  border-radius:2px}
.cell.own-internal:after{background:var(--st-late)}
.cell.own-external:after{background:var(--st-wait)}
.cell.own-hold:after{background:var(--st-hold)}

/* the repeatable finding block (#7) */
.fblock{border:1px solid var(--line-2);border-radius:var(--r-md);padding:13px 14px 4px;
  margin-bottom:11px;background:var(--card-2)}
.fblock-h{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:11px;font-size:12px}
.fblock-h b{font-size:11px;text-transform:uppercase;letter-spacing:.09em;
  color:var(--ink-2)}
.zm-fld.nc{background:var(--st-late-t);border-radius:8px;padding:7px 9px;margin:-7px -9px 13px}

/* the today view leans on the table, so give the reason column room */
.tbl td[colspan]{padding:0}
"""

p = ROOT + "\\css\\zd-ui.css"
s = open(p, encoding="utf-8").read()
if "the 1 Sep review layer" not in s:
    open(p, "w", encoding="utf-8").write(s + CSS)
    print("patched css/zd-ui.css")
