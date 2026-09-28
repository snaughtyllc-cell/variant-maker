(() => {
  "use strict";

  const STYLES = [
    "tiktok-classic-box",
    "edits-classic-outline",
    "edits-strong",
  ];
  const SLOTS = ["top", "mid", "low"];
  const MAX = 5;

  const seedInput = document.getElementById("seed");
  const stylesEl = document.getElementById("styles");
  const slotsEl = document.getElementById("slots");
  const addBtn = document.getElementById("add");
  const addHint = document.getElementById("add-hint");
  const versionsEl = document.getElementById("versions");
  const versionsEmpty = document.getElementById("versions-empty");
  const saveBtn = document.getElementById("save");
  const downloadBtn = document.getElementById("download");
  const statusEl = document.getElementById("status");
  const stillImg = document.getElementById("still");
  const frameEmpty = document.getElementById("frame-empty");
  const overlay = document.getElementById("overlay");
  const stillMeta = document.getElementById("still-meta");
  const cliHint = document.getElementById("cli-hint");

  let styleId = STYLES[0];
  let slot = SLOTS[0];
  let versions = [];

  function stillName(entry) {
    if (typeof entry === "string") return entry;
    if (entry && typeof entry.name === "string") return entry.name;
    return "";
  }

  const SLOT_Y = { top: 0.16, mid: 0.45, low: 0.62 };

  function payload() {
    const hooks = versions.map((v) => ({
      text: v.text,
      style_id: v.style_id,
      slot: v.slot,
    }));
    const runSlot = hooks.length ? hooks[hooks.length - 1].slot : slot;
    const allowMid = runSlot === "mid" || hooks.some((h) => h.slot === "mid");
    return {
      schema: "hook-variants.placement.v1",
      written_by: "place",
      seed_text: seedInput.value,
      slot: runSlot,
      y: SLOT_Y[runSlot],
      allow_mid: allowMid,
      hooks,
    };
  }

  function setStatus(message, kind) {
    statusEl.textContent = message;
    statusEl.classList.toggle("ok", kind === "ok");
    statusEl.classList.toggle("err", kind === "err");
  }

  function currentText() {
    return seedInput.value.trim();
  }

  function renderChips(root, items, selected, onPick, prefix) {
    root.replaceChildren();
    for (const item of items) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.role = "radio";
      btn.setAttribute("aria-checked", item === selected ? "true" : "false");
      btn.textContent = item;
      btn.addEventListener("click", () => onPick(item));
      btn.id = `${prefix}-${item}`;
      root.appendChild(btn);
    }
  }

  function renderPreview() {
    overlay.dataset.slot = slot;
    overlay.dataset.style = styleId;
    overlay.textContent = currentText() || "Your hook";
    const quoted = currentText() || "…";
    cliHint.textContent = `hook-variants clip.mp4 --text "${quoted}" --from-placement placement.json`;
  }

  function renderVersions() {
    versionsEl.replaceChildren();
    versionsEmpty.hidden = versions.length > 0;
    versions.forEach((version, index) => {
      const li = document.createElement("li");
      li.className = "version";

      const body = document.createElement("div");
      const text = document.createElement("div");
      text.className = "version-text";
      text.textContent = version.text;
      const meta = document.createElement("div");
      meta.className = "version-meta";
      meta.textContent = `${version.style_id} · ${version.slot}`;
      body.append(text, meta);

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "version-remove";
      remove.textContent = "Remove";
      remove.setAttribute("aria-label", `Remove version ${index + 1}`);
      remove.addEventListener("click", () => {
        versions.splice(index, 1);
        renderVersions();
      });

      li.append(body, remove);
      versionsEl.appendChild(li);
    });

    const full = versions.length >= MAX;
    addBtn.disabled = full;
    addHint.textContent = full ? "Maximum 5 versions" : "Up to 5 versions";
  }

  function addVersion() {
    const text = currentText();
    if (!text) {
      setStatus("Enter seed text before adding a version.", "err");
      seedInput.focus();
      return;
    }
    if (versions.length >= MAX) {
      setStatus("Maximum 5 versions.", "err");
      return;
    }
    versions.push({ text, style_id: styleId, slot });
    setStatus("");
    renderVersions();
  }

  function downloadPlacement() {
    const blob = new Blob([JSON.stringify(payload(), null, 2) + "\n"], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "placement.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function savePlacement() {
    const body = payload();
    try {
      const res = await fetch("/api/placement", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        let saved = "placement.json";
        try {
          const data = await res.json();
          if (data && data.path) saved = data.path;
        } catch {
          /* ignore */
        }
        setStatus(`Saved ${saved}`, "ok");
        return;
      }
    } catch {
      /* fall through to download */
    }
    downloadPlacement();
    setStatus("Downloaded placement.json (server save unavailable)", "ok");
  }

  function pickStyle(next) {
    styleId = next;
    renderChips(stylesEl, STYLES, styleId, pickStyle, "style");
    renderPreview();
  }

  function pickSlot(next) {
    slot = next;
    renderChips(slotsEl, SLOTS, slot, pickSlot, "slot");
    renderPreview();
  }

  async function loadStills() {
    let stills = [];
    try {
      const res = await fetch("/api/stills");
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) stills = data;
        else if (data && Array.isArray(data.stills)) stills = data.stills;
      }
    } catch {
      stills = [];
    }

    const names = stills.map(stillName).filter(Boolean);
    if (names.length === 0) {
      stillImg.hidden = true;
      stillImg.removeAttribute("src");
      frameEmpty.hidden = false;
      stillMeta.textContent = "Empty 9:16 frame — drop stills in this folder or ./out*";
      return;
    }

    stillImg.src = `/stills/${encodeURIComponent(names[0])}`;
    stillImg.hidden = false;
    frameEmpty.hidden = true;
    stillMeta.textContent =
      names.length === 1 ? names[0] : `${names[0]} · ${names.length} stills`;
  }

  pickStyle(styleId);
  pickSlot(slot);
  renderPreview();
  renderVersions();
  loadStills();

  seedInput.addEventListener("input", renderPreview);
  addBtn.addEventListener("click", addVersion);
  saveBtn.addEventListener("click", () => {
    savePlacement();
  });
  downloadBtn.addEventListener("click", () => {
    downloadPlacement();
    setStatus("Downloaded placement.json", "ok");
  });
  seedInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addVersion();
    }
  });
})();
