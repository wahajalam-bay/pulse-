/* ZD PULSE — the entity layer.

   WHY THIS FILE EXISTS
     The first build could show you a number and let you press a button next to
     it. What it could not do was let you FOLLOW anything. A task named a
     workflow you could not open; a case named a project you could not reach; a
     drawing named a revision with no history behind it. Every table was a
     terminus.

     This file makes every row a door. One endpoint — /api/entity/<kind>/<id> —
     returns any record with its project, its notes, its attached documents and
     its slice of the ledger, and one drawer renders it with the actions that
     record can take. Open a case, walk to its project, walk to the stage, open
     the checklist, see the lesson that put an item on it. Nothing is a dead end.

   THREE THINGS LIVE HERE
     E.open()   the drawer, with a breadcrumb stack so you can walk back
     E.pal()    the command palette — one box over every register (Ctrl/⌘+K)
     E.notify() what is actually waiting on the person reading the screen
*/

const E = {stack: [], cur: null};

/* ── a link to anything. data-e="kind:id" works anywhere on the page. ──── */
E.link = (kind, id, text, cls) =>
  `<span class="kl ${cls || ""}" data-e="${kind}:${id}">${esc(text)}</span>`;

document.addEventListener("click", ev => {
  const a = ev.target.closest("[data-e]");
  if (a) {
    /* A control INSIDE a clickable row wins — pressing Decide on a case row must
       decide, not open the drawer behind it. A control that IS the link opens. */
    const it = ev.target.closest("button,a,input,select,textarea,label");
    if (!(it && it !== a && a.contains(it))) {
      ev.preventDefault(); ev.stopPropagation();
      const [k, i] = a.dataset.e.split(":");
      return E.open(k, +i);
    }
  }
  const t = ev.target.closest("[data-goto]");
  if (t) {
    ev.preventDefault();
    E.close();
    const [tab, pid] = t.dataset.goto.split(":");
    if (pid) CACHE.pid = +pid;
    return go(tab);
  }
});

/* ── the drawer ─────────────────────────────────────────────────────────── */
E.close = () => {
  document.querySelectorAll(".zdrw").forEach(x => x.remove());
  E.stack = []; E.cur = null;
  document.onkeydown = null;
  if (location.hash.startsWith("#/e/")) history.replaceState(null, "", "#/" + TAB);
};

E.open = async (kind, id, opts = {}) => {
  if (E.cur && !opts.back) E.stack.push(E.cur);
  E.cur = {kind, id};
  history.replaceState(null, "", `#/e/${kind}/${id}`);
  let d;
  try { d = await api(`/api/entity/${kind}/${id}`); }
  catch (x) { return F.toast(x.message, true); }
  if (d.error) return F.toast("That record no longer exists.", true);
  E.draw(d);
};

E.back = () => {
  const prev = E.stack.pop();
  if (!prev) return E.close();
  E.cur = null;
  E.open(prev.kind, prev.id, {back: true});
};

const KINDNAME = {
  project: "Project", task: "Step", case: "Case", drawing: "Drawing",
  transmittal: "Transmittal", person: "Person", coordination: "Cross-team ask",
  obligation: "Obligation", visit: "Site visit", llr: "Lesson learned",
  authority: "Authority file", product: "Catalog step",
};

E.draw = (d) => {
  document.querySelectorAll(".zdrw").forEach(x => x.remove());
  const crumbs = E.stack.map((s, i) =>
    `<button data-crumb="${i}">${esc(KINDNAME[s.kind] || s.kind)}</button><span>›</span>`
  ).join("");

  const w = el(`<div class="zdrw">
    <div class="zw-bd"></div>
    <div class="zw-box" role="dialog" aria-modal="true">
      <div class="zw-h">
        <div class="zw-crumb">
          ${E.stack.length ? `<button data-back>‹ Back</button><span>·</span>` : ""}
          ${crumbs}
          <span class="prov">${esc(KINDNAME[d.kind] || d.kind)}</span>
          ${d.project ? `<span>·</span>${E.link("project", d.project.id, d.project.name)}` : ""}
        </div>
        <div class="zw-t">
          <div><h2>${esc(d.title)}</h2><p>${esc(d.sub || "")}</p></div>
          <button class="zw-x" aria-label="Close">✕</button>
        </div>
      </div>
      <div class="zw-act">${(E.acts[d.kind] || (() => ""))(d)}</div>
      <div class="zw-b">${(E.body[d.kind] || E.body._)(d)}
        ${E.docs(d)}${E.notes(d)}${E.hist(d)}</div>
    </div></div>`);

  document.body.appendChild(w);
  w.querySelector(".zw-bd").onclick = E.close;
  w.querySelector(".zw-x").onclick = E.close;
  const b = w.querySelector("[data-back]"); if (b) b.onclick = E.back;
  w.querySelectorAll("[data-crumb]").forEach(x => x.onclick = () => {
    const i = +x.dataset.crumb, tgt = E.stack[i];
    E.stack = E.stack.slice(0, i); E.cur = null;
    E.open(tgt.kind, tgt.id, {back: true});
  });
  w.querySelectorAll("[data-doc]").forEach(x =>
    x.onclick = () => UI.newDoc(d.kind, d.id, d.project && d.project.id));
  w.querySelectorAll("[data-notenew]").forEach(x =>
    x.onclick = () => UI.note(`${d.kind}:${d.id}`));
  UI.bind(w);
  E.wire(d, w);
  document.onkeydown = ev => { if (ev.key === "Escape") E.close(); };
};

/* per-kind extra wiring that needs the payload */
E.wire = (d, w) => {
  const R = d.record;
  const rf = async (fn, msg) => { try { await fn(); F.toast(msg); E.open(d.kind, d.id, {back: true}); CACHE.matrix = null; render(); } catch (x) { F.toast(x.message, true); } };
  w.querySelectorAll("[data-x]").forEach(btn => btn.onclick = () => {
    const a = btn.dataset.x;
    if (a === "revise-dwg") return UI.reviseDrawing(R, () => E.open("drawing", d.id, {back: true}));
    if (a === "auth-respond") return UI.authRespond(R, () => E.open("authority", d.id, {back: true}));
    if (a === "llr-rule") return UI.llrRule(R, () => E.open("llr", d.id, {back: true}));
    if (a === "llr-promote") return UI.llrPromote(R, () => E.open("llr", d.id, {back: true}));
    if (a === "case-withdraw") return UI.withdraw(R, () => E.open("case", d.id, {back: true}));
    if (a === "close-ask") return rf(() =>
      F.act("/api/coordination/close", {id: R.id}), "Ask closed");
    if (a === "project-close") return UI.closeProject(R);
    if (a === "intake") return UI.intake(R.id);
    if (a === "newcase") return UI.newCase(R.id);
    if (a === "newask") return UI.newAsk(R.id);
    if (a === "newvisit") return UI.newVisit(R.id);
    if (a === "newdwg") return UI.newDrawing(R.id);
    if (a === "newtr") return UI.newTransmittal(R.id);
    if (a === "newllr") return UI.newLLR(R.id, d.kind, d.id);
    if (a === "authsubmit") return UI.authSubmit(R.id);
  });
};

/* ── shared blocks ──────────────────────────────────────────────────────── */
const dl = (pairs) => `<dl class="dl">${pairs.filter(Boolean).map(([k, v]) =>
  `<dt>${esc(k)}</dt><dd>${v == null || v === "" ? '<span class="mut">—</span>' : v}</dd>`
).join("")}</dl>`;

const sec = (title, right) => `<div class="zw-s"><span>${title}</span>${right || ""}</div>`;

E.docs = (d) => sec("Attached documents",
  `<button data-doc>+ Attach a link</button>`) + (d.documents.length
  ? `<div class="feed">${d.documents.map(x => `<div class="fe">
       <span>${esc(x.kind || "Reference")} · Rev ${esc(x.revision || "A")}</span>
       <a href="${esc(x.link)}" target="_blank" rel="noopener">${esc(x.title)} ↗</a>
       <span class="who"> — ${esc(x.added_by || "")} ${esc((x.added_at || "").slice(0, 10))}</span>
     </div>`).join("")}</div>`
  : `<div class="emptyx"><b>Nothing attached</b>The register records which file is
     current and what it belongs to. The file itself stays on the drive.</div>`);

E.notes = (d) => sec("Notes", `<button data-notenew>+ Add a note</button>`)
  + (d.notes.length
    ? `<div class="feed">${d.notes.map(x => `<div class="fe">
         <span>${esc(x.who || "")} · ${esc((x.at || "").replace("T", " ").slice(0, 16))}</span>
         ${esc(x.body)}</div>`).join("")}</div>`
    : `<div class="emptyx"><b>No notes</b>This is what currently lives in WhatsApp.</div>`);

E.hist = (d) => sec("History") + (d.ledger.length
  ? `<div class="feed">${d.ledger.slice(0, 25).map(x => `<div class="fe ${x.blocked ? "blk" : ""}">
       <span>${esc((x.at || "").replace("T", " ").slice(0, 16))} · ${esc(x.action)}
         ${x.blocked ? " · BLOCKED" : ""}</span>
       ${esc(x.summary || "")}<span class="who"> — ${esc(x.who || "")}${x.tier != null ? ` (T${x.tier})` : ""}</span>
     </div>`).join("")}</div>`
  : `<div class="emptyx"><b>Nothing recorded yet</b>Every action taken on this record
     lands here, with the authority it was taken under.</div>`);

const miniCell = (label, val, cls, goto) =>
  `<div class="${cls || ""}${goto ? " cl" : ""}" ${goto ? `data-goto="${goto}"` : ""}>
     <b>${val}</b><span>${esc(label)}</span></div>`;

/* ── per-kind bodies ────────────────────────────────────────────────────── */
E.body = {};

E.body._ = (d) => dl(Object.entries(d.record)
  .filter(([k, v]) => v !== null && v !== "" && k !== "id")
  .map(([k, v]) => [k.replace(/_/g, " "), esc(String(v))]));

E.body.project = (d) => {
  const R = d.record, x = d.extra, c = x.counts;
  const intakeFilled = Object.entries(x.intake || {})
    .filter(([k, v]) => !["project_id", "updated_at", "updated_by"].includes(k) && v).length;
  return `
  <div class="mini">
    ${miniCell("Steps", c.tasks, "", "tasks:" + R.id)}
    ${miniCell("Open cases", c.open_cases, c.open_cases ? "hot" : "ok", "cases")}
    ${miniCell("Open asks", c.asks, c.asks ? "cool" : "ok", "coord")}
    ${miniCell("Drawings", c.drawings, "", "drawings:" + R.id)}
    ${miniCell("Transmittals", c.transmittals, "", "drawings:" + R.id)}
    ${miniCell("Site visits", c.visits, "", "site")}
    ${miniCell("Lessons", c.lessons, "", "llr")}
  </div>

  ${sec("Intake — Manual §3.1", `<button data-x="intake">Open the intake</button>`)}
  <div class="${intakeFilled === 7 ? "feed" : "emptyx"}">
    ${intakeFilled === 7
      ? `<div class="fe"><span>Complete</span>All seven fields filled${x.intake.updated_by
          ? ` — last by ${esc(x.intake.updated_by)}` : ""}. Stage 3 is unblocked.</div>`
      : `<b>${intakeFilled} of 7 fields</b>Stage 3 will refuse to initiate until this is
         complete, and it will name the missing fields.`}
  </div>

  ${sec("The spine")}
  <div class="tl">${x.stages.map(s => {
    const nm = x.stage_names[s.stage] || "";
    const cls = s.status === "done" ? "past" : s.status === "running" ? "cur" : "";
    const chk = s.checklist
      ? `${s.checks_done || 0}/${s.checks || 0} checks${s.checklist.signed_at ? " · signed" : ""}`
      : "no checklist yet";
    return `<div class="tli ${cls}">
      <b>${s.stage} · ${esc(nm)}</b>
      <em>${esc(s.status.replace("_", " "))} · own ${s.own_days || 0}d · wait ${s.wait_days || 0}d
        · ${esc(chk)}${s.planned_end ? ` · planned end ${esc(s.planned_end.slice(0, 10))}` : ""}</em>
      <div style="margin-top:5px;display:flex;gap:5px;flex-wrap:wrap">
        ${s.status === "not_started"
          ? `<button class="btn sm" data-stage="${R.id}:${s.stage}:not_started">Initiate</button>`
          : `<button class="btn sm" data-chk="${R.id}:${s.stage}">Checklist</button>
             ${s.status === "running"
               ? `<button class="btn sm" data-stage="${R.id}:${s.stage}:running">Sign off</button>` : ""}`}
      </div></div>`;
  }).join("")}</div>`;
};

E.body.task = (d) => {
  const R = d.record, v = d.extra.view, p = d.extra.product;
  return `
  <div class="mini">
    ${miniCell("Baseline", v.baseline == null ? "—" : v.baseline + "d")}
    ${miniCell("Own", v.own + "d")}
    ${miniCell("Wait", v.wait + "d", v.wait ? "cool" : "")}
    ${miniCell("Variance", v.variance == null ? "—" : (v.variance > 0 ? "+" : "") + v.variance,
      v.variance > 0 ? "hot" : v.variance < 0 ? "ok" : "")}
    ${miniCell("Revisions", v.revision, v.revision ? "hot" : "")}
  </div>
  ${sec("The step")}
  ${dl([
    ["Status", stChip(R.status)],
    ["Project", d.project ? E.link("project", d.project.id, d.project.name) : null],
    ["Stage", `${R.stage} — ${esc(BOOT.stages.find(s => s.stage === R.stage)?.name || "")}`],
    ["Workflow", esc(R.workflow || "")],
    ["Team", esc(R.team)],
    ["Lane", R.is_external
      ? `<span class="chip c-ext">${esc(R.lane)}</span> — outside the department, so this
         time is booked as wait, never against the team`
      : esc(R.lane)],
    ["Assigned to", d.extra.person && d.extra.person.id
      ? E.link("person", d.extra.person.id, d.extra.person.name)
        + ` <span class="mut">${esc(d.extra.person.designation || "")}</span>`
      : `<span class="mut">nobody</span>`],
    ["Planned", `${dash(R.planned_sd)} → ${dash(R.planned_ed)}`],
    ["Actual", `${dash(R.actual_sd)} → ${dash(R.actual_ed)}`],
    ["Note", esc(R.note || "")],
  ])}
  ${p ? sec("Where this came from") + dl([
    ["Catalog step", E.link("product", p.id, `${p.workflow} · step ${p.seq}`)],
    ["Published TAT", p.tat_days == null
      ? `<span class="mut">blank in the source document — rendered as “—”, never zero</span>`
      : p.tat_days + " working days"],
    ["Booklet / Manual", `${esc(p.tat_booklet || "—")} / ${esc(p.tat_manual || "—")}`
      + (p.tat_manual && p.tat_manual !== p.tat_booklet
        ? ` <span class="chip c-late">conflict</span>` : "")],
    ["Source", `<span class="prov ${(p.source || "").includes("Manual") ? "manual" : ""}">${esc(p.source || "")}</span>`],
    ["Marks", [p.maker && "maker", p.checker && "checker", p.rework && "rework loop",
      p.gate && "gate", p.variable && "variable duration"].filter(Boolean)
      .map(t => `<span class="chip c-queue">${t}</span>`).join(" ") || "—"],
  ]) : ""}
  ${d.extra.siblings.length > 1 ? sec(`The rest of this stage — ${esc(R.team)}`)
    + `<div class="card"><table class="tbl"><tbody>${d.extra.siblings.map(s => `
      <tr class="rc" data-e="task:${s.id}"><td class="mut" style="width:26px">${s.seq}</td>
      <td><b>${esc(s.title)}</b></td><td style="width:74px">${stChip(s.status)}</td>
      <td class="num mut" style="width:52px">${s.baseline_days == null ? "—" : s.baseline_days + "d"}</td>
      </tr>`).join("")}</tbody></table></div>` : ""}`;
};

E.body.case = (d) => {
  const R = d.record, x = d.extra;
  const gate = R.value_pkr >= BOOT.thresholds.ceo ? "CEO Office"
    : R.value_pkr >= BOOT.thresholds.cpc ? "CPC" : null;
  return `
  ${sec("The route", `<span class="prov manual">${esc(x.source || "")}</span>`)}
  <div class="tl">${x.lanes.map((l, i) => `
    <div class="tli ${i < R.position ? "past" : i === R.position ? "cur" : ""} ${l.is_stub ? "stub" : ""}">
      <b>${esc(l.label)}</b>
      <em>${esc(l.owner_lane)}${l.sla_days ? ` · SLA ${l.sla_days}d` : ""}
        ${l.is_stub ? ` · <span class="chip c-ext">external — no system yet</span>` : ""}
        ${l.age != null ? ` · <b>${l.age}d in this lane</b>` : ""}</em>
      ${l.left_at ? `<div class="out">${esc(l.outcome || "passed")} by ${esc(l.actor || "—")}
        on ${esc((l.left_at || "").slice(0, 10))}${l.note ? ` — ${esc(l.note)}` : ""}</div>` : ""}
    </div>`).join("")}</div>
  ${sec("The case")}
  ${dl([
    ["Reference", `<b>${esc(R.ref)}</b>`],
    ["Type", `${esc(R.type)} — ${esc(x.route || "")}`],
    ["Status", stChip(R.status === "open" ? "running" : R.status === "rejected" ? "hold" : "done")],
    ["Project", d.project ? E.link("project", d.project.id, d.project.name) : null],
    ["Value", R.value_pkr ? pkr(R.value_pkr)
      + (gate ? ` <span class="chip c-late">${gate} approval required</span>` : "") : null],
    ["Raised by", `${esc(R.raised_by || "")} on ${esc(R.raised_at || "")}`],
    ["Closed", R.closed_at ? esc(R.closed_at.slice(0, 10)) : null],
    ["Note", esc(R.note || "")],
  ])}
  ${x.asks && x.asks.length ? sec("Clocks this case started")
    + `<div class="card"><table class="tbl"><tbody>${x.asks.map(a => `
      <tr class="rc" data-e="coordination:${a.id}"><td><b>${esc(a.to_lane)}</b></td>
      <td>${esc(a.ask)}</td><td class="num mut">${a.closed_at ? "closed" : "open"}</td>
      </tr>`).join("")}</tbody></table></div>` : ""}`;
};

E.body.drawing = (d) => {
  const R = d.record, x = d.extra;
  return `
  ${sec("The sheet")}
  ${dl([
    ["Number", `<b>${esc(R.number)}</b>`],
    ["Title", esc(R.title)],
    ["Discipline", esc(R.discipline || "")],
    ["Current revision", `<span class="chip c-queue">Rev ${esc(R.revision)}</span>
       <span class="chip ${R.status === "IFC" ? "c-done" : "c-run"}">${esc(R.status)}</span>`],
    ["First issued at stage", R.stage],
    ["Project", d.project ? E.link("project", d.project.id, d.project.name) : null],
    ["File", R.link ? `<a href="${esc(R.link)}" target="_blank" rel="noopener">open on the drive ↗</a>` : null],
  ])}
  ${sec("Revision history")}
  ${x.revs.length ? `<div class="feed">${x.revs.map(r => `<div class="fe">
      <span>Rev ${esc(r.revision)} · ${esc(r.status || "")} · ${esc((r.at || "").slice(0, 10))}</span>
      ${esc(r.note || "")}<span class="who"> — ${esc(r.by_whom || "")}</span></div>`).join("")}</div>`
    : `<div class="emptyx"><b>No revisions recorded</b>“Which drawing is the contractor
       actually building from” is the question a register exists to answer.</div>`}
  ${sec("Issued on")}
  ${x.transmittals.length ? `<div class="card"><table class="tbl"><tbody>
    ${x.transmittals.map(t => `<tr class="rc" data-e="transmittal:${t.id}">
      <td><b>${esc(t.ref)}</b></td><td>${esc(t.phase)}</td>
      <td class="mut">Rev ${esc(t.issued_rev || "")}</td>
      <td class="mut">${esc((t.issued_at || "").slice(0, 10))}</td></tr>`).join("")}
    </tbody></table></div>`
    : `<div class="emptyx"><b>Never formally issued</b>A sheet that has not been on a
       transmittal has no contractual standing (§5).</div>`}`;
};

E.body.transmittal = (d) => {
  const R = d.record, x = d.extra;
  return `
  ${sec("The issuance")}
  ${dl([
    ["Reference", `<b>${esc(R.ref)}</b>`],
    ["Phase", `<span class="chip c-run">${esc(R.phase)}</span>`],
    ["Issued to", (R.issued_to || "").split(",").map(s =>
      `<span class="chip c-ext">${esc(s.trim())}</span>`).join(" ")],
    ["Sheets", R.drawing_count],
    ["Issued", `${esc((R.issued_at || "").slice(0, 16).replace("T", " "))} by ${esc(R.issued_by || "")}`],
    ["Project", d.project ? E.link("project", d.project.id, d.project.name) : null],
    ["Note", esc(R.note || "")],
  ])}
  ${sec(`Sheet list — ${x.sheets.length} drawings`)}
  ${x.sheets.length ? `<div class="card"><table class="tbl">
    <thead><tr><th>Number</th><th>Title</th><th>Issued at</th><th>Now</th></tr></thead>
    <tbody>${x.sheets.map(s => `<tr class="rc" data-e="drawing:${s.id}">
      <td><b>${esc(s.number)}</b></td><td>${esc(s.title)}</td>
      <td><span class="chip c-queue">Rev ${esc(s.issued_rev || "")}</span></td>
      <td class="mut">Rev ${esc(s.revision)} · ${esc(s.status)}</td></tr>`).join("")}
    </tbody></table></div>`
    : `<div class="emptyx"><b>No sheet list</b>Recorded as a count only.</div>`}`;
};

E.body.person = (d) => {
  const R = d.record, k = d.extra.kpi;
  return `
  <div class="mini">
    ${miniCell("Open", k.open)}
    ${miniCell("Closed", k.done)}
    ${miniCell("On time", k.done ? Math.round(k.on_time / k.done * 100) + "%" : "—",
      k.done && k.on_time / k.done >= .7 ? "ok" : k.done ? "hot" : "")}
    ${miniCell("Revisions", k.revisions, k.revisions ? "hot" : "")}
  </div>
  ${sec("Who")}
  ${dl([
    ["Name", `<b>${esc(R.name)}</b>`],
    ["Designation", esc(R.designation || "")],
    ["Team", esc(R.team)],
    ["Tier", `T${R.tier} — ${R.tier === 0 ? "department head" : R.tier === 1 ? "senior manager"
      : R.tier === 2 ? "lead" : "member"}`],
    ["Email", esc(R.email || "")],
  ])}
  ${sec("Their work")}
  ${d.extra.tasks.length ? `<div class="card scroll"><table class="tbl">
    <thead><tr><th>Step</th><th>Project</th><th class="num">Base</th>
      <th class="num">Own</th><th>Status</th></tr></thead>
    <tbody>${d.extra.tasks.map(t => `<tr class="rc" data-e="task:${t.id}">
      <td><b>${esc(t.title)}</b></td><td class="mut">${esc(t.pname || "")}</td>
      <td class="num mut">${t.baseline_days == null ? "—" : t.baseline_days}</td>
      <td class="num">${t.own_days || "—"}</td><td>${stChip(t.status)}</td>
      </tr>`).join("")}</tbody></table></div>`
    : `<div class="emptyx"><b>Nothing assigned</b></div>`}`;
};

E.body.coordination = (d) => {
  const R = d.record, x = d.extra;
  const over = R.sla_days && x.age > R.sla_days;
  return `
  <div class="mini">
    ${miniCell("Age", x.age + "d", over ? "hot" : "cool")}
    ${miniCell("SLA", R.sla_days ? R.sla_days + "d" : "—")}
    ${miniCell("Overrun", over ? "+" + (x.age - R.sla_days) + "d" : "—", over ? "hot" : "ok")}
  </div>
  ${sec("The ask")}
  ${dl([
    ["What is needed", `<b>${esc(R.ask)}</b>`],
    ["From", esc(R.from_team)],
    ["Waiting on", `<span class="chip ${x.external ? "c-ext" : "c-queue"}">${esc(R.to_lane)}</span>
      ${x.external ? " — a department with no system yet. The clock is held here and the "
        + "wait is recorded; the day their system connects this becomes a live lane." : ""}`],
    ["Project", d.project ? E.link("project", d.project.id, d.project.name) : null],
    ["Stage", R.stage],
    ["Opened", esc(R.opened_at || "")],
    ["Closed", R.closed_at ? esc(R.closed_at.slice(0, 10)) : `<span class="chip c-wait">still open</span>`],
  ])}`;
};

E.body.obligation = (d) => {
  const R = d.record;
  const today = new Date().toISOString().slice(0, 10);
  return `
  ${sec("The commitment")}
  ${dl([
    ["Obligation", `<b>${esc(R.label)}</b>`],
    ["Cadence", esc(R.cadence)],
    ["Due", esc(R.due_on)],
    ["Status", R.done_at ? `<span class="chip c-done">Done ${esc(R.done_at.slice(0, 10))}</span>`
      : R.due_on < today ? `<span class="chip c-late">Missed</span>`
      : `<span class="chip c-queue">Due</span>`],
    ["Evidence", R.evidence ? esc(R.evidence)
      : `<span class="mut">none recorded — an obligation ticked with no evidence is not evidence</span>`],
    ["Completed by", esc(R.done_by || "")],
    ["Project", d.project ? E.link("project", d.project.id, d.project.name) : "Department"],
    ["Source", `<span class="prov manual">${esc(R.source || "")}</span>`],
  ])}
  ${sec("The run of them")}
  <div class="feed">${d.extra.history.map(h => `<div class="fe ${!h.done_at && h.due_on < today ? "blk" : ""}">
    <span>${esc(h.due_on)}</span>${h.done_at
      ? `Completed ${esc(h.done_at.slice(0, 10))} — ${esc(h.evidence || "")}`
      : h.due_on < today ? "Missed" : "Due"}</div>`).join("")}</div>`;
};

E.body.visit = (d) => {
  const R = d.record;
  return `
  ${sec("The visit — Manual §15")}
  ${dl([
    ["Visited", esc(R.visited_on)],
    ["By", esc(R.by_whom || "")],
    ["Project", d.project ? E.link("project", d.project.id, d.project.name) : null],
    ["Photos", R.photos],
    ["Findings", esc(R.findings || "")],
    ["Non-compliance", R.non_compliance
      ? `<span class="chip c-late">Yes — an NCR was raised</span>`
      : `<span class="chip c-done">None found</span>`],
  ])}
  ${R.non_compliance ? sec("What it raised") + (d.extra.ncr.length
    ? `<div class="card"><table class="tbl"><tbody>${d.extra.ncr.map(n => `
        <tr class="rc" data-e="case:${n.id}"><td><b>${esc(n.ref)}</b></td>
        <td>${esc(n.title)}</td><td>${stChip(n.status === "open" ? "running" : "done")}</td>
        </tr>`).join("")}</tbody></table></div>`
    : `<div class="emptyx"><b>No NCR found</b></div>`) : ""}`;
};

E.body.llr = (d) => {
  const R = d.record, x = d.extra;
  return `
  ${sec("The lesson — Manual §7.6")}
  ${dl([
    ["Lesson", `<b>${esc(R.title)}</b>`],
    ["Status", `<span class="chip ${R.status === "adopted" ? "c-done" : R.status === "ruled"
      ? "c-run" : "c-queue"}">${esc(R.status)}</span>`],
    ["Category", esc(R.category || "")],
    ["Discipline", esc(R.discipline || "")],
    ["Stage", R.stage ? `${R.stage} — ${esc(x.stage_names[R.stage] || "")}` : null],
    ["Project", d.project ? E.link("project", d.project.id, d.project.name) : "Department-wide"],
    ["What happened", esc(R.detail || "")],
    ["What it cost", esc(R.impact || "")],
    ["Raised by", `${esc(R.raised_by || "")} on ${esc(R.raised_at || "")}`],
    ["Ruling", R.ruling ? `${esc(R.ruling)} <span class="mut">— ${esc(R.ruled_by || "")}</span>`
      : `<span class="mut">not ruled on yet</span>`],
  ])}
  ${sec("Did it change anything?")}
  ${x.template
    ? `<div class="feed"><div class="fe"><span>Adopted into the stage ${R.promoted_stage} checklist</span>
       ${esc(x.template.text)}<span class="who"> — every project that reaches this stage is
       now checked for it</span></div></div>`
    : `<div class="emptyx"><b>Not adopted</b>A lessons register that does not change the
       checklist is a diary. Promote it and every future project is stopped for it.</div>`}`;
};

E.body.authority = (d) => {
  const R = d.record, x = d.extra;
  return `
  <div class="mini">
    ${miniCell("Days with them", x.age, R.status === "approved" ? "ok" : "cool")}
    ${miniCell("Station", R.stage || "—")}
    ${miniCell("Answered", R.responded_on ? "yes" : "not yet",
      R.responded_on ? "ok" : "cool")}
  </div>
  ${sec("The submission — Manual §7 / §17")}
  ${dl([
    ["Reference", `<b>${esc(R.ref)}</b>`],
    ["Authority", esc(R.authority)],
    ["Type", esc(R.kind)],
    ["Title", esc(R.title || "")],
    ["Project", d.project ? E.link("project", d.project.id, d.project.name) : null],
    ["Submitted", `${esc(R.submitted_on || "")} by ${esc(R.submitted_by || "")}`],
    ["Status", `<span class="chip ${R.status === "approved" ? "c-done"
      : R.status === "rejected" ? "c-late" : "c-wait"}">${esc(R.status)}</span>`],
    ["Responded", R.responded_on ? esc(R.responded_on) : `<span class="mut">still waiting</span>`],
    ["Observations", esc(R.observations || "")],
    ["Conditions", esc(R.conditions || "")],
  ])}
  ${x.ask ? sec("The clock this opened") + `<div class="card"><table class="tbl"><tbody>
    <tr class="rc" data-e="coordination:${x.ask.id}"><td><b>${esc(x.ask.to_lane)}</b></td>
    <td>${esc(x.ask.ask)}</td><td class="num mut">${x.ask.closed_at ? "closed" : "open"}</td>
    </tr></tbody></table></div>` : ""}`;
};

E.body.product = (d) => {
  const R = d.record, x = d.extra;
  return `
  ${sec("The catalog step", `<span class="prov ${(R.source || "").includes("Manual") ? "manual" : ""}">${esc(R.source || "")}</span>`)}
  ${dl([
    ["Step", `<b>${esc(R.step)}</b>`],
    ["Workflow", esc(R.workflow)],
    ["Stage", `${R.stage} — ${esc(BOOT.stages.find(s => s.stage === R.stage)?.name || "")}`],
    ["Sequence", R.seq],
    ["Team", esc(R.team)],
    ["Lane", R.is_external ? `<span class="chip c-ext">${esc(R.lane)}</span>` : esc(R.lane)],
    ["Duration", R.tat_days == null
      ? `<span class="mut">blank in the source document</span>` : R.tat_days + " working days"],
    ["Overall TAT", `Booklet ${esc(R.tat_booklet || "—")} / Manual ${esc(R.tat_manual || "—")}`
      + (R.tat_manual && R.tat_manual !== R.tat_booklet
        ? ` <span class="chip c-late">these disagree</span>` : "")],
    ["Marks", [R.maker && "maker", R.checker && "checker", R.rework && "rework loop",
      R.gate && "gate", R.variable && "variable"].filter(Boolean)
      .map(t => `<span class="chip c-queue">${t}</span>`).join(" ") || "—"],
  ])}
  ${sec(`Live on ${x.instances.length} project${x.instances.length === 1 ? "" : "s"}`)}
  ${x.instances.length ? `<div class="card scroll"><table class="tbl">
    <thead><tr><th>Project</th><th class="num">Base</th><th class="num">Own</th>
      <th class="num">Wait</th><th>Status</th></tr></thead>
    <tbody>${x.instances.map(t => `<tr class="rc" data-e="task:${t.id}">
      <td><b>${esc(t.pname || "")}</b></td>
      <td class="num mut">${t.baseline_days == null ? "—" : t.baseline_days}</td>
      <td class="num">${t.own_days || "—"}</td>
      <td class="num" style="color:var(--st-wait)">${t.wait_days || "—"}</td>
      <td>${stChip(t.status)}</td></tr>`).join("")}</tbody></table></div>`
    : `<div class="emptyx"><b>Not generated on any project yet</b>Initiating this stage
       creates it, with the planned dates coming from the duration above.</div>`}`;
};

/* ── per-kind action bars ───────────────────────────────────────────────── */
E.acts = {
  project: (d) => `
    <button class="btn" data-x="intake">Intake</button>
    <button class="btn" data-x="newcase">+ Case</button>
    <button class="btn" data-x="newask">+ Ask</button>
    <button class="btn" data-x="newvisit">+ Site visit</button>
    <button class="btn" data-x="newdwg">+ Drawing</button>
    <button class="btn" data-x="newtr">Transmittal</button>
    <button class="btn" data-x="authsubmit">Authority</button>
    <button class="btn" data-x="newllr">+ Lesson</button>
    <button class="btn" data-x="project-close">Close out</button>`,
  task: (d) => {
    const s = d.record.status;
    return `${s === "queued" ? `<button class="btn pri" data-act="start" data-id="${d.id}">Start</button>` : ""}
      ${s === "running" || s === "waiting" ? `<button class="btn pri" data-act="finish" data-id="${d.id}">Finish</button>` : ""}
      ${s === "done" ? `<button class="btn" data-act="revise" data-id="${d.id}">Revise</button>` : ""}
      <button class="btn" data-assign="${d.id}" data-team="${esc(d.record.team)}">Assign</button>
      <button class="btn" data-x="newllr">+ Lesson from this</button>`;
  },
  case: (d) => `
    <button class="btn pri" data-decide="${d.id}" data-ref="${esc(d.record.ref)}">Decide</button>
    <button class="btn" data-x="case-withdraw">Withdraw</button>
    <button class="btn" data-x="newllr">+ Lesson from this</button>`,
  drawing: (d) => `<button class="btn pri" data-x="revise-dwg">New revision</button>`,
  coordination: (d) => d.record.closed_at ? ""
    : `<button class="btn pri" data-x="close-ask">Close the ask</button>`,
  obligation: (d) => d.record.done_at ? ""
    : `<button class="btn pri" data-oblig="${d.id}" data-lbl="${esc(d.record.label)}">Complete</button>`,
  visit: (d) => `<button class="btn" data-x="newllr">+ Lesson from this</button>`,
  llr: (d) => `
    ${d.record.status === "open" ? `<button class="btn pri" data-x="llr-rule">Rule on it</button>` : ""}
    ${d.record.status !== "adopted" ? `<button class="btn ${d.record.status === "ruled" ? "pri" : ""}" data-x="llr-promote">Adopt into the checklist</button>` : ""}`,
  authority: (d) => d.record.status === "approved" ? ""
    : `<button class="btn pri" data-x="auth-respond">Record the response</button>`,
};

/* ── command palette — one box over every register ──────────────────────── */
E.pal = () => {
  document.querySelectorAll(".zpal").forEach(x => x.remove());
  const m = el(`<div class="zpal"><div class="zp-bd"></div>
    <div class="zp-box">
      <input class="zp-in" placeholder="Search projects, cases, steps, drawings, people, lessons…"
             autocomplete="off" spellcheck="false">
      <div class="zp-res"><div class="zp-g">Type at least two characters</div></div>
      <div class="zp-f"><span><kbd>↑</kbd><kbd>↓</kbd> move</span>
        <span><kbd>↵</kbd> open</span><span><kbd>esc</kbd> close</span>
        <span style="margin-left:auto">Every register, one box</span></div>
    </div></div>`);
  document.body.appendChild(m);
  const inp = m.querySelector(".zp-in"), res = m.querySelector(".zp-res");
  let rows = [], sel = 0, t = null;
  const close = () => m.remove();
  m.querySelector(".zp-bd").onclick = close;
  inp.focus();

  const paint = () => {
    let i = 0; rows = [];
    res.innerHTML = (E.pdata.groups || []).map(g => `<div class="zp-g">${esc(g.label)}</div>` +
      g.rows.map(r => { rows.push([g.kind, r.id]);
        return `<div class="zp-r" data-i="${i++}"><b>${esc(r.title)}</b><em>${esc(r.sub || "")}</em></div>`;
      }).join("")).join("")
      || `<div class="zp-g">Nothing matches “${esc(E.pdata.q || "")}”</div>`;
    sel = 0; mark();
    res.querySelectorAll(".zp-r").forEach(x => x.onclick = () => pick(+x.dataset.i));
  };
  const mark = () => res.querySelectorAll(".zp-r").forEach((x, i) => {
    x.classList.toggle("on", i === sel);
    if (i === sel) x.scrollIntoView({block: "nearest"});
  });
  const pick = (i) => { const r = rows[i]; if (!r) return; close(); E.open(r[0], r[1]); };

  inp.oninput = () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const q = inp.value.trim();
      if (q.length < 2) { res.innerHTML = `<div class="zp-g">Type at least two characters</div>`; rows = []; return; }
      try { E.pdata = await api("/api/search?q=" + encodeURIComponent(q)); paint(); }
      catch (x) { res.innerHTML = `<div class="zp-g">${esc(x.message)}</div>`; }
    }, 140);
  };
  m.onkeydown = ev => {
    if (ev.key === "Escape") { ev.preventDefault(); close(); }
    if (ev.key === "ArrowDown") { ev.preventDefault(); sel = Math.min(sel + 1, rows.length - 1); mark(); }
    if (ev.key === "ArrowUp") { ev.preventDefault(); sel = Math.max(sel - 1, 0); mark(); }
    if (ev.key === "Enter") { ev.preventDefault(); pick(sel); }
  };
};
E.pdata = {groups: []};

/* ── notifications — computed, never stored ─────────────────────────────── */
E.notify = async () => {
  document.querySelectorAll(".npan").forEach(x => x.remove());
  let d;
  try { d = await api("/api/notifications"); } catch (x) { return F.toast(x.message, true); }
  const p = el(`<div class="npan">
    <div class="npan-h"><b>Waiting on you</b>
      <span>${d.count} item${d.count === 1 ? "" : "s"} · ${d.bad} need action today</span></div>
    <div class="npan-b">${d.rows.length ? d.rows.map(r => `
      <div class="nrow ${r.level}" ${r.kind === "tab" ? `data-goto="${r.tab}"` : `data-e="${r.kind}:${r.id}"`}>
        <i></i><div><p>${esc(r.text)}</p><em>${esc(r.sub || "")}</em></div></div>`).join("")
      : `<div class="emptyx" style="border:0"><b>Nothing is waiting</b>No overdue steps,
         no decisions in your lane, no missed obligations.</div>`}</div>
  </div>`);
  document.body.appendChild(p);
  setTimeout(() => document.addEventListener("click", function o(ev) {
    if (!p.contains(ev.target)) { p.remove(); document.removeEventListener("click", o); }
  }), 10);
};

E.badge = async () => {
  try {
    const d = await api("/api/notifications");
    const b = document.querySelector("#bellCount");
    if (!b) return;
    b.textContent = d.count > 99 ? "99+" : d.count;
    b.hidden = !d.count;
    b.className = d.bad ? "" : "calm";
  } catch (x) { /* the bell is not worth an error state */ }
};

/* ⌘K / Ctrl+K anywhere */
document.addEventListener("keydown", ev => {
  if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") {
    ev.preventDefault(); E.pal();
  }
  if (ev.key === "/" && !/input|textarea|select/i.test(document.activeElement.tagName)) {
    ev.preventDefault(); E.pal();
  }
});

/* The entity layer is reachable from the console and from a driver script.
   Classic-script `const` does not attach to window, and being able to say
   E.open("case", 12) from devtools is worth one line. */
window.E = E; window.UI = UI; window.F = F;
