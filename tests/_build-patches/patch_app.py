"""Patch js/app.js: two new rails, hash routing, and a clickable row everywhere."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\js\app.js"
src = open(PATH, encoding="utf-8").read()


def sub(old, new):
    global src
    assert old in src, "ANCHOR MISSING: " + old[:80]
    src = src.replace(old, new, 1)


# ══════════════════════════════════════════════════════════════════════════
# 1 · rails
# ══════════════════════════════════════════════════════════════════════════
sub("""  drawings:'<path d="M3 3h7v7H3zM14 3h7v18h-7zM3 14h7v7H3z"/>',
};""",
    """  drawings:'<path d="M3 3h7v7H3zM14 3h7v18h-7zM3 14h7v7H3z"/>',
  site:'<path d="M12 21s-7-5.5-7-11a7 7 0 0 1 14 0c0 5.5-7 11-7 11Z"/><circle cx="12" cy="10" r="2.6"/>',
  llr:'<path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2Z"/>',
};""")

sub("""  {k:"drawings",t:"Drawings & Issuance",h:"DRAWINGS & ISSUANCE"},
  {k:"catalog", t:"Workflow Catalog",    h:"WORKFLOW CATALOG"},""",
    """  {k:"drawings",t:"Drawings & Issuance",h:"DRAWINGS & ISSUANCE"},
  {k:"site",    t:"Site & Compliance",   h:"SITE & COMPLIANCE"},
  {k:"llr",     t:"Lessons & Standards", h:"LESSONS & STANDARDS"},
  {k:"catalog", t:"Workflow Catalog",    h:"WORKFLOW CATALOG"},""")

sub("""  drawings:"The drawing register and every formal issuance — Manual §5.",""",
    """  drawings:"The register, every revision, and which sheets went out on which transmittal — §5.",
  site:"Site visits, non-conformance and the authority file — §15, §16, §17.",
  llr:"Lessons learned, and the stage checklist they change — §7.6 and §4.2.",""")

sub("""  matrix:"Every project against all 13 stations. Click a cell to open the project.",""",
    """  matrix:"Every project against all 14 stations. Click a cell to open the project.",""")

# ══════════════════════════════════════════════════════════════════════════
# 2 · routing — a URL you can send someone
# ══════════════════════════════════════════════════════════════════════════
sub("""function go(k) { TAB = k; drawRail(); render(); }""",
    """function go(k) {
  TAB = k; drawRail();
  if (location.hash !== "#/" + k) history.replaceState(null, "", "#/" + k);
  render();
}

/* Deep links. #/tasks opens a rail, #/e/case/13 opens a record — so a finding can
   be sent to someone as a URL instead of "go to approvals and scroll". */
function fromHash() {
  const h = (location.hash || "").replace(/^#\\/?/, "").split("/");
  if (h[0] === "e" && h[1] && h[2]) { E.open(h[1], +h[2]); return NAV.some(n => n.k === TAB) ? TAB : "queue"; }
  return NAV.some(n => n.k === h[0]) ? h[0] : "queue";
}
window.addEventListener("hashchange", () => {
  const h = (location.hash || "").replace(/^#\\/?/, "").split("/");
  if (h[0] === "e" && h[1] && h[2]) return E.open(h[1], +h[2]);
  if (NAV.some(n => n.k === h[0]) && h[0] !== TAB) { TAB = h[0]; drawRail(); render(); }
});""")

# ══════════════════════════════════════════════════════════════════════════
# 3 · executive summary — the new registers, and honest labelling
# ══════════════════════════════════════════════════════════════════════════
start = src.index("/* ── 1 · executive ")
end = src.index("/* ── 2 · stage matrix ")
NEWEXEC = r'''/* ── 1 · executive ───────────────────────────────────────────────────── */
function vExec() {
  const k = BOOT.kpi, cs = BOOT.catalog_stats;
  const p = $("#page");
  p.innerHTML = `
  <div class="note"><b>Everything on this screen is live and every row opens.</b>
    The catalog, the spine, the routes and their sources, the PKR thresholds, the TAT
    conflicts, the people and the project names are transcribed from Design Workflow
    Booklet Vol.1 and the Guidelines Manual. Where a project sits on the spine, and the
    register history behind it, is seeded operating history so every surface has something
    to act on — it is generated FROM the stage each project has reached, so the registers
    and the spine can never disagree. Four of the twelve on-ground projects are not named
    in any document supplied and were not invented.</div>

  <div class="grid g4">
    <div class="card dark">
      <div class="k-lbl">Wait time booked outside the department</div>
      <div class="k-val">${n0(k.wait_days)}<span class="u">days</span></div>
      <div class="k-note">${k.wait_share}% of all elapsed time on Arch &amp; Design work was
        spent waiting on PM, Supply Chain, Finance, the Authority, vendors or stakeholders.
        <b>This is the number nobody can produce today.</b></div>
    </div>
    <div class="card clickcard" data-goto="matrix">
      <div class="k-lbl">Stages running late</div>
      <div class="k-val" style="color:${k.stages_late ? "var(--bad)" : "var(--good)"}">${k.stages_late}</div>
      <div class="k-note">Past planned end and still open, across ${k.projects} projects ×
        ${BOOT.stages.length} stations.</div>
    </div>
    <div class="card clickcard" data-goto="cases">
      <div class="k-lbl">Awaiting a decision</div>
      <div class="k-val">${k.open_cases}</div>
      <div class="k-note"><b>${k.cases_at_zd}</b> sit with Arch &amp; Design ·
        <b>${k.cases_stuck}</b> sit with a department that has no system yet.</div>
    </div>
    <div class="card clickcard" data-goto="oblig">
      <div class="k-lbl">Obligations missed</div>
      <div class="k-val" style="color:${k.oblig_missed ? "var(--bad)" : "var(--good)"}">${k.oblig_missed}</div>
      <div class="k-note">Weekly reviews, site visits and compliance reports past due —
        Manual §9 and §15.</div>
    </div>
  </div>

  <div class="sec"><h2>Where the department's time actually goes</h2>
    <p>Own time versus wait time, the split captured at every handoff.</p></div>
  <div class="card">
    ${clockBar(k.own_days, k.wait_days)}
    <div style="display:flex;justify-content:space-between;margin-top:9px;font-size:12px">
      <span><b>${n0(k.own_days)}d</b> own</span>
      <span><b>${n0(k.wait_days)}d</b> waiting on others</span></div>
    ${CLOCK_LEGEND}
  </div>

  <div class="sec"><h2>The construction years</h2>
    <p>Stage 13 used to be one label covering everything from an RFI to a handover.
      These are the Manual sections that now have a surface, a clock and a gate.</p></div>
  <div class="grid g4">
    <div class="card clickcard" data-goto="drawings">
      <div class="k-lbl">Sheets on the register</div>
      <div class="k-val sm">${n0(k.drawings)}</div>
      <div class="k-note"><b>${n0(k.sheets_issued)}</b> sheet-issuances recorded — which
        drawing, at which revision, to whom. §5.</div></div>
    <div class="card clickcard" data-goto="site">
      <div class="k-lbl">NCRs open</div>
      <div class="k-val sm" style="color:${k.ncr_open ? "var(--bad)" : "var(--good)"}">${k.ncr_open}</div>
      <div class="k-note">Raised by a site visit that found non-compliance. §15 → §16.</div></div>
    <div class="card clickcard" data-goto="site">
      <div class="k-lbl">Days with the Authority</div>
      <div class="k-val sm" style="color:var(--st-wait)">${n0(Math.round(k.authority_days))}</div>
      <div class="k-note">${k.authority_open} submissions and inspections open. §7 / §17.</div></div>
    <div class="card clickcard" data-goto="llr">
      <div class="k-lbl">Lessons adopted into the standard</div>
      <div class="k-val sm">${k.lessons_adopted}<span class="u">/ ${k.lessons_adopted + k.lessons_open}</span></div>
      <div class="k-note">${k.template_items} checks now live on the §4.2 template —
        the annexure the Manual marks “(to be added)”.</div></div>
  </div>

  <div class="sec"><h2>Open cross-team asks</h2>
    <p>Who owes Arch &amp; Design what, and for how long.</p></div>
  <div class="grid g4">
    <div class="card clickcard" data-goto="coord"><div class="k-lbl">Open asks</div>
      <div class="k-val sm">${k.coord_open}</div></div>
    <div class="card clickcard" data-goto="coord"><div class="k-lbl">Past their own SLA</div>
      <div class="k-val sm" style="color:${k.coord_over ? "var(--bad)" : "var(--good)"}">${k.coord_over}</div></div>
    <div class="card clickcard" data-goto="ledger"><div class="k-lbl">Blocked attempts logged</div>
      <div class="k-val sm" style="color:var(--st-wait)">${n0(k.blocked)}</div>
      <div class="k-note">Gate refusals and external-lane blocks. The count that justifies
        building the other departments' systems.</div></div>
    <div class="card clickcard" data-goto="catalog"><div class="k-lbl">Catalog loaded</div>
      <div class="k-val sm">${cs.workflows}<span class="u">workflows</span></div>
      <div class="k-note">${cs.from_booklet} from the booklet + <b>${cs.from_manual} from the
        Manual</b> · ${cs.steps} steps · ${cs.gates} gates</div></div>
  </div>

  ${BOOT.conflicts.length ? `
  <div class="sec"><h2>Blocking the SLA baseline</h2>
    <p>The booklet and the Guidelines Manual publish different overall TATs.</p></div>
  <div class="note warn">
    <b>${BOOT.conflicts.length} of 10 architecture stages carry two different published TATs.</b>
    Until Ahmed rules on which document is canonical, no SLA figure in this system can be
    defended. Both are stored; the Workflow Catalog rail lists every conflict, and each is
    already on the lessons register awaiting a ruling.
  </div>` : ""}

  <div class="sec"><h2>Still not answered</h2><p>Carried from the document review.
    Each of these is on the lessons register, so it has a status rather than living in
    a slide.</p></div>
  <div class="card"><table class="tbl">
    <tr class="rc" data-goto="llr"><td><b>TAT authority</b></td><td class="mut">Booklet vs Manual — 6 stages disagree, Manual disagrees with its own flowcharts on 3</td></tr>
    <tr><td><b>Working or calendar days?</b></td><td class="mut">No document states it. This build assumes working days, Mon–Fri.</td></tr>
    <tr><td><b>Creative scope</b></td><td class="mut">7 of 12 workflows have no project to attach to — parked on a "Department BAU" carrier</td></tr>
    <tr class="rc" data-goto="catalog"><td><b>${cs.unknown_tat} steps carry no duration</b></td><td class="mut">Topographical Survey and Structural Stability Ownership have a blank column in the booklet</td></tr>
    <tr><td><b>4 projects unnamed</b></td><td class="mut">Booklet says 12 on-ground; 8 are named on the cover. The rest were not invented.</td></tr>
    <tr class="rc" data-goto="llr"><td><b>MAR means three things</b></td><td class="mut">Design §11 / PM §5.3 / Supply Chain §4.2 — different scopes, different approval chains</td></tr>
  </table></div>`;
}

'''
src = src[:start] + NEWEXEC + src[end:]

# ══════════════════════════════════════════════════════════════════════════
# 4 · matrix — the project name opens the record
# ══════════════════════════════════════════════════════════════════════════
sub("""    <td class="pj">${esc(r.project.name)}<small>${esc(r.project.kind)} · ${esc(r.project.city)}</small></td>""",
    """    <td class="pj" style="cursor:pointer" data-e="project:${r.project.id}">${esc(r.project.name)}<small>${esc(r.project.kind)} · ${esc(r.project.city)}</small></td>""")

sub("""  <div class="note">Every project against all 13 stations of the spine — acquisition,
    the ten design stages, and construction support. <b>This replaces the master sheet.</b>""",
    """  <div class="note">Every project against all ${d.stages.length} stations of the spine —
    acquisition, the ten design stages, construction support, and <b>closeout</b>.
    Station 14 is new: before it, stage 13 ran forever and a project could never be
    finished. <b>This replaces the master sheet.</b>""")

# ══════════════════════════════════════════════════════════════════════════
# 5 · project insights — the registers, and rows that open
# ══════════════════════════════════════════════════════════════════════════
sub("""  <div class="actbar">
    <select class="btn" id="psel" style="padding:8px 12px">${opts}</select>
    <button class="btn" data-intake="${pid}">Intake (§3.1)</button>
    <button class="btn" id="pTask">+ Task</button>
    <button class="btn" id="pCase">+ Case</button>
    <button class="btn" id="pAsk">+ Ask</button>
    <button class="btn" id="pVisit">+ Site visit</button>
  </div>""",
    """  <div class="actbar">
    <select class="btn" id="psel" style="padding:8px 12px">${opts}</select>
    <button class="btn pri" data-e="project:${pid}">Open the record</button>
    <button class="btn" data-intake="${pid}">Intake (§3.1)</button>
    <button class="btn" id="pTask">+ Task</button>
    <button class="btn" id="pCase">+ Case</button>
    <button class="btn" id="pAsk">+ Ask</button>
    <button class="btn" id="pVisit">+ Site visit</button>
    <button class="btn" id="pLLR">+ Lesson</button>
  </div>""")

sub("""  <div class="grid g4">
    <div class="card"><div class="k-lbl">Stage reached</div>
      <div class="k-val sm">${d.stages.filter(s => s.status === "done").length}<span class="u">/ 13</span></div></div>""",
    """  <div class="grid g4">
    <div class="card"><div class="k-lbl">Stations signed off</div>
      <div class="k-val sm">${d.stages.filter(s => s.status === "done").length}<span class="u">/ ${d.stages.length}</span></div></div>""")

sub("""      <td style="white-space:nowrap">
        ${s.status === "not_started"
          ? `<button class="btn sm" data-stage="${pid}:${s.stage}:not_started">Initiate</button>`
          : s.status === "running"
          ? `<button class="btn sm" data-chk="${pid}:${s.stage}">Checklist</button>
             <button class="btn sm" data-stage="${pid}:${s.stage}:running">Sign off</button>`
          : `<button class="btn sm" data-chk="${pid}:${s.stage}">Checklist</button>`}
      </td></tr>`).join("")}""",
    """      <td class="mut">${s.checklist
        ? `${s.checks_done || 0}/${s.checks || 0}${s.checklist.signed_at
            ? ` <span class="chip c-done">signed</span>` : ""}`
        : `<span class="mut">—</span>`}</td>
      <td style="white-space:nowrap">
        ${s.status === "not_started"
          ? `<button class="btn sm" data-stage="${pid}:${s.stage}:not_started">Initiate</button>`
          : s.status === "running"
          ? `<button class="btn sm" data-chk="${pid}:${s.stage}">Checklist</button>
             <button class="btn sm" data-stage="${pid}:${s.stage}:running">Sign off</button>`
          : `<button class="btn sm" data-chk="${pid}:${s.stage}">Checklist</button>`}
      </td></tr>`).join("")}""")

sub("""    <thead><tr><th>#</th><th>Stage</th><th>Status</th><th class="num">Own</th>
      <th class="num">Wait</th><th>Planned end</th><th></th></tr></thead><tbody>""",
    """    <thead><tr><th>#</th><th>Stage</th><th>Status</th><th class="num">Own</th>
      <th class="num">Wait</th><th>Planned end</th><th>Checklist</th><th></th></tr></thead><tbody>""")

sub("""  <div class="sec"><h2>Open with someone else</h2>
    <p>Cross-team asks on this project that have not come back.</p></div>
  <div class="card">${d.coordination.length ? `<table class="tbl">
    <thead><tr><th>From</th><th>Waiting on</th><th>Ask</th><th class="num">SLA</th>
      <th class="num">Age</th></tr></thead><tbody>
    ${d.coordination.map(c => `<tr>""",
    """  <div class="sec"><h2>Open with someone else</h2>
    <p>Cross-team asks on this project that have not come back.</p></div>
  <div class="card">${d.coordination.length ? `<table class="tbl">
    <thead><tr><th>From</th><th>Waiting on</th><th>Ask</th><th class="num">SLA</th>
      <th class="num">Age</th></tr></thead><tbody>
    ${d.coordination.map(c => `<tr class="rc" data-e="coordination:${c.id}">""")

sub("""  <div class="sec"><h2>Open cases</h2></div>
  <div class="card">${d.cases.length ? `<table class="tbl">
    <thead><tr><th>Ref</th><th>Type</th><th>Title</th><th class="num">Value</th><th>Status</th></tr></thead>
    <tbody>${d.cases.map(c => `<tr><td><b>${esc(c.ref)}</b></td><td>${esc(c.type)}</td>
      <td>${esc(c.title)}</td><td class="num mut">${pkr(c.value_pkr)}</td>
      <td>${stChip(c.status === "open" ? "running" : "done")}</td></tr>`).join("")}</tbody>
    </table>` : `<div class="empty">No cases.</div>`}</div>`;""",
    """  <div class="sec"><h2>Cases on this project</h2></div>
  <div class="card">${d.cases.length ? `<table class="tbl">
    <thead><tr><th>Ref</th><th>Type</th><th>Title</th><th class="num">Value</th><th>Status</th></tr></thead>
    <tbody>${d.cases.map(c => `<tr class="rc" data-e="case:${c.id}">
      <td><b>${esc(c.ref)}</b></td><td>${esc(c.type)}</td>
      <td>${esc(c.title)}</td><td class="num mut">${pkr(c.value_pkr)}</td>
      <td>${stChip(c.status === "open" ? "running" : c.status === "rejected" ? "hold" : "done")}</td>
      </tr>`).join("")}</tbody>
    </table>` : `<div class="empty">No cases.</div>`}</div>

  <div class="sec"><h2>The registers</h2>
    <p>Everything this project has produced or is waiting on. Every row opens.</p></div>
  <div class="grid g2">
    <div class="card"><h3>Drawings &amp; issuance</h3>
      <div class="sub">${d.drawings.length} sheets · ${d.transmittals.length} transmittals ·
        ${d.drawings.filter(x => x.status === "IFC").length} issued for construction</div>
      ${d.transmittals.length ? `<table class="tbl"><tbody>${d.transmittals.slice(0, 6).map(t => `
        <tr class="rc" data-e="transmittal:${t.id}"><td><b>${esc(t.ref)}</b></td>
        <td>${esc(t.phase)}</td><td class="num mut">${dash(t.drawing_count)} sheets</td>
        <td class="mut">${esc((t.issued_at || "").slice(0, 10))}</td></tr>`).join("")}</tbody></table>`
        : `<div class="emptyx"><b>Nothing issued</b></div>`}
      <div style="margin-top:9px"><button class="btn sm" data-goto="drawings:${pid}">Open the register →</button></div>
    </div>
    <div class="card"><h3>Authority file</h3>
      <div class="sub">${d.authority.length} records ·
        ${d.authority.filter(a => a.status !== "approved").length} still open</div>
      ${d.authority.length ? `<table class="tbl"><tbody>${d.authority.map(a => `
        <tr class="rc" data-e="authority:${a.id}"><td><b>${esc(a.ref)}</b></td>
        <td>${esc(a.authority)}</td>
        <td><span class="chip ${a.status === "approved" ? "c-done" : "c-wait"}">${esc(a.status)}</span></td>
        <td class="num mut">${a.age}d</td></tr>`).join("")}</tbody></table>`
        : `<div class="emptyx"><b>Nothing submitted</b></div>`}
    </div>
    <div class="card"><h3>Site visits — §15</h3>
      <div class="sub">${d.visits.length} logged ·
        ${d.visits.filter(v => v.non_compliance).length} found non-compliance</div>
      ${d.visits.length ? `<table class="tbl"><tbody>${d.visits.slice(0, 6).map(v => `
        <tr class="rc" data-e="visit:${v.id}"><td class="mut">${esc(v.visited_on)}</td>
        <td>${esc((v.findings || "").slice(0, 60))}…</td>
        <td>${v.non_compliance ? `<span class="chip c-late">NCR</span>`
          : `<span class="chip c-done">clean</span>`}</td></tr>`).join("")}</tbody></table>`
        : `<div class="emptyx"><b>No visits logged</b></div>`}
    </div>
    <div class="card"><h3>Lessons learned — §7.6</h3>
      <div class="sub">${d.lessons.length} raised on this project</div>
      ${d.lessons.length ? `<table class="tbl"><tbody>${d.lessons.map(l => `
        <tr class="rc" data-e="llr:${l.id}"><td><b>${esc(l.title.slice(0, 60))}</b></td>
        <td><span class="chip ${l.status === "adopted" ? "c-done" : "c-queue"}">${esc(l.status)}</span></td>
        </tr>`).join("")}</tbody></table>`
        : `<div class="emptyx"><b>Nothing recorded</b>A project that produced no lessons
           either went perfectly or nobody wrote them down.</div>`}
    </div>
  </div>`;""")

sub("""  $("#pVisit").onclick = () => UI.newVisit(pid);
  UI.bind(p);""",
    """  $("#pVisit").onclick = () => UI.newVisit(pid);
  $("#pLLR").onclick = () => UI.newLLR(pid);
  UI.bind(p);""")

# ══════════════════════════════════════════════════════════════════════════
# 6 · approvals inbox — ten routes, and the card opens the case
# ══════════════════════════════════════════════════════════════════════════
sub("""  const card = r => `
  <div class="card" style="margin-bottom:12px">""",
    """  const card = r => `
  <div class="card" style="margin-bottom:12px;cursor:pointer" data-e="case:${r.id}">""")

sub("""        <h3>${esc(r.ref)} · ${esc(r.title)}</h3>""",
    """        <h3>${esc(r.ref)} · ${esc(r.title)} <span class="kl">open →</span></h3>""")

sub("""  <div class="note">One engine, ${d.routes.length} route definitions — MAR, DCR, RFI, shop drawings
    and third-party vetting are the same object with different lanes. Lanes marked
    <b>external</b> belong to a department whose system does not exist yet: they hold the
    clock and record the wait, and become live lanes the day that system connects.</div>""",
    """  <div class="note">One engine, <b>${d.routes.length} route definitions</b> —
    ${esc(d.routes.join(" · "))}. They are the same object with different lanes, so adding
    the five that were missing (value engineering, non-conformance, BOQ endorsement,
    material sampling, as-built closeout) changed one table and no code. Lanes marked
    <b>external</b> belong to a department whose system does not exist yet: they hold the
    clock and record the wait, and become live lanes the day that system connects.</div>""")

# ══════════════════════════════════════════════════════════════════════════
# 7 · coordination, tasks, obligations, ledger, people, team — rows open
# ══════════════════════════════════════════════════════════════════════════
sub("""    ${d.rows.sort((a, b) => b.age - a.age).map(r => `<tr>
      <td>${esc(r.pcode || "")}</td><td class="mut">${r.stage}</td>""",
    """    ${d.rows.sort((a, b) => b.age - a.age).map(r => `<tr class="rc" data-e="coordination:${r.id}">
      <td>${esc(r.pcode || "")}</td><td class="mut">${r.stage}</td>""")

sub("""  $("#kNew").onclick = () => UI.newAsk();
  p.querySelectorAll("[data-close]").forEach(b => b.onclick = async () => {
    b.disabled = true;
    await api("/api/coordination/close", {method: "POST", body: JSON.stringify({id: +b.dataset.close})});
    CACHE.matrix = null; render();
  });
}""",
    """  $("#kNew").onclick = () => UI.newAsk();
  UI.bind(p);
}""")

sub("""    ${d.rows.map(t => `<tr>
      <td class="mut">${esc(pn[t.project_id] || "")}</td>
      <td class="mut">${t.stage}</td><td>${esc(t.team)}</td>""",
    """    ${d.rows.map(t => `<tr class="rc" data-e="task:${t.id}">
      <td class="mut">${esc(pn[t.project_id] || "")}</td>
      <td class="mut">${t.stage}</td><td>${esc(t.team)}</td>""")

sub("""    <tbody>${d.rows.map(r => `<tr>
      <td><b>${esc(r.label)}</b></td>
      <td class="mut">${esc(r.pname || "Department")}</td>""",
    """    <tbody>${d.rows.map(r => `<tr class="rc" data-e="obligation:${r.id}">
      <td><b>${esc(r.label)}</b></td>
      <td class="mut">${esc(r.pname || "Department")}</td>""")

sub("""    ${d.rows.map(r => `<tr style="${r.blocked ? "background:var(--st-wait-t)" : ""}">
      <td class="mut" style="white-space:nowrap">${esc((r.at || "").replace("T", " ").slice(0, 16))}</td>""",
    """    ${d.rows.map(r => `<tr class="${LEDGER_KINDS[r.entity] && r.entity_id ? "rc" : ""}"
      ${LEDGER_KINDS[r.entity] && r.entity_id ? `data-e="${r.entity}:${r.entity_id}"` : ""}
      style="${r.blocked ? "background:var(--st-wait-t)" : ""}">
      <td class="mut" style="white-space:nowrap">${esc((r.at || "").replace("T", " ").slice(0, 16))}</td>""")

sub("""/* ── 10 · ledger ─────────────────────────────────────────────────────── */""",
    """/* Entities the drawer knows how to open — a ledger row for a template edit or a
   system seed has nothing to open, and should not pretend it does. */
const LEDGER_KINDS = {project:1, task:1, case:1, drawing:1, transmittal:1,
  coordination:1, obligation:1, visit:1, llr:1, authority:1};

/* ── 10 · ledger ─────────────────────────────────────────────────────── */""")

sub("""    <tbody>${d.people.map(x => `<tr><td><b>${esc(x.name)}</b></td>
      <td class="mut">${esc(x.designation || "")}</td><td class="mut">${esc(x.role)}</td></tr>`).join("")}""",
    """    <tbody>${d.people.map(x => `<tr class="rc" data-e="person:${x.id}">
      <td><b>${esc(x.name)}</b></td>
      <td class="mut">${esc(x.designation || "")}</td><td class="mut">${esc(x.role)}</td></tr>`).join("")}""")

sub("""      <table class="tbl"><tbody>${list.map(x => `<tr>
        <td><b>${esc(x.name)}</b></td><td class="mut">${esc(x.designation || "")}</td>
        <td class="mut" style="width:70px">T${x.tier}</td></tr>`).join("")}</tbody></table>""",
    """      <table class="tbl"><tbody>${list.map(x => `<tr class="rc" data-e="person:${x.id}">
        <td><b>${esc(x.name)}</b></td><td class="mut">${esc(x.designation || "")}</td>
        <td class="mut" style="width:70px">T${x.tier}</td></tr>`).join("")}</tbody></table>""")

sub("""  p.querySelectorAll("[data-team]").forEach(b => b.onclick = () => { CACHE.team = b.dataset.team; render(); });
}""",
    """  p.querySelectorAll("[data-team]").forEach(b => b.onclick = () => { CACHE.team = b.dataset.team; render(); });
  UI.bind(p);
}""")

sub("""<tbody>${d.owed.slice(0, 25).map(o => `<tr>""",
    """<tbody>${d.owed.slice(0, 25).map(o => `<tr class="rc" data-e="coordination:${o.id}">""")

# ══════════════════════════════════════════════════════════════════════════
# 8 · workflow catalog — provenance, and a step you can open
# ══════════════════════════════════════════════════════════════════════════
start = src.index("/* ── 9 · catalog ")
end = src.index("/* Entities the drawer knows")
NEWCAT = r'''/* ── 9 · catalog ─────────────────────────────────────────────────────── */
async function vCatalog() {
  const d = CACHE.cat || (CACHE.cat = await api("/api/catalog"));
  const p = $("#page");
  const team = CACHE.cteam || (CACHE.cteam = "Architecture");
  const srcf = CACHE.csrc || (CACHE.csrc = "");
  const wmeta = {};
  (d.workflows || []).forEach(w => (wmeta[w.team + "|" + w.workflow] = w));
  let rows = d.rows.filter(r => r.team === team);
  if (srcf === "booklet") rows = rows.filter(r => r.source === d.booklet);
  if (srcf === "manual") rows = rows.filter(r => r.source !== d.booklet);
  const byWf = {};
  rows.forEach(r => (byWf[r.workflow] = byWf[r.workflow] || []).push(r));

  p.innerHTML = `
  <div class="note">The department's process, as data. <b>${d.stats.workflows} workflows ·
    ${d.stats.steps} steps · ${d.stats.rework_points} rework loops · ${d.stats.gates} gates ·
    ${d.stats.stations} stations.</b> ${d.stats.from_booklet} workflows are transcribed from
    Design Workflow Booklet Vol.1. <b>${d.stats.from_manual} are transcribed from the
    Guidelines Manual's prose</b> — value engineering (§8), BOQ endorsement (§10),
    finishing and sampling (§12), QA/QC coordination (§16), regulatory inspection support
    (§17), closeout and as-built (§18) and the lessons-learned review (§7.6). The booklet
    never drew a swimlane for any of them, and they are where a project spends its last
    three years. Every step carries its source. Click a step to see where it is live.</div>

  ${d.conflicts.length ? `<div class="note warn">
    <b>${d.conflicts.length} TAT conflicts between the Booklet and the Guidelines Manual §4.0.</b>
    Both are stored; neither is silently preferred. Until this is ruled on, no SLA number here is defensible.
    <table class="tbl" style="margin-top:10px">
      <thead><tr><th>Stage</th><th>Workflow</th><th>Booklet</th><th>Manual</th></tr></thead>
      <tbody>${d.conflicts.map(c => `<tr><td>${c.stage}</td><td><b>${esc(c.workflow)}</b></td>
        <td>${esc(c.booklet)}</td><td>${esc(c.manual)}</td></tr>`).join("")}</tbody></table>
  </div>` : ""}

  ${d.stats.unknown_tat ? `<div class="note warn"><b>${d.stats.unknown_tat} steps have no duration
    at all</b> — the source's duration column is blank, or the step waits on a party outside
    the department with no committed date. They render as "—", never as zero, because a zero
    would quietly deflate every rollup.</div>` : ""}

  <div class="pills">${["Architecture", "MEP", "Structure", "Creative"].map(t =>
    `<button class="pill ${t === team ? "on" : ""}" data-ct="${t}">${t}</button>`).join("")}
    <span style="width:14px"></span>
    ${[["", "Both sources"], ["booklet", "Booklet Vol.1"], ["manual", "From the Manual"]].map(
      ([v, l]) => `<button class="pill ${srcf === v ? "on" : ""}" data-cs="${v}">${l}</button>`).join("")}
  </div>

  ${Object.keys(byWf).length ? Object.entries(byWf).map(([wf, steps]) => {
    const s0 = steps[0], sum = steps.reduce((a, b) => a + (b.tat_days || 0), 0);
    const meta = wmeta[team + "|" + wf] || {};
    const fromManual = s0.source !== d.booklet;
    return `<div class="card" style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px">
        <div><h3>${esc(wf)}</h3>
          <div class="sub">Stage ${s0.stage} · ${steps.length} steps · steps sum to ${sum} working days
            ${meta.unknown ? ` · ${meta.unknown} with no duration` : ""}
            ${meta.external ? ` · ${meta.external} outside the department` : ""}</div>
          <span class="prov ${fromManual ? "manual" : ""}">${esc(s0.source || "")}</span></div>
        <div style="text-align:right">
          <div class="chip c-run">Booklet ${esc(s0.tat_booklet || "—")}</div>
          ${s0.tat_manual ? `<div class="chip ${s0.tat_manual !== s0.tat_booklet ? "c-late" : "c-done"}"
             style="margin-top:4px">Manual ${esc(s0.tat_manual)}</div>` : ""}
        </div></div>
      <table class="tbl" style="margin-top:11px"><tbody>
      ${steps.map(r => `<tr class="rc" data-e="product:${r.id}">
        <td class="mut" style="width:26px">${r.seq}</td>
        <td><b>${esc(r.step)}</b></td>
        <td style="width:130px">${r.is_external ? `<span class="chip c-ext">${esc(r.lane)}</span>` : ""}</td>
        <td class="num" style="width:60px">${r.tat_days == null ? '<span class="mut">—</span>' : r.tat_days + "d"}</td>
        <td style="width:150px">
          ${r.maker ? '<span class="chip c-queue">maker</span> ' : ""}
          ${r.checker ? '<span class="chip c-run">checker</span> ' : ""}
          ${r.rework ? '<span class="chip c-hold">rework</span> ' : ""}
          ${r.gate ? '<span class="chip c-late">gate</span>' : ""}</td></tr>`).join("")}
      </tbody></table></div>`;
  }).join("") : `<div class="emptyx"><b>Nothing matches that filter</b>${team} has no
    workflows from that source.</div>`}`;

  p.querySelectorAll("[data-ct]").forEach(b => b.onclick = () => { CACHE.cteam = b.dataset.ct; render(); });
  p.querySelectorAll("[data-cs]").forEach(b => b.onclick = () => { CACHE.csrc = b.dataset.cs; render(); });
  UI.bind(p);
}

'''
src = src[:start] + NEWCAT + src[end:]

# ══════════════════════════════════════════════════════════════════════════
# 9 · header: search, the bell, and a refreshed badge after every render
# ══════════════════════════════════════════════════════════════════════════
sub("""async function render() {
  const n = NAV.find(x => x.k === TAB);
  $("#headTitle").textContent = n.h;
  $("#headSub").textContent = SUB[TAB] || "";
  $("#page").innerHTML = `<div class="empty">Loading…</div>`;
  try { await VIEWS[TAB](); }""",
    """async function render() {
  const n = NAV.find(x => x.k === TAB);
  $("#headTitle").textContent = n.h;
  $("#headSub").textContent = SUB[TAB] || "";
  $("#page").innerHTML = `<div class="empty">Loading…</div>`;
  E.badge();
  try { await VIEWS[TAB](); }""")

sub("""  drawRail();
  render();
})();""",
    """  $("#hSearch").onclick = () => E.pal();
  $("#hBell").onclick = (ev) => { ev.stopPropagation(); E.notify(); };
  TAB = fromHash();
  drawRail();
  render();
})();""")

open(PATH, "w", encoding="utf-8").write(src)
print("app.js patched")
