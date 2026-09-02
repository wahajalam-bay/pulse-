/* ZD PULSE — the 1 Sep review layer.

   Every surface in this file traces to a numbered item in Haroon's review of
   1 September 2026 (`ARCH AND DESIGN (1).docx`, tracked in BACKLOG.md). It is a
   separate file so the change can be read as one thing, and so the earlier build
   stays legible underneath it.

   Loaded after app.js / ui-actions.js / entity.js, so it can override a rail
   that already existed (exec, matrix, site) rather than the earlier file having
   to know this change was coming.

   THE ONE IDEA THAT SHAPES ALL OF IT
     §36 of the review says eight business definitions "should not be hard-coded
     until the business definition is confirmed". So this layer never states a
     performance figure without also being able to say which definition produced
     it — and it labels a figure UNCONFIRMED when the definition behind it has
     not been agreed. A number nobody has signed off is worse than a blank,
     because a blank does not get quoted in a board pack.
*/

/* ── priority, which is NOT TAT (#5 / #6) ──────────────────────────────── */
const PRI_CLASS = {Critical: "c-late", High: "c-hold", Medium: "c-run", Low: "c-queue"};
const priChip = (p) => p
  ? `<span class="chip ${PRI_CLASS[p] || "c-queue"} pri">${esc(p)}</span>`
  : `<span class="mut">—</span>`;
const priOpts = () => (BOOT.priorities || ["Critical", "High", "Medium", "Low"]);

/* a TAT figure whose definition is still open gets marked, every time */
const unconf = (n) => (BOOT.unconfirmed
  ? ` <span class="prov warnprov" data-goto="settings" title="The definition behind this
      number is not confirmed — Haroon's review §36">unconfirmed</span>` : "");

const DAYS = (v, cls) => v ? `<b class="${cls || ""}">${n0(v)}d</b>`
                           : `<span class="mut">—</span>`;

/* ═══════════════════════════════════════════════════════════════════════════
   #13 · "What should I do today?"  Asked for by name.
   ═══════════════════════════════════════════════════════════════════════════ */
VIEWS.today = async function () {
  const d = await api("/api/today");
  const p = $("#page");
  const order = ["Acknowledge", "Decide", "My work", "Site findings",
                 "Compliance", "Rule on", "Define"];
  const groups = {};
  d.rows.forEach(r => (groups[r.bucket] = groups[r.bucket] || []).push(r));
  const names = Object.keys(groups).sort(
    (a, b) => (order.indexOf(a) + 99) % 99 - (order.indexOf(b) + 99) % 99);

  p.innerHTML = `
  <div class="note">The review asked for this in these words: <b>“What should I do
    today?”</b> — an action-oriented view rather than another list of pending things.
    So every row says <b>why it is here</b> and <b>what the action is</b>, and the sort is
    priority first, lateness second. A Critical two days late outranks a Low three weeks
    late, which the old queue could not express because priority and TAT were the same
    field.</div>

  <div class="grid g4">
    <div class="card dark"><div class="k-lbl">Needs action today</div>
      <div class="k-val">${d.count}</div>
      <div class="k-note">Across ${names.length} kinds of work.</div></div>
    <div class="card"><div class="k-lbl">Overdue</div>
      <div class="k-val" style="color:${d.overdue ? "var(--bad)" : "var(--good)"}">${d.overdue}</div>
      <div class="k-note">Past a due date or an acknowledgement window.</div></div>
    <div class="card"><div class="k-lbl">Critical</div>
      <div class="k-val" style="color:${d.critical ? "var(--bad)" : "var(--good)"}">${d.critical}</div>
      <div class="k-note">Business importance, not elapsed time.</div></div>
    <div class="card"><div class="k-lbl">You</div>
      <div class="k-val sm">${esc(d.me ? d.me.name.split(" ")[0] : BOOT.user.name.split(" ")[0])}</div>
      <div class="k-note">${esc(d.me ? d.me.designation + " · " + d.me.team
        : BOOT.user.designation)}</div></div>
  </div>

  ${names.length ? names.map(nm => `
    <div class="sec"><h2>${esc(nm)}</h2>
      <p>${esc({
        "Acknowledge": "Someone raised this at us and nobody has replied yet. The window is a setting — §36 A is still open on what 24 hours means.",
        "Decide": "Sitting in an Arch & Design lane. Actionable here, now.",
        "My work": "Assigned to you and either overdue, blocked or not started.",
        "Site findings": "Owned by you or your team and still open.",
        "Compliance": "Recurring commitments the Manual makes that are past due.",
        "Rule on": "A lesson cannot be adopted into a checklist until it is ruled on.",
        "Define": "Business definitions that every performance figure depends on.",
      }[nm] || "")}</p></div>
    <div class="card"><table class="tbl">
      <thead><tr><th style="width:80px">Priority</th><th>What</th><th>Why it is here</th>
        <th>Action</th><th style="width:96px">Due</th></tr></thead>
      <tbody>${groups[nm].map(r => `
        <tr class="${r.kind === "setting" ? "rc" : "rc"}"
            ${r.kind === "setting" ? `data-goto="settings"` : `data-e="${r.kind}:${r.id}"`}>
          <td>${priChip(r.priority)}</td>
          <td><b>${esc(r.title)}</b>${r.sub ? `<br><span class="mut" style="font-size:11px">${esc(r.sub)}</span>` : ""}</td>
          <td class="${r.overdue ? "" : "mut"}" style="${r.overdue ? "color:var(--bad);font-weight:600" : ""}">${esc(r.why)}</td>
          <td class="mut">${esc(r.action)}</td>
          <td class="mut" style="white-space:nowrap">${r.due ? esc(String(r.due).slice(0, 16)) : "—"}</td>
        </tr>`).join("")}</tbody></table></div>`).join("")
    : `<div class="emptyx"><b>Nothing needs action today</b>No unacknowledged requests,
       no decisions in your lane, no overdue steps, no missed obligations.</div>`}`;
  UI.bind(p);
};

/* ═══════════════════════════════════════════════════════════════════════════
   §36 · The definitions.  "Should not be hard-coded until confirmed."
   ═══════════════════════════════════════════════════════════════════════════ */
VIEWS.settings = async function () {
  const d = await api("/api/settings");
  const p = $("#page");
  p.innerHTML = `
  ${d.unconfirmed ? `<div class="note warn">
    <b>${d.unconfirmed} of ${d.total} business definitions are still UNCONFIRMED.</b>
    §36 of the review lists eight points that "should not be hard-coded until the business
    definition is confirmed". They are therefore rows in a table, not constants in code:
    every calculation in the system reads them, and each one carries the question it is
    waiting on. <b>Until they are answered, no performance figure here can be defended</b>
    — which is exactly why they are shown rather than quietly defaulted.
  </div>` : `<div class="note"><b>All ${d.total} definitions confirmed.</b> Every figure in
    the system can now be traced to an agreed rule and the person who agreed it.</div>`}

  <div class="grid g4">
    <div class="card dark"><div class="k-lbl">Definitions</div>
      <div class="k-val">${d.total}</div></div>
    <div class="card"><div class="k-lbl">Unconfirmed</div>
      <div class="k-val" style="color:${d.unconfirmed ? "var(--bad)" : "var(--good)"}">${d.unconfirmed}</div>
      <div class="k-note">Each blocks a number somewhere.</div></div>
    <div class="card"><div class="k-lbl">Confirmed</div>
      <div class="k-val" style="color:var(--good)">${d.total - d.unconfirmed}</div></div>
    <div class="card"><div class="k-lbl">Sections</div>
      <div class="k-val sm">${Object.keys(d.sections).length}</div>
      <div class="k-note">Acknowledgement · Priority · SLA/TAT · Time · Delivery ·
        Baseline · Escalation · Lessons</div></div>
  </div>

  ${Object.entries(d.sections).map(([sec, rows]) => `
    <div class="sec"><h2>${esc(sec)}</h2>
      <p>${rows.filter(r => !r.confirmed).length} of ${rows.length} unconfirmed</p></div>
    <div class="card"><table class="tbl">
      <thead><tr><th style="width:34%">Definition</th><th style="width:20%">Current value</th>
        <th>The question it is waiting on</th><th style="width:74px">Source</th>
        <th style="width:78px"></th></tr></thead>
      <tbody>${rows.map(r => `<tr>
        <td><b>${esc(r.label)}</b>
          ${r.confirmed
            ? `<br><span class="chip c-done">confirmed by ${esc(r.confirmed_by || "")}</span>`
            : `<br><span class="chip c-late">unconfirmed</span>`}</td>
        <td><code class="setval">${esc(r.kind === "bool"
            ? (r.value === "1" ? "yes" : "no")
            : (r.value || "—"))}</code></td>
        <td class="mut" style="line-height:1.5">${esc(r.note || "")}</td>
        <td class="src">${esc(r.doc_ref || "")}</td>
        <td><button class="btn sm" data-set="${esc(r.key)}">Set</button></td>
      </tr>`).join("")}</tbody></table></div>`).join("")}`;

  p.querySelectorAll("[data-set]").forEach(b => b.onclick = () =>
    UI.editSetting(d.rows.find(r => r.key === b.dataset.set)));
};

/* ═══════════════════════════════════════════════════════════════════════════
   #16 · Learning Summary.  A dedicated page, as asked.
   ═══════════════════════════════════════════════════════════════════════════ */
VIEWS.learning = async function () {
  const d = await api("/api/learning");
  const p = $("#page");
  const k = d.kpi;
  const bar = (obj, total) => Object.entries(obj)
    .sort((a, b) => b[1] - a[1]).map(([lbl, n]) => `
    <div style="margin-bottom:11px">
      <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">
        <b>${esc(lbl)}</b><span class="mut">${n}</span></div>
      <div class="bar"><i style="width:${n / (total || 1) * 100}%"></i></div></div>`).join("");

  p.innerHTML = `
  <div class="note">The review, §13: <b>"turn lessons learned into institutional
    knowledge and process improvement."</b> Which means this page cannot just list
    lessons. It has to answer what keeps happening, whose process caused it, how much
    turnaround it actually cost, and which improvements are genuinely closed —
    otherwise a lessons register is a diary.
    <br><br>Visibility follows §11: a lesson reaches the department head when it is
    raised${d.settings.notify_audit ? `, and Audit from <b>${esc(d.settings.audit_from)}</b> onward` : ""}.
    Both are settings, because who sees what is a governance decision.</div>

  <div class="grid g4">
    <div class="card dark"><div class="k-lbl">Turnaround days lost</div>
      <div class="k-val">${n0(k.tat_days_lost)}</div>
      <div class="k-note">Totalled from the lessons that recorded a delay. This is the
        number §12 of the review is really asking for.</div></div>
    <div class="card"><div class="k-lbl">Lessons</div>
      <div class="k-val">${k.total}</div>
      <div class="k-note">${k.open} open · ${k.ruled} ruled · <b>${k.adopted} adopted</b></div></div>
    <div class="card"><div class="k-lbl">Became a standing check</div>
      <div class="k-val" style="color:var(--good)">${k.checks_created}</div>
      <div class="k-note">Items now on the §4.2 stage-checklist template because of a
        lesson. Every future project is stopped for these.</div></div>
    <div class="card"><div class="k-lbl">Improvements open</div>
      <div class="k-val" style="color:${k.improvements_open ? "var(--st-wait)" : "var(--good)"}">${k.improvements_open}</div>
      <div class="k-note">${k.improvements_closed} closed. A lesson can be adopted and
        still have work behind it.</div></div>
  </div>

  <div class="sec"><h2>Where the delay actually came from</h2>
    <p>§12 of the review: was the delay internal or external, was there a dependency,
      which team or process caused it.</p></div>
  <div class="grid g4">
    ${[["Internal", k.internal, "var(--bad)"], ["External", k.external, "var(--st-wait)"],
       ["Dependency", k.dependency, "var(--st-hold)"], ["Process", k.process, "var(--st-run)"]]
      .map(([l, v, c]) => `<div class="card"><div class="k-lbl">${l}</div>
        <div class="k-val sm" style="color:${c}">${v}</div></div>`).join("")}
  </div>

  <div class="grid g2" style="margin-top:14px">
    <div class="card"><h3>By category</h3>
      <div class="sub">What kind of thing keeps going wrong</div>
      ${bar(d.by_category, k.total)}</div>
    <div class="card"><h3>Whose process</h3>
      <div class="sub">Named on the lesson, not inferred</div>
      ${bar(d.by_delay_owner, k.total)}</div>
  </div>

  ${d.recurring.length ? `
  <div class="sec"><h2>Recurring</h2>
    <p>More than one lesson in the same category — the review's "major recurring
      issues".</p></div>
  <div class="card"><table class="tbl">
    <thead><tr><th>Category</th><th class="num">Lessons</th>
      <th class="num">Turnaround days lost</th></tr></thead>
    <tbody>${d.recurring.map(r => `<tr>
      <td><b>${esc(r.category || "Uncategorised")}</b></td>
      <td class="num">${r.n}</td>
      <td class="num"><b style="color:var(--bad)">${n0(r.days)}</b></td></tr>`).join("")}
    </tbody></table></div>` : ""}

  <div class="sec"><h2>The register</h2>
    <p>Root cause, preventive action, and whether the improvement is closed.
      Click a lesson to rule on it or adopt it.</p></div>
  <div class="card scroll"><table class="tbl">
    <thead><tr><th>Lesson</th><th style="width:74px">Priority</th><th>Root cause</th>
      <th style="width:84px">Delay</th><th>Preventive action</th>
      <th style="width:88px">Improvement</th><th style="width:96px">Visibility</th></tr></thead>
    <tbody>${d.rows.map(l => `<tr class="rc" data-e="llr:${l.id}">
      <td><b>${esc(l.title)}</b>
        <br><span class="mut" style="font-size:11px">${esc(l.pname || "Department")}
        ${l.category ? " · " + esc(l.category) : ""}</span></td>
      <td>${priChip(l.priority)}</td>
      <td class="mut" style="line-height:1.45">${esc((l.root_cause || "").slice(0, 150))
        || `<span style="color:var(--bad)">not recorded</span>`}</td>
      <td class="num">${l.delay_days ? `<b style="color:var(--bad)">${l.delay_days}d</b>
        <br><span class="mut" style="font-size:10px">${esc(l.delay_kind || "")}</span>` : "—"}</td>
      <td class="mut" style="line-height:1.45">${esc((l.preventive_action || "").slice(0, 130)) || "—"}</td>
      <td><span class="chip ${l.improvement_status === "done" ? "c-done"
        : l.improvement_status === "dropped" ? "c-queue"
        : l.improvement_status === "in_progress" ? "c-run" : "c-hold"}">${esc(
          (l.improvement_status || "proposed").replace("_", " "))}</span></td>
      <td style="font-size:10px">
        ${l.head_notified_at ? `<span class="chip c-done">head</span>` : ""}
        ${l.audit_notified_at ? `<span class="chip c-run">audit</span>` : ""}
      </td></tr>`).join("")}
    </tbody></table></div>`;
  UI.bind(p);
};

/* ═══════════════════════════════════════════════════════════════════════════
   #29 #30 #32 #33 · Delivery cycle
   ═══════════════════════════════════════════════════════════════════════════ */
VIEWS.delivery = async function () {
  const d = await api("/api/delivery");
  const p = $("#page");
  const tot = d.rows.reduce((a, r) => ({
    gross: a.gross + r.gross, delivery: a.delivery + r.delivery,
    excluded: a.excluded + r.excluded, md: a.md + r.md_approval,
  }), {gross: 0, delivery: 0, excluded: 0, md: 0});

  p.innerHTML = `
  <div class="note">§29 of the review made the sharpest point in the document:
    <b>"When a Director signs off, the timing of that approval can currently reflect
    negatively on the senior manager."</b> A single elapsed number cannot tell the
    difference between a team being slow and a team waiting for a signature. So delivery
    time is decomposed, and <b>what comes out of it is a setting</b> — §30 asked for MD
    approval to be excluded, and §36 F says confirm the rest before locking it.
    <br><br>Currently excluding: ${d.exclusions.length
      ? d.exclusions.map(x => `<b>${esc(x.replace("_", " "))}</b>`).join(" · ")
      : "<b>nothing</b>"} — <span class="kl" data-goto="settings">change what is excluded →</span></div>

  <div class="grid g4">
    <div class="card"><div class="k-lbl">Gross elapsed</div>
      <div class="k-val sm">${n0(Math.round(tot.gross))}<span class="u">d</span></div>
      <div class="k-note">Everything, including waiting and blocking.</div></div>
    <div class="card"><div class="k-lbl">Excluded</div>
      <div class="k-val sm" style="color:var(--st-wait)">${n0(Math.round(tot.excluded))}<span class="u">d</span></div>
      <div class="k-note">Not the department's to answer for.</div></div>
    <div class="card dark"><div class="k-lbl">Delivery time</div>
      <div class="k-val">${n0(Math.round(tot.delivery))}<span class="u">d</span></div>
      <div class="k-note">What the department is actually accountable for${unconf()}</div></div>
    <div class="card"><div class="k-lbl">MD approval time</div>
      <div class="k-val sm">${n0(Math.round(tot.md))}<span class="u">d</span></div>
      <div class="k-note">Removed from delivery by default — §30.</div></div>
  </div>

  <div class="sec"><h2>By project</h2>
    <p>Team execution, waiting for approval, external dependency and blocking time, kept
      apart so the right conversation happens.</p></div>
  <div class="card scroll"><table class="tbl">
    <thead><tr><th>Project</th><th class="num">Expected</th><th class="num">In progress</th>
      <th class="num">Wait (ours)</th><th class="num">Wait (theirs)</th>
      <th class="num">Hold</th><th class="num">Approval</th><th class="num">MD</th>
      <th class="num">Gross</th><th class="num">Delivery</th></tr></thead>
    <tbody>${d.rows.map(r => `<tr class="rc" data-e="project:${r.project.id}">
      <td><b>${esc(r.project.name)}</b><br><span class="mut" style="font-size:11px">${r.steps} steps</span></td>
      <td class="num mut">${DAYS(r.expected)}</td>
      <td class="num">${DAYS(r.in_progress)}</td>
      <td class="num">${DAYS(r.wait_internal)}</td>
      <td class="num" style="color:var(--st-wait)">${DAYS(r.wait_external)}</td>
      <td class="num" style="color:var(--st-hold)">${DAYS(r.hold)}</td>
      <td class="num mut">${DAYS(r.approval)}</td>
      <td class="num mut">${DAYS(r.md_approval)}</td>
      <td class="num mut">${DAYS(r.gross)}</td>
      <td class="num"><b>${n0(r.delivery)}d</b></td></tr>`).join("")}
    </tbody></table></div>

  <div class="sec"><h2>What is excluded, and by whose decision</h2></div>
  <div class="card"><table class="tbl">
    <tbody>${d.settings.map(s => `<tr>
      <td><b>${esc(s.label)}</b><br><span class="mut" style="font-size:11px">${esc(s.note || "")}</span></td>
      <td style="width:80px">${s.value === "1"
        ? `<span class="chip c-done">excluded</span>`
        : `<span class="chip c-queue">counted</span>`}</td>
      <td style="width:110px">${s.confirmed
        ? `<span class="chip c-done">confirmed</span>`
        : `<span class="chip c-late">unconfirmed</span>`}</td>
      <td class="src" style="width:70px">${esc(s.doc_ref || "")}</td>
      <td style="width:60px"><button class="btn sm" data-set2="${esc(s.key)}">Set</button></td>
      </tr>`).join("")}</tbody></table></div>`;

  p.querySelectorAll("[data-set2]").forEach(b => b.onclick = () =>
    UI.editSetting(d.settings.find(r => r.key === b.dataset.set2)));
  UI.bind(p);
};

/* ═══════════════════════════════════════════════════════════════════════════
   #21 #22 · Executive View — department facts and workload bifurcation
   ═══════════════════════════════════════════════════════════════════════════ */
VIEWS.exec = async function () {
  const d = await api("/api/exec");
  const p = $("#page");
  const k = BOOT.kpi;
  const maxStation = Math.max(1, ...Object.values(d.by_station)
    .flatMap(o => Object.values(o).map(x => x.days)));

  p.innerHTML = `
  ${d.unconfirmed ? `<div class="note warn">
    <b>${d.unconfirmed} business definitions are unconfirmed (§36).</b> The figures below
    are computed from the current working assumptions and are marked where that matters.
    <span class="kl" data-goto="settings">Review the definitions →</span></div>` : ""}

  <div class="grid g4">
    <div class="card dark"><div class="k-lbl">Time booked outside the department</div>
      <div class="k-val">${n0(k.wait_days)}<span class="u">days</span></div>
      <div class="k-note">${k.wait_share}% of all elapsed time. Of that,
        <b>${n0(k.wait_ext_days)}d</b> was held by a party outside Zameen —
        the split §25 of the review asked for.</div></div>
    <div class="card clickcard" data-goto="today"><div class="k-lbl">Needs action today</div>
      <div class="k-val" style="color:${k.unacknowledged ? "var(--bad)" : "var(--good)"}">${k.unacknowledged}</div>
      <div class="k-note">Cross-team requests nobody has acknowledged.
        ${k.escalated} escalated.</div></div>
    <div class="card clickcard" data-goto="site"><div class="k-lbl">Site findings open</div>
      <div class="k-val" style="color:${k.findings_overdue ? "var(--bad)" : "var(--good)"}">${k.findings_open}</div>
      <div class="k-note">${k.findings_overdue} past their TAT, of ${k.findings} recorded.</div></div>
    <div class="card clickcard" data-goto="learning"><div class="k-lbl">Turnaround lost to known causes</div>
      <div class="k-val">${n0(k.tat_days_lost)}<span class="u">d</span></div>
      <div class="k-note">From lessons that recorded a root cause.</div></div>
  </div>

  <div class="sec"><h2>Department facts</h2>
    <p>§17 of the review: workload, performance, pending items, delays, TAT and
      cross-team dependencies, per department.</p></div>
  <div class="card scroll"><table class="tbl">
    <thead><tr><th>Department</th><th class="num">People</th><th class="num">Open</th>
      <th class="num">Per head</th><th class="num">On time</th><th class="num">In progress</th>
      <th class="num">Wait (ours)</th><th class="num">Wait (theirs)</th><th class="num">Hold</th>
      <th class="num">Revisions</th><th class="num">Owed to them</th>
      <th class="num">Unack'd</th><th class="num">Findings</th></tr></thead>
    <tbody>${d.departments.map(x => `<tr class="rc" data-goto="team">
      <td><b>${esc(x.team)}</b></td>
      <td class="num">${x.people}</td>
      <td class="num"><b>${x.open}</b></td>
      <td class="num">${x.load_per_head == null ? "—" : x.load_per_head}</td>
      <td class="num"><b style="color:${x.on_time_pct == null ? "inherit"
        : x.on_time_pct >= 70 ? "var(--good)" : "var(--bad)"}">${
        x.on_time_pct == null ? "—" : x.on_time_pct + "%"}</b></td>
      <td class="num">${DAYS(x.in_progress)}</td>
      <td class="num">${DAYS(x.wait_internal)}</td>
      <td class="num" style="color:var(--st-wait)">${DAYS(x.wait_external)}</td>
      <td class="num" style="color:var(--st-hold)">${DAYS(x.hold)}</td>
      <td class="num">${x.revisions || "—"}</td>
      <td class="num">${x.owed_asks ? `${x.owed_asks} · ${n0(x.owed_days)}d` : "—"}</td>
      <td class="num"><b style="color:${x.unacknowledged ? "var(--bad)" : "inherit"}">${
        x.unacknowledged || "—"}</b></td>
      <td class="num">${x.findings_open || "—"}${x.findings ? `<span class="mut">/${x.findings}</span>` : ""}</td>
      </tr>`).join("")}</tbody></table></div>

  <div class="sec"><h2>Workload bifurcation</h2>
    <p>§18 of the review, and Haroon's own observation: <b>Architecture &amp; Design is
      front-heavy — the workload is high for the first six months and then reduces.</b>
      A flat headcount-versus-tasks figure hides exactly that, and it is the number that
      decides whether a team is under-resourced or simply early in a project.</p></div>
  <div class="card mx"><table>
    <thead><tr><th class="pj">Department</th>
      ${d.stations.map(s => `<th title="${esc(s.name)}">${s.stage}</th>`).join("")}
      <th style="min-width:90px">Phase split</th></tr></thead>
    <tbody>${d.departments.map(x => {
      const st = d.by_station[x.team] || {};
      const ph = d.by_phase[x.team] || {};
      const phTot = Object.values(ph).reduce((a, b) => a + b, 0) || 1;
      return `<tr><td class="pj">${esc(x.team)}<small>${n0(x.expected)}d published</small></td>
        ${d.stations.map(s => {
          const cell = st[s.stage];
          const w = cell ? cell.days / maxStation : 0;
          return `<td><div class="cell heat" style="--h:${w}"
            title="${esc(x.team)} — stage ${s.stage} ${esc(s.name)}\n${
              cell ? `${cell.days} published days · ${cell.steps} steps · ${cell.open} open`
                   : "no steps"}">
            <b>${cell ? cell.days || "" : ""}</b></div></td>`;
        }).join("")}
        <td><div class="clock" style="height:11px">
          ${["A", "B", "C"].map(f => `<i style="width:${(ph[f] || 0) / phTot * 100}%;
             background:${f === "A" ? "var(--st-queue)" : f === "B" ? "var(--st-run)"
             : "var(--st-done)"}"></i>`).join("")}</div>
          <div style="font-size:9.5px;color:var(--ink-3);margin-top:3px">
            ${Math.round((ph.B || 0) / phTot * 100)}% design</div></td>
        </tr>`;
    }).join("")}</tbody></table></div>
  <div class="legend">
    <span><b style="background:var(--st-queue)"></b>A · Acquisition</span>
    <span><b style="background:var(--st-run)"></b>B · Design</span>
    <span><b style="background:var(--st-done)"></b>C · Construction &amp; closeout</span>
    <span style="margin-left:auto">Darker cell = more published days at that station</span>
  </div>

  <div class="sec"><h2>Load over time</h2>
    <p>Published days by month, from the planned dates the catalog generated.</p></div>
  <div class="grid g2">${d.departments.map(x => {
    const ms = (d.by_month[x.team] || []).filter(m => m.month);
    const mx = Math.max(1, ...ms.map(m => m.days));
    return `<div class="card"><h3>${esc(x.team)}</h3>
      <div class="sub">${ms.length} months with planned work · peak ${mx}d</div>
      <div class="spark" style="height:44px">${ms.map(m => `
        <i style="height:${m.days / mx * 100}%;background:${
          m.days > mx * .66 ? "var(--bad)" : m.days > mx * .33 ? "var(--st-run)"
          : "var(--st-queue)"}" title="${esc(m.month)} — ${m.days}d, ${m.steps} steps"></i>`).join("")}</div>
      <div style="display:flex;justify-content:space-between;font-size:9.5px;color:var(--ink-3);margin-top:4px">
        <span>${esc(ms.length ? ms[0].month : "")}</span>
        <span>${esc(ms.length ? ms[ms.length - 1].month : "")}</span></div>
    </div>`;
  }).join("")}</div>`;
  UI.bind(p);
};

/* ═══════════════════════════════════════════════════════════════════════════
   #24 #28 #29 · The stage matrix, with the five time categories apart
   ═══════════════════════════════════════════════════════════════════════════ */
VIEWS.matrix = async function () {
  const d = CACHE.matrix || (CACHE.matrix = await api("/api/matrix"));
  const p = $("#page");
  const mode = CACHE.mxmode || (CACHE.mxmode = "progress");
  const hdr = d.stages.map(s =>
    `<th title="${esc(s.name)}">${s.stage}<br><span style="font-weight:600">${esc(s.name.split(" ")[0])}</span></th>`).join("");

  const cellFor = (c) => {
    if (mode === "progress") {
      const lbl = c.status === "done" ? "✓"
        : c.status === "running" ? (c.n ? Math.round(c.done / c.n * 100) + "%" : "•")
        : c.status === "hold" ? "⏸" : "";
      return {lbl, sub: c.wait ? `${c.wait}d wait` : (c.own ? `${c.own}d` : "")};
    }
    if (mode === "delay") {
      return {lbl: c.delay ? "+" + c.delay : (c.expected ? "0" : ""),
              sub: c.delay_owner || ""};
    }
    if (mode === "wait") {
      return {lbl: c.wait_external || c.wait_internal ? String(c.wait_external) : "",
              sub: c.wait_internal ? `${c.wait_internal}d ours` : ""};
    }
    return {lbl: c.hold ? String(c.hold) : "", sub: c.hold ? "hold" : ""};
  };

  const rows = d.rows.map(r => `<tr>
    <td class="pj" style="cursor:pointer" data-e="project:${r.project.id}">${esc(r.project.name)}<small>${esc(r.project.kind)} · ${esc(r.project.city)}</small></td>
    ${r.cells.map(c => {
      const cls = c.overdue ? "s-overdue" : "s-" + c.status;
      const v = cellFor(c);
      return `<td><div class="cell ${cls} ${c.delay_owner ? "own-" + c.delay_owner : ""}"
        data-p="${r.project.id}"
        title="${esc(r.project.name)} — ${esc(c.name)}
Expected ${c.expected || "—"}d · actual ${c.actual}d
In progress ${c.in_progress}d · wait ours ${c.wait_internal}d · wait theirs ${c.wait_external}d · hold ${c.hold}d
${c.delay ? "Delay " + c.delay + "d, mostly " + (c.delay_owner || "unattributed") : "No delay against the published TAT"}
${c.done}/${c.n} steps">
        <b>${v.lbl}</b><i>${esc(v.sub)}</i></div></td>`;
    }).join("")}</tr>`).join("");

  p.innerHTML = `
  <div class="actbar"><button class="btn pri" id="mNew">+ Add a project</button></div>
  <div class="note">§24 of the review asked the heatmap to distinguish
    <b>expected, actual, waiting, hold and in-progress</b> time, and §25 to show
    <b>how much time is spent waiting for our team versus another party</b> — because
    "the purpose is to avoid incorrectly attributing delays to a team when the actual
    blocker is elsewhere". One elapsed number could never do that. Switch what the cells
    show below; the tooltip always carries all five.${unconf()}</div>
  <div class="pills">
    ${[["progress", "Progress"], ["delay", "Delay vs expected"],
       ["wait", "Waiting on others"], ["hold", "Blocked / hold"]].map(([v, l]) =>
      `<button class="pill ${mode === v ? "on" : ""}" data-mx="${v}">${l}</button>`).join("")}
  </div>
  <div class="phase-band">
    <span style="flex:2">◀ Acquisition</span><span style="flex:10">Design ▶</span>
    <span style="flex:2">Support &amp; closeout</span></div>
  <div class="card mx"><table>
    <thead><tr><th class="pj">Project</th>${hdr}</tr></thead>
    <tbody>${rows}</tbody></table></div>
  <div class="legend">
    <span><b style="background:var(--st-done-t)"></b>Done</span>
    <span><b style="background:var(--st-run-t);border:1px solid var(--st-run)"></b>Running</span>
    <span><b style="background:var(--st-late-t);border:1px solid var(--st-late)"></b>Overdue</span>
    <span><b style="background:var(--card-3)"></b>Not started</span>
    <span style="margin-left:auto">Bar under a cell = whose delay:
      <b style="background:var(--st-late)"></b>ours
      <b style="background:var(--st-wait)"></b>outside
      <b style="background:var(--st-hold)"></b>blocked</span></div>`;

  $("#mNew").onclick = () => UI.newProject();
  p.querySelectorAll("[data-mx]").forEach(b => b.onclick = () => {
    CACHE.mxmode = b.dataset.mx; render();
  });
  p.querySelectorAll(".cell").forEach(c => c.onclick = () => {
    if (!c.dataset.p) return;
    CACHE.pid = +c.dataset.p; go("project");
  });
  UI.bind(p);
};

/* ═══════════════════════════════════════════════════════════════════════════
   #7 #8 #9 #10 #23 · Site & Compliance, rebuilt around findings
   ═══════════════════════════════════════════════════════════════════════════ */
VIEWS.site = async function () {
  const [s, f] = await Promise.all([api("/api/site"), api("/api/findings")]);
  const p = $("#page");
  const k = f.kpi, sk = s.kpi;
  const fil = CACHE.ffil || (CACHE.ffil = {status: "", team: ""});
  let rows = f.rows;
  if (fil.status) rows = rows.filter(r => r.status === fil.status);
  if (fil.team) rows = rows.filter(r => r.responsible_team === fil.team);

  p.innerHTML = `
  <div class="actbar">
    <button class="btn pri" id="sVisit">+ Log a visit</button>
    <button class="btn" id="sFind">+ Finding</button>
    <button class="btn" id="sAuth">+ Authority submission</button>
  </div>
  <div class="note">§4 of the review killed the old shape in one line:
    <b>"A visit should not become one large unstructured record."</b> Five problems found
    on one walk used to be one row — one owner, one status, one clock — so four of them
    could not be assigned, timed or closed. Now a visit is a container and each finding
    carries its own category, place, owner, priority, TAT and evidence, and can become an
    RFI, an NCR or a task on its own (§5). §6 asked for history, so a finding also knows
    whether the same thing has been found in the same place before.</div>

  <div class="grid g4">
    <div class="card dark"><div class="k-lbl">Findings recorded</div>
      <div class="k-val">${k.total}</div>
      <div class="k-note">Across ${s.visits.length} visits — an average of
        ${(k.total / (s.visits.length || 1)).toFixed(1)} per visit, which is the number
        the old single-text-field could never show.</div></div>
    <div class="card"><div class="k-lbl">Open</div>
      <div class="k-val" style="color:${k.overdue ? "var(--bad)" : "var(--good)"}">${k.open}</div>
      <div class="k-note">${k.overdue} past their TAT.</div></div>
    <div class="card"><div class="k-lbl">Non-compliance</div>
      <div class="k-val" style="color:${k.non_compliance ? "var(--bad)" : "var(--good)"}">${k.non_compliance}</div>
      <div class="k-note"><b>${k.became_case}</b> raised an NCR on the §16 route.</div></div>
    <div class="card"><div class="k-lbl">Seen before</div>
      <div class="k-val" style="color:${k.recurring ? "var(--st-wait)" : "var(--good)"}">${k.recurring}</div>
      <div class="k-note">Same category, same place, earlier visit. The difference
        between "a marble complaint" and "the fourth marble complaint".</div></div>
  </div>

  ${Object.keys(f.recurring).length ? `
  <div class="sec"><h2>Recurring problems</h2>
    <p>§6 of the review — is this new, recurring, previously resolved, or still
      outstanding.</p></div>
  <div class="card"><table class="tbl">
    <thead><tr><th>Category</th><th>Location</th><th class="num">Times found</th>
      <th class="num">Projects</th></tr></thead>
    <tbody>${Object.entries(f.recurring).flatMap(([cat, list]) => list.map(r => `<tr>
      <td><b>${esc(cat)}</b></td><td class="mut">${esc(r.location || "—")}</td>
      <td class="num"><b style="color:var(--bad)">${r.n}</b></td>
      <td class="num mut">${r.np}</td></tr>`)).join("")}
    </tbody></table></div>` : ""}

  <div class="sec"><h2>Findings</h2>
    <p>Click one for its evidence, its history in the same place, and what it became.</p></div>
  <div class="frow">
    <select id="ffs"><option value="">Any status</option>
      ${["open", "assigned", "in_progress", "resolved", "closed"].map(x =>
        `<option ${fil.status === x ? "selected" : ""}>${x}</option>`).join("")}</select>
    <select id="fft"><option value="">Any team</option>
      ${Object.keys(f.by_team).filter(x => x !== "unassigned").map(x =>
        `<option ${fil.team === x ? "selected" : ""}>${esc(x)}</option>`).join("")}</select>
    <span class="mut" style="font-size:11.5px">${rows.length} of ${f.rows.length}</span>
  </div>
  <div class="card scroll"><table class="tbl">
    <thead><tr><th style="width:74px">Priority</th><th>Finding</th><th>Category</th>
      <th>Where</th><th>Owner</th><th style="width:88px">Due</th><th>Status</th>
      <th>Became</th></tr></thead>
    <tbody>${rows.map(r => `<tr class="rc" data-e="finding:${r.id}">
      <td>${priChip(r.priority)}</td>
      <td><b>${esc(r.title)}</b>
        ${r.non_compliance ? ` <span class="chip c-late">NC</span>` : ""}
        ${r.recurrence_of ? ` <span class="chip c-hold">seen before</span>` : ""}
        <br><span class="mut" style="font-size:11px">${esc(r.pcode || "")} ·
          visit ${esc((r.visited_on || "").slice(0, 10))}</span></td>
      <td class="mut">${esc(r.category || "—")}</td>
      <td class="mut" style="max-width:170px">${esc(r.location || "—")}</td>
      <td class="mut">${esc(r.responsible_team || "unassigned")}
        ${r.person ? `<br><span style="font-size:11px">${esc(r.person)}</span>` : ""}</td>
      <td class="mut" style="${r.overdue ? "color:var(--bad);font-weight:700" : ""}">${dash(r.due_on)}</td>
      <td><span class="chip ${r.status === "closed" ? "c-done"
        : r.status === "resolved" ? "c-done" : r.status === "in_progress" ? "c-run"
        : r.status === "assigned" ? "c-queue" : "c-hold"}">${esc(r.status.replace("_", " "))}</span></td>
      <td class="mut" style="font-size:11px">${r.case_ref
        ? `<span class="kl">${esc(r.case_ref)}</span>` : "—"}</td>
      </tr>`).join("")}</tbody></table></div>

  <div class="sec"><h2>Visits</h2><p>Each one is a container. Click for its findings.</p></div>
  <div class="card"><table class="tbl">
    <thead><tr><th>Date</th><th>Project</th><th>By</th><th class="num">Findings</th>
      <th class="num">Photos</th><th>Summary</th></tr></thead>
    <tbody>${s.visits.map(v => `<tr class="rc" data-e="visit:${v.id}">
      <td class="mut">${esc(v.visited_on)}</td>
      <td class="mut">${esc(v.pcode || v.pname || "")}</td>
      <td>${esc(v.by_whom || "")}</td>
      <td class="num"><b>${f.rows.filter(x => x.visit_id === v.id).length}</b></td>
      <td class="num mut">${v.photos || 0}</td>
      <td class="mut">${esc(v.findings || "")}</td></tr>`).join("")}
    </tbody></table></div>

  <div class="sec"><h2>The authority file — §7 / §17</h2>
    <p>${sk.authority_open} open, ${n0(Math.round(sk.authority_days))} days accumulated.</p></div>
  <div class="card"><table class="tbl">
    <thead><tr><th>Ref</th><th>Project</th><th>Authority</th><th>Type</th>
      <th class="num">Days</th><th>Status</th></tr></thead>
    <tbody>${s.authority.map(a => `<tr class="rc" data-e="authority:${a.id}">
      <td><b>${esc(a.ref)}</b></td><td class="mut">${esc(a.pname || "")}</td>
      <td>${esc(a.authority)}</td><td class="mut">${esc(a.kind)}</td>
      <td class="num"><b style="color:${a.status === "approved" ? "inherit" : "var(--st-wait)"}">${a.age}d</b></td>
      <td><span class="chip ${a.status === "approved" ? "c-done"
        : a.status === "rejected" ? "c-late" : "c-wait"}">${esc(a.status)}</span></td>
      </tr>`).join("")}</tbody></table></div>`;

  $("#sVisit").onclick = () => UI.newVisit();
  $("#sFind").onclick = () => UI.newFinding();
  $("#sAuth").onclick = () => UI.authSubmit();
  $("#ffs").onchange = e => { fil.status = e.target.value; render(); };
  $("#fft").onchange = e => { fil.team = e.target.value; render(); };
  UI.bind(p);
};

/* ═══════════════════════════════════════════════════════════════════════════
   The drawer learns findings, and cases learn their thread
   ═══════════════════════════════════════════════════════════════════════════ */
E.body.finding = (d) => {
  const R = d.record, x = d.extra;
  const hist = (x.same_place || []).concat(
    (x.history || []).filter(h => !(x.same_place || []).some(s => s.id === h.id)));
  return `
  <div class="mini">
    ${miniCell("Priority", R.priority, R.priority === "Critical" ? "hot" : "")}
    ${miniCell("TAT", R.tat_days ? R.tat_days + "d" : "—")}
    ${miniCell("Seen before", (x.history || []).length, (x.history || []).length ? "cool" : "ok")}
    ${miniCell("Evidence", d.documents.length, d.documents.length ? "ok" : "hot")}
  </div>
  ${sec("The finding — Manual §15 / §16")}
  ${dl([
    ["Finding", `<b>${esc(R.title)}</b>`],
    ["Category", esc(R.category || "")],
    ["Where", esc(R.location || "")],
    ["Description", esc(R.description || "")],
    ["Non-compliance", R.non_compliance
      ? `<span class="chip c-late">Yes — against approved IFC</span>`
      : `<span class="chip c-done">No</span>`],
    ["Status", `<span class="chip ${R.status === "closed" || R.status === "resolved"
      ? "c-done" : "c-run"}">${esc(R.status.replace("_", " "))}</span>`],
    ["Owner", R.responsible_team
      ? esc(R.responsible_team) + (R.person ? ` · ${esc(R.person)}` : "")
      : `<span class="mut">nobody yet</span>`],
    ["Due", R.due_on],
    ["Raised", `${esc(R.raised_by || "")} on ${esc(R.raised_at || "")}`
      + (R.visited_on ? ` · visit ${esc(R.visited_on)}` : "")],
    ["Visit", R.visit_id ? E.link("visit", R.visit_id, "the visit it came from") : null],
    ["Resolution", R.resolution ? esc(R.resolution)
      + ` <span class="mut">— ${esc(R.resolved_by || "")}</span>` : null],
  ])}

  ${sec("What it became")}
  ${(R.case_ref || x.task || x.lesson) ? `<div class="feed">
    ${R.case_ref ? `<div class="fe"><span>Case</span>
      ${E.link("case", R.case_id, R.case_ref + " — on the §16 route")}
      <span class="who"> — ${esc(R.case_status || "")}</span></div>` : ""}
    ${x.task ? `<div class="fe"><span>Task</span>
      ${E.link("task", x.task.id, x.task.title)}</div>` : ""}
    ${x.lesson ? `<div class="fe"><span>Lesson learned</span>
      ${E.link("llr", x.lesson.id, x.lesson.title)}</div>` : ""}
  </div>` : `<div class="emptyx"><b>Nothing raised from it yet</b>§5 of the review: a
     finding should be able to become an RFI or an action on the relevant team.</div>`}

  ${sec(`History in this place — §6`, hist.length ? `<span class="mut">${hist.length} earlier</span>` : "")}
  ${hist.length ? `<div class="card"><table class="tbl"><tbody>
    ${hist.slice(0, 10).map(h => `<tr class="rc" data-e="finding:${h.id}">
      <td class="mut" style="width:88px">${esc((h.visited_on || h.raised_at || "").slice(0, 10))}</td>
      <td><b>${esc(h.title)}</b><br><span class="mut" style="font-size:11px">${esc(h.location || "")}</span></td>
      <td style="width:78px"><span class="chip ${h.status === "closed" || h.status === "resolved"
        ? "c-done" : "c-hold"}">${esc(h.status)}</span></td></tr>`).join("")}
    </tbody></table></div>
    ${x.recurrence ? `<div class="note" style="margin-top:9px">This was logged as a
      <b>recurrence</b> of ${E.link("finding", x.recurrence.id, x.recurrence.title)} —
      so it is not a new problem, it is an unresolved one.</div>` : ""}`
    : `<div class="emptyx"><b>First time</b>Nothing else has been found in this category
       and place on this project.</div>`}`;
};

E.acts.finding = (d) => {
  const R = d.record;
  return `
    ${R.status !== "closed" ? `<button class="btn" data-x="f-assign">Assign</button>` : ""}
    ${!R.case_id ? `<button class="btn pri" data-x="f-raise">Raise as NCR / RFI</button>` : ""}
    ${!R.task_id ? `<button class="btn" data-x="f-task">Make it a task</button>` : ""}
    ${R.status !== "closed" ? `<button class="btn" data-x="f-resolve">Resolve</button>` : ""}
    ${!R.llr_id ? `<button class="btn" data-x="f-lesson">+ Lesson from this</button>` : ""}
    <button class="btn" data-x="f-pri">Priority</button>`;
};

/* the case drawer gains the thread, the acknowledgement and the escalation */
const _caseBody = E.body.case;
E.body.case = (d) => {
  const R = d.record, x = d.extra;
  const msgs = x.messages || [];
  const KIND = {ack: "Acknowledged", update: "Update", question: "Question",
                answer: "Answer", escalation: "Escalated", decision: "Decision"};
  const collab = (R.to_team || msgs.length || R.escalation_level) ? `
  ${sec("Cross-team — §2.1 / §3 / §16",
    `<span class="prov manual">Haroon review 1 Sep</span>`)}
  ${dl([
    ["Raised by", esc(R.from_team || "")],
    ["Raised at", R.to_team ? `<b>${esc(R.to_team)}</b>` : null],
    ["Priority", priChip(R.priority) + ` <button class="btn sm" data-x="c-pri">change</button>`],
    ["TAT", R.tat_days ? `${R.tat_days} working days`
      + (R.due_on ? ` · due ${esc(R.due_on)}` : "") : null],
    ["Acknowledged", R.acknowledged_at
      ? `<span class="chip c-done">${esc(R.acknowledged_at.slice(0, 16).replace("T", " "))}
         by ${esc(R.ack_by || "")}</span>`
      : R.ack_due_at
        ? `<span class="chip ${x.ack_overdue ? "c-late" : "c-wait"}">
           ${x.ack_overdue ? "window closed" : "due"}
           ${esc(String(R.ack_due_at).slice(0, 16).replace("T", " "))}</span>
           <span class="mut"> — window is ${esc(BOOT.ack_window || "")}, and what that
           means is still an open question (§36 A)</span>`
        : null],
    ["Escalation", R.escalation_level
      ? `<span class="chip c-late">level ${R.escalation_level} — ${esc(R.escalated_to || "")}</span>
         <br><span class="mut">${esc(R.escalation_reason || "")}
         — ${esc(R.escalated_by || "")}</span>`
      : `<span class="mut">none</span>`],
  ])}

  ${sec("Conversation", `<button class="btn sm" data-x="c-msg">+ Post an update</button>`)}
  ${msgs.length ? `<div class="feed">${msgs.map(m => `
    <div class="fe ${m.kind === "escalation" ? "blk" : ""}">
      <span>${esc(KIND[m.kind] || m.kind)} · ${esc(m.who || "")}${m.who_team
        ? " (" + esc(m.who_team) + ")" : ""} · ${esc((m.at || "").replace("T", " ").slice(0, 16))}</span>
      ${esc(m.body)}</div>`).join("")}</div>`
    : `<div class="emptyx"><b>Nothing said yet</b>The review asked for this specifically:
       the receiving team should be able to give an update <b>without closing the
       case</b>. Before it, the only way to say anything was to decide.</div>`}` : "";

  const origin = x.origin && x.origin.id ? sec("Where it came from")
    + `<div class="feed"><div class="fe"><span>${esc(R.origin_entity || "")}</span>
       ${E.link(R.origin_entity, x.origin.id, x.origin.title || x.origin.findings
         || "the record that raised this")}</div></div>` : "";

  return collab + origin + _caseBody(d);
};

const _caseActs = E.acts.case;
E.acts.case = (d) => {
  const R = d.record;
  return `${!R.acknowledged_at && R.ack_due_at
      ? `<button class="btn pri" data-x="c-ack">Acknowledge</button>` : ""}
    <button class="btn" data-x="c-msg">Post an update</button>
    <button class="btn" data-x="c-esc">Escalate</button>
    ` + _caseActs(d);
};

/* wire the new drawer buttons */
const _wire = E.wire;
E.wire = (d, w) => {
  _wire(d, w);
  const R = d.record;
  const back = () => E.open(d.kind, d.id, {back: true});
  w.querySelectorAll("[data-x]").forEach(btn => {
    const a = btn.dataset.x, prev = btn.onclick;
    btn.onclick = () => {
      if (a === "c-ack") return UI.ack(R, back);
      if (a === "c-msg") return UI.message(R, back);
      if (a === "c-esc") return UI.escalate(R, back);
      if (a === "c-pri") return UI.setPriority("case", R, back);
      if (a === "f-pri") return UI.setPriority("finding", R, back);
      if (a === "f-assign") return UI.assignFinding(R, back);
      if (a === "f-raise") return UI.raiseFinding(R, back);
      if (a === "f-task") return UI.findingTask(R, back);
      if (a === "f-resolve") return UI.resolveFinding(R, back);
      if (a === "f-lesson") return UI.findingLesson(R, back);
      if (prev) return prev();
    };
  });
};

/* ═══════════════════════════════════════════════════════════════════════════
   THE MODALS
   ═══════════════════════════════════════════════════════════════════════════ */
const deptOpts = (kinds) => (BOOT.departments || [])
  .filter(x => !kinds || kinds.includes(x.kind))
  .map(x => [x.name, `${x.name}${x.kind !== "design" ? "  (" + x.kind + ")" : ""}`]);

UI.crossTeam = (pid) => F.modal("Raise a request to another team",
  "§2.1 of the review. The receiving team has to acknowledge it, can give updates "
  + "without closing it, and it escalates if the window passes. Priority and TAT are "
  + "separate fields — one is importance, the other is time.",
  F.field("to_team", "Which team", {options: deptOpts(["design", "internal", "governance"])}) +
  F.field("project_id", "Project", {options: projOpts(), value: pid || CACHE.pid || ""}) +
  F.field("title", "What you need", {placeholder: "Confirm the easement on the eastern boundary"}) +
  F.field("priority", "Priority", {options: priOpts(), value: BOOT.priority_default}) +
  F.field("tat_days", "TAT (working days)", {type: "number", value: 3,
    hint: "How long the turnaround should take. Not the same as how important it is."}) +
  F.field("note", "Detail", {type: "textarea", rows: 3}),
  async d => { const r = await F.act("/api/case/create", {...d, type: "CTR"});
    refresh(`${r.ref} raised to ${d.to_team}`
      + (r.ack_due_at ? ` — acknowledgement due ${String(r.ack_due_at).slice(0, 16).replace("T", " ")}` : "")); },
  "Raise it");

UI.ack = (R, then) => F.modal(`Acknowledge ${R.ref}`,
  "§3 of the review: the receiving team must acknowledge. The window is a setting, "
  + "because §36 A leaves open whether 24 hours means calendar hours, business hours or "
  + "working days — a request raised 4pm Friday is due Saturday on one reading and "
  + "Monday on another.",
  F.field("body", "Anything to say with it", {type: "textarea", rows: 2,
    value: "Acknowledged — looking at it now."}),
  async d => { const r = await F.act("/api/case/ack", {...d, id: R.id});
    F.toast(r.late ? "Acknowledged — after the window closed, and logged as such"
                   : "Acknowledged inside the window"); if (then) then(); }, "Acknowledge");

UI.message = (R, then) => F.modal(`Post an update on ${R.ref}`,
  "An update does NOT close the case. The review asked for this in those words, because "
  + "a team with a partial answer used to either stay silent or close something that "
  + "was not finished.",
  F.field("kind", "This is", {options: [["update", "An update"],
    ["question", "A question back to the requestor"], ["answer", "An answer"]]}) +
  F.field("body", "Message", {type: "textarea", rows: 4}),
  async d => { await F.act("/api/case/message", {...d, id: R.id});
    F.toast("Posted"); if (then) then(); }, "Post");

UI.escalate = (R, then) => F.modal(`Escalate ${R.ref}`,
  "§16: collaboration cannot be limited to junior staff. An escalation is not a sharper "
  + "email — it is a recorded step with a named senior person and a reason, so \"how "
  + "often did we have to escalate to get an answer\" becomes a number a head can act on.",
  F.field("escalated_to", "To", {placeholder: "Leave blank to use the next rung",
    hint: "The ladder is a setting: " + (BOOT.escalation || "Line Manager → Senior Manager → Department Head")}) +
  F.field("reason", "Why", {type: "textarea", rows: 3,
    hint: "Required. It is going into a senior person's queue and they will ask."}),
  async d => { const r = await F.act("/api/case/escalate", {...d, id: R.id});
    F.toast(`Escalated to ${r.to}`); if (then) then(); }, "Escalate");

UI.setPriority = (entity, R, then) => F.modal("Change priority",
  "§3 of the review separated priority from TAT: priority is business importance, TAT is "
  + "time. The old value and the reason are kept, so a Critical raised on a Friday can "
  + "be explained on Monday.",
  F.field("priority", "Priority", {options: priOpts(), value: R.priority}) +
  F.field("reason", "Why it is changing", {type: "textarea", rows: 2}),
  async d => { await F.act("/api/priority/set", {...d, entity, id: R.id});
    F.toast("Priority changed"); if (then) then(); CACHE.matrix = null; }, "Change");

UI.newFinding = (pid, vid) => F.modal("Record a finding",
  "One observation, with its own owner, clock and evidence. §4.2 of the review: a visit "
  + "that found five problems needs five of each.",
  F.field("project_id", "Project", {options: projOpts(), value: pid || CACHE.pid || ""}) +
  F.field("title", "What was found", {placeholder: "Corridor ceiling void 320mm against 400mm"}) +
  F.field("category", "Category", {options: BOOT.finding_categories || []}) +
  F.field("location", "Where exactly", {placeholder: "Level 7, corridor at grid F",
    hint: "Be specific — this is what makes “found here before” answerable."}) +
  F.field("description", "Detail", {type: "textarea", rows: 3}) +
  F.field("responsible_team", "Responsible team",
    {options: [["", "— unassigned —"]].concat(deptOpts())}) +
  F.field("priority", "Priority", {options: priOpts(), value: BOOT.priority_default}) +
  F.field("tat_days", "TAT (working days)", {type: "number", value: 7}) +
  F.field("non_compliance", "", {type: "checkbox",
    placeholder: "Non-compliance against approved IFC (raises an NCR)"}),
  async d => { const r = await F.act("/api/finding/create", {...d, visit_id: vid || ""});
    refresh(r.recurrence_of ? "Finding recorded — this has been found here before"
                            : "Finding recorded"); }, "Record");

UI.assignFinding = (R, then) => F.modal("Assign this finding",
  "§5 of the review: individual findings should be assignable to the relevant team.",
  F.field("responsible_team", "Team", {options: deptOpts(), value: R.responsible_team || ""}) +
  F.field("person_id", "Person", {options: peopleOpts(R.responsible_team)}) +
  F.field("tat_days", "TAT (working days)", {type: "number", value: R.tat_days || 7}),
  async d => { await F.act("/api/finding/assign", {...d, id: R.id});
    F.toast("Assigned"); if (then) then(); }, "Assign");

UI.raiseFinding = (R, then) => F.modal("Raise this finding",
  "Visit → Finding → Relevant team → RFI / Action, which is the chain §5 asks for. The "
  + "case stays linked to the finding and the finding to the visit.",
  F.field("as", "Raise it as", {options: [
    ["NCR", "NCR — non-conformance, §16 route"],
    ["RFI", "RFI — request for information"],
    ["DCR", "DCR — design change request"],
    ["SMP", "SMP — material sample / mock-up"]], value: R.non_compliance ? "NCR" : "RFI"}),
  async d => { const r = await F.act("/api/finding/raise", {...d, id: R.id});
    F.toast(`${r.ref} raised`); if (then) then(); CACHE.matrix = null; }, "Raise");

UI.findingTask = (R, then) => F.modal("Make this a task",
  "For work that belongs on the department's own queue rather than on a route.",
  `<div class="note">Creates a stage-13 step on <b>${esc(R.responsible_team || "Architecture")}</b>
    carrying this finding's priority and TAT, linked back to the finding.</div>`,
  async d => { const r = await F.act("/api/finding/raise", {...d, id: R.id, as: "TASK"});
    F.toast("Task created"); if (then) then(); }, "Create task");

UI.resolveFinding = (R, then) => F.modal("Resolve this finding",
  "Record what was actually done. A finding closed with no resolution cannot be checked "
  + "on the next visit — which is exactly how the same problem gets found four times.",
  F.field("status", "Outcome", {options: [
    ["resolved", "Resolved — done, pending verification"],
    ["closed", "Closed — verified"]]}) +
  F.field("resolution", "What was done", {type: "textarea", rows: 3}),
  async d => { await F.act("/api/finding/resolve", {...d, id: R.id});
    F.toast("Recorded"); if (then) then(); }, "Record");

UI.findingLesson = (R, then) => F.modal("Raise a lesson from this finding",
  "§12 of the review: a lesson captures why it happened and what should change — not "
  + "what the defect was.",
  F.field("title", "The lesson, in one line", {value: R.title}) +
  F.field("root_cause", "Root cause — why did it happen", {type: "textarea", rows: 3}) +
  F.field("delay_kind", "The delay was", {options: [["", "— none —"],
    ["internal", "Internal — our own process"], ["external", "External — outside Zameen"],
    ["dependency", "A dependency on another team"], ["process", "A process or document gap"]]}) +
  F.field("delay_owner", "Whose process", {value: R.responsible_team || ""}) +
  F.field("preventive_action", "What should change", {type: "textarea", rows: 2}),
  async d => { await F.act("/api/finding/lesson", {...d, id: R.id});
    F.toast("Lesson raised — it needs a ruling before it can be adopted");
    if (then) then(); }, "Raise lesson");

UI.editSetting = (s) => {
  if (!s) return;
  const opts = (s.options || "").split("|").filter(Boolean);
  const field = s.kind === "bool"
    ? F.field("value", s.label, {options: [["1", "Yes"], ["0", "No"]], value: s.value})
    : opts.length
      ? F.field("value", s.label, {options: opts, value: s.value})
      : s.kind === "int"
        ? F.field("value", s.label, {type: "number", value: s.value})
        : F.field("value", s.label, {type: s.kind === "text" ? "textarea" : "text",
                                     rows: 3, value: s.value});
  F.modal(s.label, s.note,
    field
    + F.field("confirm", "", {type: "checkbox", value: s.confirmed,
      placeholder: "Confirm this definition — it stops being marked UNCONFIRMED",
      hint: "Confirming records your name against it. Every calculation that depends on "
          + "this definition becomes defensible; leaving it unconfirmed keeps the warning "
          + "on screen, which is the honest state until the business has actually decided."}),
    async d => { const r = await F.act("/api/setting/save", {...d, key: s.key});
      BOOT = await api("/api/bootstrap");
      refresh(r.confirmed ? "Confirmed" : "Saved — still unconfirmed"); },
    "Save");
};

UI.hold = (tid) => F.modal("Put this step on hold",
  "§27 of the review defines hold as time progress is intentionally or externally "
  + "blocked. It is excluded from the team's own time, so an unexplained hold is an "
  + "unexplained gap in the SLA.",
  F.field("reason", "What is blocking it", {type: "textarea", rows: 3}),
  async d => { await F.act("/api/task/hold", {...d, id: tid});
    refresh("On hold — the clock is separated"); }, "Hold");

UI.improve = (R, then) => F.modal("Improvement action",
  "A lesson can be adopted into a checklist and still have work behind it. The review "
  + "asked to see open and closed improvements separately.",
  F.field("improvement_status", "Status", {options: [
    ["proposed", "Proposed"], ["agreed", "Agreed"], ["in_progress", "In progress"],
    ["done", "Done"], ["dropped", "Dropped"]], value: R.improvement_status}) +
  F.field("improvement_owner", "Owner", {value: R.improvement_owner || ""}) +
  F.field("improvement_due", "Due", {type: "date", value: R.improvement_due || ""}) +
  F.field("preventive_action", "What should change", {type: "textarea", rows: 3,
    value: R.preventive_action || ""}) +
  F.field("note", "Note", {type: "textarea", rows: 2}),
  async d => { await F.act("/api/llr/improve", {...d, id: R.id});
    F.toast("Improvement updated"); if (then) then(); }, "Save");

/* lessons drawer gains root cause + the improvement action */
const _llrBody = E.body.llr;
E.body.llr = (d) => {
  const R = d.record;
  return `${sec("Root cause — §12 of the review")}
  ${dl([
    ["Why it happened", R.root_cause
      ? esc(R.root_cause)
      : `<span style="color:var(--bad)">not recorded — a lesson without a root cause
         cannot drive an improvement, and will be raised again next project</span>`],
    ["The delay was", R.delay_kind
      ? `<span class="chip ${R.delay_kind === "internal" ? "c-late"
        : R.delay_kind === "external" ? "c-wait" : "c-hold"}">${esc(R.delay_kind)}</span>` : null],
    ["Whose process", esc(R.delay_owner || "")],
    ["Turnaround lost", R.delay_days ? `<b style="color:var(--bad)">${R.delay_days} days</b>` : null],
    ["Dependency", esc(R.dependency || "")],
    ["What should change", esc(R.preventive_action || "")],
    ["Improvement", `<span class="chip ${R.improvement_status === "done" ? "c-done"
      : "c-hold"}">${esc((R.improvement_status || "proposed").replace("_", " "))}</span>`
      + (R.improvement_owner ? ` <span class="mut">${esc(R.improvement_owner)}</span>` : "")],
    ["Seen by", [R.head_notified_at && "Department head",
      R.audit_notified_at && "Audit / IA"].filter(Boolean)
      .map(t => `<span class="chip c-done">${t}</span>`).join(" ")
      || `<span class="mut">not escalated for visibility</span>`],
    ["From a finding", R.origin_finding_id
      ? E.link("finding", R.origin_finding_id, "the site finding that produced it") : null],
  ])}` + _llrBody(d);
};

const _llrActs = E.acts.llr;
E.acts.llr = (d) => `<button class="btn" data-x="llr-improve">Improvement action</button> `
  + _llrActs(d);

const _wire2 = E.wire;
E.wire = (d, w) => {
  _wire2(d, w);
  w.querySelectorAll('[data-x="llr-improve"]').forEach(b => b.onclick = () =>
    UI.improve(d.record, () => E.open("llr", d.id, {back: true})));
};

/* ═══════════════════════════════════════════════════════════════════════════
   #11 · "Add a Project", not "Open a Project", everywhere
   ═══════════════════════════════════════════════════════════════════════════ */
UI.newProject = () => F.modal("Add a project",
  "Manual §3 — creates all 14 stations and opens the intake.",
  F.field("name", "Project name", {placeholder: "Zameen Sapphire"}) +
  F.field("code", "Code", {placeholder: "ZS2", hint: "Used on refs — MAR-ZS2-104"}) +
  F.field("kind", "Type", {options: ["Residential", "Mixed Use", "Commercial"]}) +
  F.field("city", "City", {options: ["Lahore", "Islamabad", "Multan", "Karachi"]}),
  async d => {
    const r = await F.act("/api/project/create", d);
    CACHE.pid = r.id;
    BOOT = await api("/api/bootstrap");
    refresh("Project added — fill the intake to unlock Stage 3");
  }, "Add project");

/* ═══════════════════════════════════════════════════════════════════════════
   #7 · Logging a visit, with as many findings as the visit actually found.
   The review's example: "During one visit, 5 separate problems may be
   identified... The system should allow the user to create Finding 1..5."
   ═══════════════════════════════════════════════════════════════════════════ */
UI.newVisit = (pid) => {
  let n = 0;
  const block = (i) => `
    <div class="fblock" data-i="${i}">
      <div class="fblock-h"><b>Finding ${i + 1}</b>
        ${i ? `<button type="button" class="btn sm" data-drop="${i}">Remove</button>` : ""}</div>
      ${F.field(`f${i}_title`, "What was found",
        {placeholder: "Corridor ceiling void 320mm against 400mm required"})}
      ${F.field(`f${i}_category`, "Category", {options: BOOT.finding_categories || []})}
      ${F.field(`f${i}_location`, "Where exactly",
        {placeholder: "Level 7, corridor at grid F",
         hint: "Specific enough that “found here before” is answerable."})}
      ${F.field(`f${i}_description`, "Detail", {type: "textarea", rows: 2})}
      ${F.field(`f${i}_responsible_team`, "Responsible team",
        {options: [["", "— unassigned —"]].concat(deptOpts())})}
      ${F.field(`f${i}_priority`, "Priority",
        {options: priOpts(), value: BOOT.priority_default})}
      ${F.field(`f${i}_tat_days`, "TAT (working days)", {type: "number", value: 7})}
      ${F.field(`f${i}_non_compliance`, "", {type: "checkbox",
        placeholder: "Non-compliance against approved IFC — raises an NCR"})}
    </div>`;

  const m = F.modal("Log a site visit",
    "Manual §15 — one visit per project per month; logging it closes the obligation. "
    + "The visit is a container: record each problem as its own finding so it gets its "
    + "own owner, clock and evidence. A finding marked non-compliant automatically "
    + "raises an NCR on the §16 route.",
    F.field("project_id", "Project", {options: projOpts(), value: pid || CACHE.pid || ""}) +
    F.field("visited_on", "Date", {type: "date",
      value: new Date().toISOString().slice(0, 10)}) +
    F.field("photos", "Photos taken", {type: "number", value: 0}) +
    F.field("summary", "Summary of the walk", {type: "textarea", rows: 2,
      placeholder: "What was inspected overall"}) +
    `<div id="fbs">${block(0)}</div>
     <button type="button" class="btn sm" id="addf">+ Add another finding</button>`,
    async v => {
      const rows = [];
      document.querySelectorAll("#fbs .fblock").forEach(b => {
        const i = b.dataset.i;
        if (!String(v[`f${i}_title`] || "").trim()) return;
        rows.push({
          title: v[`f${i}_title`], category: v[`f${i}_category`],
          location: v[`f${i}_location`], description: v[`f${i}_description`],
          responsible_team: v[`f${i}_responsible_team`],
          priority: v[`f${i}_priority`], tat_days: v[`f${i}_tat_days`],
          non_compliance: v[`f${i}_non_compliance`] ? 1 : 0,
        });
      });
      const r = await F.act("/api/visit/create",
        {project_id: v.project_id, visited_on: v.visited_on, photos: v.photos,
         summary: v.summary, findings: JSON.stringify(rows)});
      refresh(`Visit logged — ${r.findings.length} finding`
        + (r.findings.length === 1 ? "" : "s")
        + (r.ncr.length ? `, ${r.ncr.length} NCR raised (${r.ncr.join(", ")})` : "")
        + (r.recurrences ? `, ${r.recurrences} seen before` : ""));
    }, "Log the visit");

  const wire = () => {
    m.querySelectorAll("[data-drop]").forEach(b => b.onclick = () => {
      const el = m.querySelector(`.fblock[data-i="${b.dataset.drop}"]`);
      if (el) el.remove();
    });
    m.querySelectorAll('[name$="_non_compliance"]').forEach(cb =>
      cb.onchange = () => cb.closest(".zm-fld").classList.toggle("nc", cb.checked));
  };
  m.querySelector("#addf").onclick = () => {
    n += 1;
    m.querySelector("#fbs").insertAdjacentHTML("beforeend", block(n));
    wire();
    m.querySelector(`.fblock[data-i="${n}"]`).scrollIntoView({block: "nearest"});
  };
  wire();
};
