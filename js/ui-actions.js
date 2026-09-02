/* ZD PULSE — the interactive surfaces. Loaded after app.js; adds the two new
   rails and every "do something" button. Split out so app.js stays the router
   and this file is the one place a new action gets wired. */

/* ── My Queue — the personal work surface ─────────────────────────────── */
VIEWS.queue = async function () {
  const d = await api("/api/myqueue");
  const p = $("#page");
  const pn = Object.fromEntries(BOOT.projects.map(x => [x.id, x.code || x.name]));
  const me = d.me;
  const todayISO = new Date().toISOString().slice(0, 10);

  p.innerHTML = `
  <div class="actbar">
    <button class="btn pri" id="aTask">+ Task</button>
    <button class="btn" id="aCase">+ Raise a case</button>
    <button class="btn" id="aAsk">+ Ask another team</button>
    <button class="btn" id="aVisit">+ Log a site visit</button>
    <button class="btn" id="aProj">+ Add a project</button>
  </div>
  ${!me ? `<div class="note">Your login is not linked to a person record, so the personal
    list is empty — the department queues below still work.</div>` : ""}

  <div class="grid g4">
    <div class="card"><div class="k-lbl">Assigned to me</div>
      <div class="k-val sm">${d.tasks.length}</div></div>
    <div class="card"><div class="k-lbl">Unassigned in my team</div>
      <div class="k-val sm" style="color:${d.unassigned.length ? "var(--st-wait)" : "var(--good)"}">${d.unassigned.length}</div></div>
    <div class="card dark"><div class="k-lbl">Decisions waiting on us</div>
      <div class="k-val sm">${d.cases.length}</div></div>
    <div class="card"><div class="k-lbl">Obligations due</div>
      <div class="k-val sm">${d.obligations.length}</div></div>
  </div>

  <div class="sec"><h2>My tasks</h2></div>
  <div class="card">${d.tasks.length ? `<table class="tbl">
    <thead><tr><th>Prj</th><th>Step</th><th>Workflow</th><th class="num">Base</th>
      <th class="num">Own</th><th>Due</th><th>Status</th><th></th></tr></thead><tbody>
    ${d.tasks.map(t => `<tr class="rc" data-e="task:${t.id}">
      <td class="mut">${esc(pn[t.project_id] || "")}</td>
      <td><b>${esc(t.title)}</b></td><td class="mut">${esc(t.workflow || "")}</td>
      <td class="num mut">${dash(t.baseline)}</td><td class="num">${t.own || "—"}</td>
      <td class="mut">${dash(t.planned_ed)}</td><td>${stChip(t.status)}</td>
      <td style="white-space:nowrap">
        ${t.status === "queued" ? `<button class="btn sm" data-act="start" data-id="${t.id}">Start</button>` : ""}
        ${t.status !== "queued" && t.status !== "done" && t.status !== "hold" ? `<button class="btn sm" data-act="finish" data-id="${t.id}">Finish</button>` : ""}
        ${t.status === "hold" ? `<button class="btn sm" data-act="resume" data-id="${t.id}">Resume</button>`
          : t.status !== "done" && t.status !== "queued" ? `<button class="btn sm" data-hold="${t.id}">Hold</button>` : ""}
        <button class="btn sm" data-note="task:${t.id}">Note</button>
      </td></tr>`).join("")}</tbody></table>`
    : `<div class="empty">Nothing assigned to you.</div>`}</div>

  <div class="sec"><h2>Unassigned — ${esc(me ? me.team : "team")}</h2>
    <p>Pick something up, or hand it to someone.</p></div>
  <div class="card">${d.unassigned.length ? `<table class="tbl">
    <thead><tr><th>Prj</th><th>Step</th><th>Workflow</th><th class="num">Base</th><th></th></tr></thead>
    <tbody>${d.unassigned.map(t => `<tr class="rc" data-e="task:${t.id}">
      <td class="mut">${esc(pn[t.project_id] || "")}</td>
      <td><b>${esc(t.title)}</b></td><td class="mut">${esc(t.workflow || "")}</td>
      <td class="num mut">${dash(t.baseline)}</td>
      <td><button class="btn sm" data-assign="${t.id}" data-team="${esc(t.team)}">Assign</button></td>
      </tr>`).join("")}</tbody></table>`
    : `<div class="empty">Nothing unassigned.</div>`}</div>

  <div class="sec"><h2>Decisions waiting on Arch &amp; Design</h2>
    <p>§9 of the review: who raised it, the TAT, the due date, the priority, and the
      days remaining or overdue.</p></div>
  <div class="card scroll">${d.cases.length ? `<table class="tbl">
    <thead><tr><th>Ref</th><th style="width:74px">Priority</th><th>Project</th><th>Title</th>
      <th>Raised by</th><th class="num">TAT</th><th>Due</th><th class="num">Left</th>
      <th class="num">Value</th><th></th></tr></thead>
    <tbody>${d.cases.map(c => {
      const left = c.due_on
        ? Math.round((new Date(c.due_on) - new Date()) / 86400000) : null;
      return `<tr class="rc" data-e="case:${c.id}"><td><b>${esc(c.ref)}</b></td>
      <td>${priChip(c.priority)}</td>
      <td class="mut">${esc(c.pname || "")}</td><td>${esc(c.title)}</td>
      <td class="mut">${esc(c.raised_by || "")}</td>
      <td class="num mut">${dash(c.tat_days)}</td>
      <td class="mut">${dash(c.due_on)}</td>
      <td class="num"><b style="color:${left != null && left < 0 ? "var(--bad)"
        : left != null && left <= 1 ? "var(--st-wait)" : "inherit"}">${
        left == null ? "—" : left < 0 ? Math.abs(left) + "d over" : left + "d"}</b></td>
      <td class="num mut">${pkr(c.value_pkr)}</td>
      <td><button class="btn sm pri" data-decide="${c.id}" data-ref="${esc(c.ref)}">Decide</button></td>
      </tr>`;}).join("")}</tbody></table>`
    : `<div class="empty">Nothing waiting.</div>`}</div>

  <div class="sec"><h2>Obligations due</h2></div>
  <div class="card">${d.obligations.length ? `<table class="tbl">
    <thead><tr><th>Obligation</th><th>Project</th><th>Due</th><th></th></tr></thead>
    <tbody>${d.obligations.slice(0, 12).map(o => `<tr class="rc" data-e="obligation:${o.id}">
      <td><b>${esc(o.label)}</b></td>
      <td class="mut">${esc(o.pname || "Department")}</td>
      <td style="${o.due_on < todayISO ? "color:var(--bad);font-weight:700" : "color:var(--ink-2)"}">${esc(o.due_on)}</td>
      <td><button class="btn sm" data-oblig="${o.id}" data-lbl="${esc(o.label)}">Complete</button></td>
      </tr>`).join("")}</tbody></table>`
    : `<div class="empty">Nothing due.</div>`}</div>`;

  $("#aTask").onclick = () => UI.newTask();
  $("#aCase").onclick = () => UI.newCase();
  $("#aAsk").onclick = () => UI.newAsk();
  $("#aVisit").onclick = () => UI.newVisit();
  $("#aProj").onclick = () => UI.newProject();
  UI.bind(p);
};

/* ── Drawings & Issuance — Manual §5 ──────────────────────────────────── */
VIEWS.drawings = async function () {
  const pid = CACHE.pid || BOOT.projects.find(x => !x.is_bau).id;
  CACHE.pid = pid;
  const d = await api("/api/drawings?project=" + pid);
  const p = $("#page");
  p.innerHTML = `
  <div class="note">The register tracks drawings and revisions; files stay on the drive
    behind a link. <b>The transmittal is the contractual fact</b> — Manual §5 ties IFC
    issuance to construction milestones, and issuing to an outside party starts their
    clock in the coordination ledger.</div>
  <div class="actbar">
    <select class="btn" id="dsel" style="padding:8px 12px">
      ${BOOT.projects.filter(x => !x.is_bau).map(x =>
        `<option value="${x.id}" ${x.id === pid ? "selected" : ""}>${esc(x.name)}</option>`).join("")}
    </select>
    <button class="btn pri" id="aDwg">+ Register a drawing</button>
    <button class="btn" id="aTr">Issue a transmittal</button>
  </div>

  <div class="grid g4">
    <div class="card"><div class="k-lbl">Sheets on the register</div>
      <div class="k-val sm">${d.drawings.length}</div></div>
    <div class="card"><div class="k-lbl">Issued for construction</div>
      <div class="k-val sm" style="color:var(--good)">${d.drawings.filter(x => x.status === "IFC").length}</div>
      <div class="k-note">A sheet not on a transmittal has no contractual standing.</div></div>
    <div class="card"><div class="k-lbl">Transmittals</div>
      <div class="k-val sm">${d.transmittals.length}</div></div>
    <div class="card dark"><div class="k-lbl">Sheet-issuances recorded</div>
      <div class="k-val sm">${d.transmittals.reduce((a, t) => a + (t.sheets || []).length, 0)}</div>
      <div class="k-note">Which sheet, at which revision, to whom, when.</div></div>
  </div>

  <div class="sec"><h2>Transmittals</h2>
    <p>Every formal issuance, with the sheet list attached. Click one to see what was in it.</p></div>
  <div class="card">${d.transmittals.length ? `<table class="tbl">
    <thead><tr><th>Ref</th><th>Phase</th><th>Issued to</th><th class="num">Sheets</th>
      <th>When</th><th>By</th></tr></thead><tbody>
    ${d.transmittals.map(t => `<tr class="rc" data-e="transmittal:${t.id}">
      <td><b>${esc(t.ref)}</b></td>
      <td><span class="chip c-run">${esc(t.phase)}</span></td>
      <td>${(t.issued_to || "").split(",").map(x => `<span class="chip c-ext">${esc(x.trim())}</span>`).join(" ")}</td>
      <td class="num"><b>${(t.sheets || []).length || dash(t.drawing_count)}</b></td>
      <td class="mut">${esc((t.issued_at || "").slice(0, 10))}</td>
      <td class="mut">${esc(t.issued_by || "")}</td></tr>`).join("")}
    </tbody></table>` : `<div class="emptyx"><b>Nothing issued yet</b>Manual §5 ties IFC
      issuance to construction milestones. Until a transmittal exists, nothing has been
      formally handed over.</div>`}</div>

  <div class="sec"><h2>Drawing register</h2>
    <p>Click a sheet for its revision history and every transmittal it went out on.</p></div>
  ${["Architecture", "Structure", "MEP", "Creative"].map(disc => {
    const rows = d.drawings.filter(x => x.discipline === disc);
    if (!rows.length) return "";
    return `<div class="card" style="margin-bottom:12px">
      <h3>${esc(disc)}</h3><div class="sub">${rows.length} sheets ·
        ${rows.filter(x => x.status === "IFC").length} issued for construction</div>
      <table class="tbl"><thead><tr><th>Number</th><th>Title</th><th>Rev</th>
        <th class="num">Revs</th><th>Status</th><th>Stage</th><th>File</th></tr></thead>
      <tbody>${rows.map(x => `<tr class="rc" data-e="drawing:${x.id}">
        <td><b>${esc(x.number)}</b></td><td>${esc(x.title)}</td>
        <td><span class="chip c-queue">${esc(x.revision)}</span></td>
        <td class="num mut">${(x.revs || []).length || "—"}</td>
        <td><span class="chip ${x.status === "IFC" ? "c-done" : "c-run"}">${esc(x.status)}</span></td>
        <td class="mut">${dash(x.stage)}</td>
        <td class="mut">${x.link ? `<a href="${esc(x.link)}" target="_blank" rel="noopener"
          onclick="event.stopPropagation()">open ↗</a>` : "—"}</td>
        </tr>`).join("")}</tbody></table></div>`;
  }).join("") || `<div class="emptyx"><b>No drawings registered</b>Register the sheets and
    the transmittal can carry a sheet list instead of a count.</div>`}`;

  $("#dsel").onchange = e => { CACHE.pid = +e.target.value; render(); };
  $("#aDwg").onclick = () => UI.newDrawing(pid);
  $("#aTr").onclick = () => UI.newTransmittal(pid);
};

/* ── the action library ───────────────────────────────────────────────── */
const UI = {};

UI.newProject = () => F.modal("Add a project",
  "Manual §3 — creates all 13 stations and opens the intake.",
  F.field("name", "Project name", {placeholder: "Zameen Sapphire"}) +
  F.field("code", "Code", {placeholder: "ZS2", hint: "Used on refs — MAR-ZS2-104"}) +
  F.field("kind", "Type", {options: ["Residential", "Mixed Use", "Commercial"]}) +
  F.field("city", "City", {options: ["Lahore", "Islamabad", "Multan", "Karachi"]}),
  async d => {
    const r = await F.act("/api/project/create", d);
    CACHE.pid = r.id;
    BOOT = await api("/api/bootstrap");
    refresh("Project opened — fill the intake to unlock Stage 3");
  }, "Open project");

UI.intake = async (pid) => {
  const d = await api("/api/intake/" + pid);
  F.modal("Project intake",
    "Manual §3.1 — each field has a named owner. Stage 3 will not initiate until all "
    + "seven are filled, which is what makes “who is holding up the start” a field with "
    + "a name on it.",
    d.fields.map(f => F.field(f.key, f.label,
      {value: f.value, hint: "Source: " + f.source, placeholder: "—"})).join(""),
    async v => { await F.act("/api/intake/save", {...v, project_id: pid});
      refresh("Intake saved"); }, "Save intake");
};

UI.newTask = (pid) => F.modal("New task",
  "Not everything the department does is in the booklet.",
  F.field("project_id", "Project", {options: projOpts(), value: pid || CACHE.pid || ""}) +
  F.field("title", "What needs doing", {placeholder: "Client presentation rehearsal"}) +
  F.field("team", "Team", {options: BOOT.teams}) +
  F.field("baseline_days", "Baseline (working days)", {type: "number", value: 2}) +
  F.field("note", "Note", {type: "textarea", rows: 2}),
  async d => { await F.act("/api/task/create", d); refresh("Task created"); }, "Create");

UI.assign = (tid, team) => F.modal("Assign", `Only ${team} can hold this step.`,
  F.field("person_id", "Person", {options: peopleOpts(team)}),
  async d => { await F.act("/api/task/assign", {...d, id: tid}); refresh("Assigned"); },
  "Assign");

UI.newCase = (pid, typ) => F.modal("Raise a case",
  "One engine, ten routes. The approval chain comes from the manual, not from memory — "
  + "and the source is printed on the case.",
  F.field("type", "Type", {value: typ || "", options: Object.entries(BOOT.routes).map(
    ([k, v]) => [k, `${k} — ${v.label}  (${v.source})`])}) +
  F.field("project_id", "Project", {options: projOpts(), value: pid || CACHE.pid || ""}) +
  F.field("title", "Title", {placeholder: "Façade stone cladding"}) +
  F.field("value_pkr", "Value (PKR)", {placeholder: "2100000",
    hint: `≥ ${n0(BOOT.thresholds.cpc)} routes to CPC · ≥ ${n0(BOOT.thresholds.ceo)} to the CEO Office`}) +
  F.field("note", "Note", {type: "textarea", rows: 2}),
  async d => { const r = await F.act("/api/case/create", d);
    refresh(`${r.ref} raised${r.gate ? ` — ${r.gate} approval required` : ""}`); }, "Raise");

UI.decide = (cid, ref) => F.modal(`Decide · ${ref}`,
  "A review that can only say yes is not a review. A return or a rejection needs a reason.",
  F.field("outcome", "Decision", {options: [
    ["approve", "Approve — pass to the next lane"],
    ["return", "Return — send back one lane"],
    ["reject", "Reject — close the case"]]}) +
  F.field("reason", "Reason", {type: "textarea", rows: 3,
    hint: "Required for a return or a rejection. It goes in the ledger."}),
  async d => { await F.act("/api/case/decide", {...d, id: cid});
    refresh("Decision recorded"); }, "Record decision");

UI.newAsk = (pid) => F.modal("Ask another team",
  "This is what currently happens in email. Here it has a clock and a name against it.",
  F.field("project_id", "Project", {options: projOpts(), value: pid || CACHE.pid || ""}) +
  F.field("to_lane", "Waiting on", {options: ["PM", "Supply Chain", "Finance", "QA/QC",
    "Legal", "Authority", "Third Party Vendor", "Zameen Studios", "Bayut", "Stakeholders",
    "Architecture", "Structure", "MEP", "Creative"]}) +
  F.field("ask", "What you need", {placeholder: "Confirm basement start date for IFC-I"}) +
  F.field("sla_days", "TAT (working days)", {type: "number", value: 3,
    hint: "§21 of the review: a cross-team timeline is a turnaround, so it is TAT."}) +
  F.field("priority", "Priority", {options: priOpts(), value: BOOT.priority_default}) +
  F.field("stage", "Stage", {type: "number", value: 11}),
  async d => { await F.act("/api/coordination/create", d);
    refresh("Ask logged — the clock is running"); }, "Raise ask");

UI.newVisit = (pid) => F.modal("Log a site visit",
  "Manual §15 — one visit per project per month. Logging it closes the obligation and "
  + "feeds the Monthly Design Compliance Report.",
  F.field("project_id", "Project", {options: projOpts(), value: pid || CACHE.pid || ""}) +
  F.field("visited_on", "Date", {type: "date", value: new Date().toISOString().slice(0, 10)}) +
  F.field("findings", "Findings", {type: "textarea", rows: 4,
    placeholder: "What was inspected and what was found"}) +
  F.field("non_compliance", "", {type: "checkbox",
    placeholder: "Non-compliance against approved IFC / MAR"}) +
  F.field("photos", "Photos taken", {type: "number", value: 0}),
  async d => { const r = await F.act("/api/visit/create", d);
    refresh(r.non_compliance ? "Visit logged — non-compliance raised" : "Visit logged"); },
  "Log visit");

UI.newDrawing = (pid) => F.modal("Register a drawing", "The register, not the file.",
  F.field("number", "Drawing number", {placeholder: "A-101"}) +
  F.field("title", "Title", {placeholder: "Ground floor plan"}) +
  F.field("discipline", "Discipline", {options: BOOT.teams}) +
  F.field("revision", "Revision", {value: "A"}) +
  F.field("status", "Status", {options: ["draft", "for review", "IFC", "superseded"]}) +
  F.field("link", "Drive link", {placeholder: "https://…",
    hint: "We link, we do not store. File storage is a different product."}),
  async d => { await F.act("/api/drawing/create", {...d, project_id: pid});
    refresh("Drawing registered"); }, "Register");

UI.newTransmittal = async (pid) => {
  const reg = await api("/api/drawings?project=" + pid);
  const byDisc = {};
  reg.drawings.forEach(x => (byDisc[x.discipline] = byDisc[x.discipline] || []).push(x));
  const picker = Object.entries(byDisc).map(([disc, rows]) => `
    <div class="zm-fld"><label>${esc(disc)} — ${rows.length} sheets
      <button type="button" class="btn sm" data-all="${esc(disc)}"
        style="float:right;margin-top:-4px">Select all</button></label>
      ${rows.map(x => `<label class="tick"><input type="checkbox" name="dwg_${x.id}"
        data-disc="${esc(disc)}"><span><b>${esc(x.number)} · ${esc(x.title)}</b>
        <em>Rev ${esc(x.revision)} · ${esc(x.status)}</em></span></label>`).join("")}
    </div>`).join("");

  const m = F.modal("Issue a transmittal",
    "Manual §5 — IFC Phase I before basement, Phase II by ground-floor slab. §4.1 blocks "
    + "issuance until the stage checklist is signed. Pick the sheets: the list, with each "
    + "sheet's revision, is the contractual record — a count is not.",
    F.field("phase", "Phase", {options: ["Tender", "Authority", "IFC Phase I",
      "IFC Phase II", "IFC Phase III", "Shop drawing", "As-built"]}) +
    F.field("issued_to", "Issued to", {value: "PM, QA/QC, Contractor",
      hint: "Comma separated. Each outside party gets a clock in the coordination ledger."}) +
    (reg.drawings.length ? picker : `<div class="note">No sheets on the register for this
      project yet. Register a drawing first, or issue anyway and the refusal will offer an
      override.</div>`) +
    F.field("note", "Note", {type: "textarea", rows: 2}),
    async v => {
      const ids = Object.keys(v).filter(k => k.startsWith("dwg_") && v[k])
                        .map(k => k.slice(4));
      const r = await F.act("/api/transmittal/issue",
        {...v, project_id: pid, drawing_ids: ids.join(",")});
      refresh(`${r.ref} issued — ${r.sheets} sheets`);
    }, "Issue");

  m.querySelectorAll("[data-all]").forEach(b => b.onclick = () => {
    const on = m.querySelectorAll(`[data-disc="${b.dataset.all}"]`);
    const flip = ![...on].every(x => x.checked);
    on.forEach(x => { x.checked = flip; x.closest(".tick").classList.toggle("on", flip); });
  });
  m.querySelectorAll('[name^="dwg_"]').forEach(cb => cb.onchange = () =>
    cb.closest(".tick").classList.toggle("on", cb.checked));
};

UI.checklist = async (pid, stage) => {
  const d = await api(`/api/checklist/${pid}/${stage}`);
  const cl = d.checklist, items = d.items;
  const body = `
    ${items.length ? `<div class="note" style="margin-bottom:12px">
      <b>${items.length} checks, stamped from the §4.2 template.</b> The Manual makes
      sign-off mandatory before any drawing issuance and then marks the annexure itself
      “(to be added)” — so it is authored in-system, once, per stage.
      ${items.filter(i => (i.source || "").startsWith("Lessons")).length
        ? `<b>${items.filter(i => (i.source || "").startsWith("Lessons")).length} of these
           came from a lesson learned</b> on an earlier project.` : ""}
      Anything added below applies to this checklist only — to change it for every future
      project, adopt it on the Lessons &amp; Standards rail.</div>`
      : `<div class="note" style="margin-bottom:12px">No template items for this stage yet.
      Author the checks here, then promote them to the template so the next project
      carries them.</div>`}
    <div id="ticks">${items.map(i => `
      <label class="tick ${i.done ? "on" : ""}">
        <input type="checkbox" data-tick="${i.id}" ${i.done ? "checked" : ""}>
        <span><b>${esc(i.text)}</b><em>${esc(i.source || "")}${i.done_by ? ` · ${esc(i.done_by)}` : ""}</em></span>
      </label>`).join("")}</div>
    ${F.field("text", "Add a check", {placeholder: "Column grid coordinated with Structure"})}
    <button type="button" class="btn sm" id="addChk">+ Add check</button>
    ${cl.signed_at ? `<div class="note" style="margin-top:12px">Signed by
      <b>${esc(cl.signed_by)}</b> on ${esc((cl.signed_at || "").slice(0, 10))}.</div>` : ""}`;

  const m = F.modal(`Stage ${stage} checklist`,
    "Manual §4.1 — sign-off is mandatory before any drawing issuance.",
    body,
    async () => { await F.act("/api/checklist/sign", {id: cl.id});
      refresh("Checklist signed"); },
    cl.signed_at ? "Already signed" : "Sign off");

  m.querySelectorAll("[data-tick]").forEach(cb => cb.onchange = async () => {
    await F.act("/api/checklist/tick", {id: +cb.dataset.tick});
    cb.closest(".tick").classList.toggle("on", cb.checked);
  });
  m.querySelector("#addChk").onclick = async () => {
    const inp = m.querySelector('[name="text"]');
    if (!inp.value.trim()) return;
    await F.act("/api/checklist/add", {checklist_id: cl.id, text: inp.value.trim()});
    m.remove(); UI.checklist(pid, stage);
  };
};

UI.oblig = (id, label) => F.modal("Complete obligation", label,
  F.field("evidence", "What was done", {type: "textarea", rows: 3,
    placeholder: "Held 27 Aug, all four leads present, actions minuted",
    hint: "An obligation ticked with no evidence is not evidence."}),
  async d => { await F.act("/api/obligation/complete", {...d, id});
    refresh("Obligation completed"); }, "Complete");

UI.note = (key) => {
  const [entity, id] = key.split(":");
  F.modal("Add a note", "The thing that currently lives in WhatsApp.",
    F.field("body", "Note", {type: "textarea", rows: 3}),
    async d => { await F.act("/api/note/add", {...d, entity, entity_id: +id});
      F.toast("Note added"); }, "Add");
};

UI.stage = (pid, stage, status) => {
  if (status === "not_started") {
    return F.modal(`Initiate stage ${stage}`,
      "Generates this stage's tasks straight from the catalog, so planned dates come "
      + "from the department's own published TAT rather than from whoever typed them.",
      `<div class="note">Gates checked: intake complete (stage 3), previous stage
        signed off. A refusal can be overridden with a stated reason — that reason
        goes in the ledger.</div>`,
      async d => { const r = await F.act("/api/stage/initiate", {...d, project_id: pid, stage});
        refresh(`Stage ${stage} initiated — ${r.tasks} tasks created`); }, "Initiate");
  }
  return F.modal(`Sign off stage ${stage}`,
    "Manual §4.1 — the stage checklist must be signed and every step closed.",
    `<div class="note">Gates checked: checklist signed, no open steps.</div>`,
    async d => { await F.act("/api/stage/signoff", {...d, project_id: pid, stage});
      refresh(`Stage ${stage} signed off`); }, "Sign off");
};

/* one delegated binder for every list button on every surface */
UI.bind = (root) => {
  root.querySelectorAll("[data-act]").forEach(b => b.onclick = async () => {
    b.disabled = true;
    try {
      await api("/api/task/" + b.dataset.act,
                {method: "POST", body: JSON.stringify({id: +b.dataset.id})});
      refresh();
    } catch (x) { F.toast(x.message, true); b.disabled = false; }
  });
  root.querySelectorAll("[data-assign]").forEach(b =>
    b.onclick = () => UI.assign(+b.dataset.assign, b.dataset.team));
  root.querySelectorAll("[data-decide]").forEach(b =>
    b.onclick = () => UI.decide(+b.dataset.decide, b.dataset.ref));
  root.querySelectorAll("[data-oblig]").forEach(b =>
    b.onclick = () => UI.oblig(+b.dataset.oblig, b.dataset.lbl));
  root.querySelectorAll("[data-note]").forEach(b =>
    b.onclick = () => UI.note(b.dataset.note));
  root.querySelectorAll("[data-intake]").forEach(b =>
    b.onclick = () => UI.intake(+b.dataset.intake));
  root.querySelectorAll("[data-stage]").forEach(b => {
    const [pid, st, status] = b.dataset.stage.split(":");
    b.onclick = () => UI.stage(+pid, +st, status);
  });
  root.querySelectorAll("[data-chk]").forEach(b => {
    const [pid, st] = b.dataset.chk.split(":");
    b.onclick = () => UI.checklist(+pid, +st);
  });
  root.querySelectorAll("[data-hold]").forEach(b => b.onclick = (ev) => {
    ev.stopPropagation(); UI.hold(+b.dataset.hold);
  });
  root.querySelectorAll("[data-close]").forEach(b => b.onclick = async (ev) => {
    ev.stopPropagation(); b.disabled = true;
    try { await F.act("/api/coordination/close", {id: +b.dataset.close});
      refresh("Ask closed"); }
    catch (x) { F.toast(x.message, true); b.disabled = false; }
  });
  /* a button inside a clickable row must not also open the row */
  root.querySelectorAll("tr.rc .btn, tr.rc input, tr.rc a").forEach(x =>
    x.addEventListener("click", ev => ev.stopPropagation()));
};


/* ══════════════════════════════════════════════════════════════════════════
   THE REGISTERS — the Manual sections that had no surface at all
   ══════════════════════════════════════════════════════════════════════════ */

/* ── Site & Compliance — Manual §15, §16, §17 ──────────────────────────── */
VIEWS.site = async function () {
  const d = await api("/api/site");
  const p = $("#page");
  const k = d.kpi;
  p.innerHTML = `
  <div class="actbar">
    <button class="btn pri" id="sVisit">+ Log a site visit</button>
    <button class="btn" id="sAuth">+ Authority submission</button>
    <button class="btn" id="sNCR">+ Raise an NCR</button>
  </div>
  <div class="note">Three Manual sections that had no surface at all before this:
    <b>§15</b> the monthly visit, <b>§16</b> QA/QC coordination, <b>§17</b> regulatory
    inspection support. The connection is the point — a visit that finds non-compliance
    <b>raises an NCR automatically</b>, the NCR runs a route with a clock on it, and the
    lesson that comes out of it can be adopted into the stage checklist.</div>

  <div class="grid g4">
    <div class="card"><div class="k-lbl">Visits logged</div>
      <div class="k-val sm">${k.visits}</div></div>
    <div class="card"><div class="k-lbl">Found non-compliance</div>
      <div class="k-val sm" style="color:${k.non_compliance ? "var(--bad)" : "var(--good)"}">${k.non_compliance}</div>
      <div class="k-note">Each one raised an NCR on the §16 route.</div></div>
    <div class="card"><div class="k-lbl">NCRs open</div>
      <div class="k-val sm" style="color:${k.ncr_open ? "var(--bad)" : "var(--good)"}">${k.ncr_open}</div></div>
    <div class="card dark"><div class="k-lbl">Days sitting with the Authority</div>
      <div class="k-val sm">${n0(Math.round(k.authority_days))}</div>
      <div class="k-note">${k.authority_open} submissions and inspections open. The longest
        single wait the department carries, and nobody totals it today.</div></div>
  </div>

  <div class="sec"><h2>Non-conformance — Manual §16</h2>
    <p>Raised on site against approved IFC. Click one for the route and the clock.</p></div>
  <div class="card">${d.ncr.length ? `<table class="tbl">
    <thead><tr><th>Ref</th><th>Project</th><th>What was found</th><th class="num">Age</th>
      <th>Status</th></tr></thead><tbody>
    ${d.ncr.map(x => `<tr class="rc" data-e="case:${x.id}">
      <td><b>${esc(x.ref)}</b></td><td class="mut">${esc(x.pname || "")}</td>
      <td>${esc(x.title)}</td>
      <td class="num"><b>${x.age}d</b></td>
      <td>${stChip(x.status === "open" ? "running" : "done")}</td></tr>`).join("")}
    </tbody></table>` : `<div class="emptyx"><b>No NCRs</b>Either the work is clean or the
      visits are not being logged.</div>`}</div>

  <div class="sec"><h2>The authority file — Manual §7 / §17</h2>
    <p>Submission, the wait, the observations, and the conditions attached to an approval.</p></div>
  <div class="card">${d.authority.length ? `<table class="tbl">
    <thead><tr><th>Ref</th><th>Project</th><th>Authority</th><th>Type</th><th>Submitted</th>
      <th class="num">Days</th><th>Status</th></tr></thead><tbody>
    ${d.authority.map(a => `<tr class="rc" data-e="authority:${a.id}">
      <td><b>${esc(a.ref)}</b></td><td class="mut">${esc(a.pname || "")}</td>
      <td>${esc(a.authority)}</td><td class="mut">${esc(a.kind)}</td>
      <td class="mut">${esc(a.submitted_on || "")}</td>
      <td class="num"><b style="color:${a.status === "approved" ? "inherit" : "var(--st-wait)"}">${a.age}d</b></td>
      <td><span class="chip ${a.status === "approved" ? "c-done" : a.status === "rejected"
        ? "c-late" : "c-wait"}">${esc(a.status)}</span></td></tr>`).join("")}
    </tbody></table>` : `<div class="emptyx"><b>Nothing on the authority file</b></div>`}</div>

  <div class="sec"><h2>Site visits — Manual §15</h2>
    <p>One per project per month. Logging one closes the obligation.</p></div>
  <div class="card scroll">${d.visits.length ? `<table class="tbl">
    <thead><tr><th>Date</th><th>Project</th><th>By</th><th>Findings</th>
      <th class="num">Photos</th><th></th></tr></thead><tbody>
    ${d.visits.map(v => `<tr class="rc" data-e="visit:${v.id}">
      <td class="mut">${esc(v.visited_on)}</td>
      <td class="mut">${esc(v.pcode || v.pname || "")}</td>
      <td>${esc(v.by_whom || "")}</td>
      <td style="max-width:420px">${esc((v.findings || "").slice(0, 130))}${(v.findings || "").length > 130 ? "…" : ""}</td>
      <td class="num mut">${v.photos || 0}</td>
      <td>${v.non_compliance ? `<span class="chip c-late">NCR</span>`
        : `<span class="chip c-done">clean</span>`}</td></tr>`).join("")}
    </tbody></table>` : `<div class="emptyx"><b>No visits logged</b>§15 requires one per
      project per month, and the obligation register is already counting the misses.</div>`}</div>`;

  $("#sVisit").onclick = () => UI.newVisit();
  $("#sAuth").onclick = () => UI.authSubmit();
  $("#sNCR").onclick = () => UI.newCase(null, "NCR");
  UI.bind(p);
};

/* ── Lessons & Standards — Manual §7.6 and §4.2 ────────────────────────── */
VIEWS.llr = async function () {
  const d = await api("/api/llr");
  const p = $("#page");
  const st = CACHE.tplStage || (CACHE.tplStage = 3);
  const tpl = d.template.filter(t => t.stage === st);
  const s = d.summary;

  p.innerHTML = `
  <div class="actbar">
    <button class="btn pri" id="lNew">+ Raise a lesson</button>
    <button class="btn" id="tNewChk">+ Add a check to stage ${st}</button>
  </div>
  <div class="note"><b>This is the loop, not a library.</b> Manual §4.2 lists an internal
    checklist annexure and then says “(to be added)” — it does not exist in any document
    supplied, so a mandatory gate was a signature against undefined content. The annexure
    is authored here, once, per stage. A lesson raised under §7.6, once ruled on, is
    <b>adopted into that template</b> — and lands immediately on every open checklist for
    the stage. That is the difference between a lessons register and a diary: this one
    changes what the next project is stopped for.
    <br><br>PM Manual §8.3 defines a competing lessons process and neither document
    references the other. Recorded on the entry, not silently resolved.</div>

  <div class="grid g4">
    <div class="card"><div class="k-lbl">Lessons open</div>
      <div class="k-val sm">${s.open || 0}</div>
      <div class="k-note">Raised, not yet ruled on.</div></div>
    <div class="card"><div class="k-lbl">Ruled</div>
      <div class="k-val sm">${s.ruled || 0}</div>
      <div class="k-note">Decided, not yet adopted into a checklist.</div></div>
    <div class="card dark"><div class="k-lbl">Adopted into the standard</div>
      <div class="k-val sm">${s.adopted || 0}</div>
      <div class="k-note">Every future project is now checked for these.</div></div>
    <div class="card"><div class="k-lbl">Template items</div>
      <div class="k-val sm">${d.template.length}<span class="u">/ 14 stages</span></div>
      <div class="k-note"><b>${d.from_lessons}</b> came from a lesson learned.</div></div>
  </div>

  <div class="sec"><h2>The register — Manual §7.6</h2>
    <p>Click a lesson to rule on it, or to adopt it into a stage checklist.</p></div>
  <div class="card scroll"><table class="tbl">
    <thead><tr><th>Lesson</th><th>Project</th><th>Stage</th><th>Category</th>
      <th>Cost of it</th><th>Status</th><th>Adopted at</th></tr></thead><tbody>
    ${d.rows.map(l => `<tr class="rc" data-e="llr:${l.id}">
      <td><b>${esc(l.title)}</b></td>
      <td class="mut">${esc(l.pname || "Department")}</td>
      <td class="mut">${dash(l.stage)}</td>
      <td class="mut">${esc(l.category || "")}</td>
      <td class="mut" style="max-width:230px">${esc(l.impact || "")}</td>
      <td><span class="chip ${l.status === "adopted" ? "c-done" : l.status === "ruled"
        ? "c-run" : "c-queue"}">${esc(l.status)}</span></td>
      <td class="mut">${l.promoted_stage ? "stage " + l.promoted_stage
        : `<span class="mut">—</span>`}</td></tr>`).join("")}
    </tbody></table></div>

  <div class="sec"><h2>The §4.2 annexure, authored</h2>
    <p>What every project is checked for at each station. Edit it and the next stage
      initiated anywhere carries the change.</p></div>
  <div class="pills">${BOOT.stages.map(x =>
    `<button class="pill ${x.stage === st ? "on" : ""}" data-ts="${x.stage}">${x.stage} ·
      ${esc(x.name)}</button>`).join("")}</div>
  <div class="card">${tpl.length ? `<table class="tbl">
    <thead><tr><th style="width:26px">#</th><th>Check</th><th>Source</th><th></th></tr></thead>
    <tbody>${tpl.map(t => `<tr>
      <td class="mut">${t.seq}</td>
      <td><b>${esc(t.text)}</b></td>
      <td><span class="prov ${t.llr_id ? "manual" : ""}">${esc(t.source || "")}</span></td>
      <td><button class="btn sm" data-retire="${t.id}">Retire</button></td>
      </tr>`).join("")}</tbody></table>`
    : `<div class="emptyx"><b>No checks defined for stage ${st}</b>A stage with no checks
       can be signed off against nothing.</div>`}</div>`;

  $("#lNew").onclick = () => UI.newLLR();
  $("#tNewChk").onclick = () => UI.templateAdd(st);
  p.querySelectorAll("[data-ts]").forEach(b => b.onclick = () => {
    CACHE.tplStage = +b.dataset.ts; render();
  });
  p.querySelectorAll("[data-retire]").forEach(b => b.onclick = () =>
    UI.templateRetire(+b.dataset.retire));
  UI.bind(p);
};


/* ══════════════════════════════════════════════════════════════════════════
   THE NEW MODALS
   ══════════════════════════════════════════════════════════════════════════ */

UI.newDoc = (entity, id, pid) => F.modal("Attach a document",
  "We link, we do not store — they already have a drive. What they do not have is a "
  + "record of which file is current and what it belongs to.",
  F.field("title", "What is it", {placeholder: "Geotech report — final"}) +
  F.field("kind", "Kind", {options: ["Reference", "Report", "Drawing set", "Letter",
    "Minutes", "Data sheet", "Photo set", "Certificate", "Contract"]}) +
  F.field("link", "Link", {placeholder: "https://drive.zameen.com/…"}) +
  F.field("revision", "Revision", {value: "A"}),
  async d => {
    await F.act("/api/document/add", {...d, entity, entity_id: id, project_id: pid || ""});
    F.toast("Attached");
    if (E.cur) E.open(E.cur.kind, E.cur.id, {back: true});
  }, "Attach");

UI.reviseDrawing = (R, then) => F.modal(`New revision · ${R.number}`,
  "The register keeps every revision. “Which drawing is the contractor actually building "
  + "from” is the question it exists to answer, and one mutable row cannot answer it.",
  F.field("revision", "New revision", {value: String.fromCharCode(
    (R.revision || "A").charCodeAt((R.revision || "A").length - 1) + 1)}) +
  F.field("status", "Status", {options: ["for review", "IFC", "draft", "superseded"],
    value: "for review"}) +
  F.field("note", "Why", {type: "textarea", rows: 3,
    placeholder: "Ceiling void raised to 400mm after MEP coordination",
    hint: "Required. A revision with no reason is not traceable."}) +
  F.field("link", "Link to the new file", {value: R.link || ""}),
  async d => { await F.act("/api/drawing/revise", {...d, id: R.id});
    F.toast("Revision recorded"); if (then) then(); CACHE.matrix = null; }, "Record revision");

UI.authSubmit = (pid) => F.modal("Authority submission",
  "Manual §7 / §17. This opens the clock on the Authority — the longest single wait the "
  + "department carries.",
  F.field("project_id", "Project", {options: projOpts(), value: pid || CACHE.pid || ""}) +
  F.field("authority", "Authority", {options: ["LDA", "CDA", "TMA", "WASA", "LESCO",
    "Fire Department", "Environmental Protection Agency", "Civil Aviation"]}) +
  F.field("kind", "Type", {options: [["submission", "Submission — building plan / drawings"],
    ["inspection", "Inspection — site visit by the authority"],
    ["noc", "NOC — no-objection certificate"]]}) +
  F.field("title", "What was submitted", {placeholder: "Building plan approval — full set"}) +
  F.field("stage", "Stage", {type: "number", value: 7}) +
  F.field("sla_days", "Expected response (working days)", {type: "number", value: 21}) +
  F.field("note", "Note", {type: "textarea", rows: 2}),
  async d => { const r = await F.act("/api/authority/submit", d);
    refresh(`${r.ref} logged — the clock on ${d.authority} is running`); }, "Log submission");

UI.authRespond = (R, then) => F.modal(`Response · ${R.ref}`,
  "An approval with conditions is not an approval until the conditions are written down. "
  + "Observations come back as a task on the design team.",
  F.field("status", "Outcome", {options: [
    ["observations", "Observations — they want changes"],
    ["approved", "Approved"],
    ["rejected", "Rejected"]]}) +
  F.field("responded_on", "Date", {type: "date",
    value: new Date().toISOString().slice(0, 10)}) +
  F.field("observations", "What they said", {type: "textarea", rows: 4,
    hint: "Required for observations or a rejection. An unrecorded observation cannot be "
        + "answered or counted."}) +
  F.field("conditions", "Conditions attached to an approval", {type: "textarea", rows: 2}),
  async d => { await F.act("/api/authority/respond", {...d, id: R.id});
    F.toast("Response recorded"); if (then) then(); CACHE.matrix = null; }, "Record response");

UI.newLLR = (pid, originEntity, originId) => F.modal("Raise a lesson learned",
  "Manual §7.6. The register only earns its place if a lesson can change the checklist — "
  + "which is what happens when this is ruled on and adopted.",
  F.field("project_id", "Project", {options: [["", "— department-wide —"]]
    .concat(projOpts()), value: pid || ""}) +
  F.field("title", "The lesson, in one line", {
    placeholder: "Column grid frozen before MEP shaft coordination"}) +
  F.field("stage", "Which stage should have caught it", {
    options: [["", "— not stage specific —"]].concat(
      BOOT.stages.map(s => [s.stage, `${s.stage} · ${s.name}`]))}) +
  F.field("discipline", "Discipline", {options: [["", "— all —"]].concat(BOOT.teams)}) +
  F.field("category", "Category", {options: ["Coordination", "Governance", "Materials",
    "Planning", "Cost", "Document control", "Authority", "General"]}) +
  F.field("detail", "What happened", {type: "textarea", rows: 3}) +
  F.field("impact", "What it cost", {type: "textarea", rows: 2,
    placeholder: "One resubmission cycle, 4 weeks of authority wait"}),
  async d => { await F.act("/api/llr/create",
      {...d, origin_entity: originEntity || "", origin_id: originId || ""});
    refresh("Lesson raised — it needs a ruling before it can be adopted"); }, "Raise");

UI.llrRule = (R, then) => F.modal("Rule on this lesson",
  "§7.6 puts the ruling before adoption. Only a senior manager or the head can rule, "
  + "because the ruling changes what every future project is checked against.",
  F.field("status", "Decision", {options: [
    ["ruled", "Ruled — accepted as a lesson"],
    ["rejected", "Rejected — not a lesson, or not ours"]]}) +
  F.field("ruling", "The ruling", {type: "textarea", rows: 4,
    placeholder: "Cross-discipline area reconciliation is mandatory before submission.",
    hint: "This is the text the department is held to. A ruling with no text is not a ruling."}),
  async d => { await F.act("/api/llr/rule", {...d, id: R.id});
    F.toast("Ruled"); if (then) then(); }, "Record ruling");

UI.llrPromote = (R, then) => F.modal("Adopt into the stage checklist",
  "This is the loop. The check is added to the §4.2 template permanently, and lands "
  + "immediately on every checklist for that stage that is not yet signed.",
  F.field("stage", "Which stage checks for this", {
    options: BOOT.stages.map(s => [s.stage, `${s.stage} · ${s.name}`]),
    value: R.stage || R.promoted_stage || 3}) +
  F.field("text", "The check, as it should appear", {type: "textarea", rows: 3,
    value: R.ruling || R.title || "",
    hint: "Write it as something a person can tick or not tick."}),
  async d => { const r = await F.act("/api/llr/promote", {...d, id: R.id});
    F.toast(`Adopted into stage ${r.stage} — ${r.checklists_updated} open checklists updated`);
    if (then) then(); }, "Adopt");

UI.templateAdd = (stage) => F.modal(`Add a check to stage ${stage}`,
  "Manual §4.2's annexure, authored in-system. Every project that initiates this stage "
  + "from now on carries it.",
  F.field("text", "The check", {
    placeholder: "Column grid coordinated with Structure and acknowledged in writing"}) +
  F.field("source", "Source", {placeholder: "Manual §4.2 / authored in-system"}),
  async d => { await F.act("/api/template/add", {...d, stage});
    refresh("Added to the template"); }, "Add");

UI.templateRetire = (id) => F.modal("Retire this check",
  "It stops appearing on new checklists. The reason stays in the ledger — a check that "
  + "was removed is as interesting as one that was added.",
  F.field("reason", "Why", {type: "textarea", rows: 3}),
  async d => { await F.act("/api/template/retire", {...d, id});
    refresh("Retired"); }, "Retire");

UI.withdraw = (R, then) => F.modal(`Withdraw ${R.ref}`,
  "Withdrawal closes the case and stops every clock it started.",
  F.field("reason", "Why", {type: "textarea", rows: 3}),
  async d => { await F.act("/api/case/withdraw", {...d, id: R.id});
    F.toast("Withdrawn"); if (then) then(); CACHE.matrix = null; }, "Withdraw");

UI.closeProject = (R) => F.modal(`Close out ${R.name}`,
  "Manual §18. Gates checked: all 14 stations signed off, an as-built transmittal issued, "
  + "and no NCR left open. A refusal names what is outstanding and can be overridden "
  + "with a reason.",
  `<div class="note">Before this station existed the lifecycle had no end — stage 13
    “Construction Support” ran forever. Closeout is what makes a project finishable.</div>`,
  async d => { await F.act("/api/project/close", {...d, project_id: R.id});
    refresh("Project closed out"); }, "Close out");
