/* ZD PULSE — the form layer.
   A generic modal + field renderer, and one `act()` that funnels every mutation
   through the same path: post, surface a refusal properly, offer an override
   where the server said one is allowed, refresh.

   The refusal handling is the point. A gate that just says "no" gets worked
   around; a gate that explains itself, names what is missing and lets a manager
   override WITH A REASON gets used — and the override is what ends up in the
   ledger. */

const F = {};

F.modal = function (title, sub, bodyHTML, onSubmit, submitLabel) {
  document.querySelectorAll(".zmodal").forEach(x => x.remove());
  const m = document.createElement("div");
  m.className = "zmodal";
  m.innerHTML = `
    <div class="zm-bd"></div>
    <div class="zm-box" role="dialog" aria-modal="true">
      <div class="zm-h">
        <div><h3>${title}</h3>${sub ? `<p>${sub}</p>` : ""}</div>
        <button class="zm-x" aria-label="Close">✕</button>
      </div>
      <form class="zm-b">${bodyHTML}
        <div class="zm-err" hidden></div>
        <div class="zm-f">
          <button type="button" class="btn zm-cancel">Cancel</button>
          <button type="submit" class="btn pri">${submitLabel || "Save"}</button>
        </div>
      </form>
    </div>`;
  document.body.appendChild(m);
  const close = () => m.remove();
  m.querySelector(".zm-x").onclick = close;
  m.querySelector(".zm-cancel").onclick = close;
  m.querySelector(".zm-bd").onclick = close;
  const first = m.querySelector("input,select,textarea");
  if (first) setTimeout(() => first.focus(), 40);

  m.querySelector("form").onsubmit = async ev => {
    ev.preventDefault();
    const btn = m.querySelector('button[type="submit"]');
    const err = m.querySelector(".zm-err");
    const data = {};
    m.querySelectorAll("[name]").forEach(i => {
      data[i.name] = i.type === "checkbox" ? (i.checked ? 1 : 0) : i.value;
    });
    btn.disabled = true; btn.textContent = "Working…"; err.hidden = true;
    try {
      await onSubmit(data);
      close();
    } catch (x) {
      err.hidden = false;
      err.innerHTML = `<b>${F.esc(x.message)}</b>`
        + (x.detail ? `<br><span class="mut">${F.esc(x.detail)}</span>` : "")
        + (x.missing ? `<ul>${x.missing.map(s => `<li>${F.esc(s)}</li>`).join("")}</ul>` : "")
        + (x.waiting_days != null
            ? `<br><span class="mut">Waiting ${x.waiting_days} working days so far.</span>` : "");
      if (x.overridable) {
        err.innerHTML += `
          <div class="zm-ovr">
            <label>Override — state the reason. It goes in the ledger.</label>
            <input name="override_reason" placeholder="Why are you proceeding anyway?">
            <button type="button" class="btn sm zm-force">Override &amp; proceed</button>
          </div>`;
        err.querySelector(".zm-force").onclick = async () => {
          const r = err.querySelector('[name="override_reason"]').value.trim();
          if (!r) { err.querySelector("input").focus(); return; }
          try { await onSubmit({...data, override_reason: r, force: 1}); close(); }
          catch (y) { err.querySelector(".zm-ovr").innerHTML =
            `<b style="color:var(--bad)">${F.esc(y.message)}</b>`; }
        };
      }
      btn.disabled = false; btn.textContent = submitLabel || "Save";
    }
  };
  return m;
};

F.esc = s => String(s ?? "").replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

F.field = (name, label, opts = {}) => {
  const {type = "text", value = "", placeholder = "", hint = "", options, rows} = opts;
  let input;
  if (options) {
    input = `<select name="${name}">${options.map(o => {
      const [v, l] = Array.isArray(o) ? o : [o, o];
      return `<option value="${F.esc(v)}" ${String(v) === String(value) ? "selected" : ""}>${F.esc(l)}</option>`;
    }).join("")}</select>`;
  } else if (type === "textarea") {
    input = `<textarea name="${name}" rows="${rows || 3}" placeholder="${F.esc(placeholder)}">${F.esc(value)}</textarea>`;
  } else if (type === "checkbox") {
    input = `<label class="zm-chk"><input type="checkbox" name="${name}" ${value ? "checked" : ""}>
             <span>${F.esc(placeholder || label)}</span></label>`;
    return `<div class="zm-fld">${input}${hint ? `<em>${F.esc(hint)}</em>` : ""}</div>`;
  } else {
    input = `<input type="${type}" name="${name}" value="${F.esc(value)}" placeholder="${F.esc(placeholder)}">`;
  }
  return `<div class="zm-fld"><label>${F.esc(label)}</label>${input}
          ${hint ? `<em>${F.esc(hint)}</em>` : ""}</div>`;
};

/* every mutation goes through here */
F.act = async (path, body) => {
  const r = await fetch(F.M + path, {
    method: "POST",
    headers: {"Content-Type": "application/json", "Authorization": "Bearer " + F.TOK},
    body: JSON.stringify(body)
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(d.error || "Request failed"), d);
  return d;
};

F.toast = (msg, bad) => {
  document.querySelectorAll(".ztoast").forEach(x => x.remove());
  const t = document.createElement("div");
  t.className = "ztoast" + (bad ? " bad" : "");
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.classList.add("go"), 20);
  setTimeout(() => t.remove(), 4200);
};
