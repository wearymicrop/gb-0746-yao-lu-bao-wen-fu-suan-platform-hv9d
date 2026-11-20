const el = (id) => document.getElementById(id);
const states = { proven: "达标", cold: "失温", unproven: "缺证" };
const causes = {
  NO_READING: "读数失采",
  BAD_READING: "读数无效",
  DRIFT_LIMIT: "偏移超限",
  READING_CONFLICT: "同点读数冲突",
  RECIPE_OVERLAP: "配方重叠",
  RECIPE_GAP: "配方缺失",
  CALIBRATION_GAP: "校准缺失",
  CALIBRATION_OVERLAP: "校准重叠",
};
const time = (value) =>
  new Date(value * 1000).toLocaleTimeString("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour12: false,
  });
const temp = (value) =>
  value == null ? "—" : `${(value / 1000).toFixed(1)} °C`;
let snapshot,
  source = "dirty",
  serial = 0,
  archived,
  correction,
  buttons = [];
function make(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw Error(data.message || "请求失败，请重试");
  return data;
}
async function load(key) {
  const current = ++serial;
  el("reading-status").textContent = "正在复算";
  el("sign-form").querySelector("button").disabled = true;
  try {
    const parts = [
      "intake",
      "calibration",
      "alignment",
      "soak",
      "gaps",
      "reconcile",
    ];
    const result = await Promise.all(
      parts.map((part) => api(`/api/${part}/${encodeURIComponent(key)}`)),
    );
    if (current !== serial) return;
    source = key;
    snapshot = Object.fromEntries(parts.map((part, i) => [part, result[i]]));
    el("batch").textContent = snapshot.intake.plan.batch;
    el("reading-status").textContent = snapshot.soak.goal_met
      ? "保温达标"
      : "待工艺复核";
    el("run-actions").hidden = true;
    el("run-feedback").textContent = "";
    archived = undefined;
    renderCorrection(null);
    renderCorrectionChain(null);
    el("correction-feedback").textContent = "";
    render();
    el("sign-form").querySelector("button").disabled = false;
  } catch (error) {
    if (current === serial) el("reading-status").textContent = error.message;
  }
}
function inspect(index) {
  const item = snapshot.soak.sections[index];
  if (!item) return;
  buttons.forEach((button, i) =>
    button.setAttribute("aria-pressed", String(i === index)),
  );
  const title = make(
    "h3",
    `${time(item.start)}–${time(item.end)} · ${states[item.state]} · ${item.version || "配方待核"}`,
  );
  const grid = make("div", undefined, "zone-grid");
  for (const z of item.zones) {
    const cell = make("div", z.zone, "zone-card");
    cell.append(
      make("strong", temp(z.value_mc)),
      make(
        "small",
        `目标 ${temp(z.target_mc)} · 读数行 ${z.reading_rows.join("、") || "—"}`,
      ),
      make(
        "small",
        z.code === "BELOW_TARGET"
          ? "低于目标"
          : causes[z.code] || `校准行 ${z.calibration_row ?? "—"}`,
      ),
    );
    grid.append(cell);
  }
  el("segment").replaceChildren(title, grid);
}
function render() {
  const { reconcile: r, intake, soak, gaps } = snapshot;
  el("metrics").replaceChildren(
    ...[
      ["计划", r.planned_s],
      ["达标累计", r.proven_s],
      ["失温", r.cold_s],
      ["缺证", r.unproven_s],
      ["最长连续", r.longest_s],
    ].map(([label, value]) => {
      const tile = make("div", undefined, "kpi");
      tile.append(
        make("span", label),
        make("strong", value),
        make("small", " 秒"),
      );
      return tile;
    }),
  );
  el("balance").textContent =
    r.status === "MATCHED"
      ? `时长和行数已对平 · 连续目标 ${soak.goal_s} 秒`
      : "炉批存在差异";
  buttons = soak.sections.map((item, i) => {
    const button = make("button", undefined, `slot ${item.state}`);
    button.style.setProperty("--part", item.seconds);
    button.title = `${time(item.start)} ${states[item.state]}`;
    button.setAttribute("aria-label", button.title);
    button.onclick = () => inspect(i);
    return button;
  });
  el("track-bars").replaceChildren(...buttons);
  const axis = Array.from({ length: 5 }, (_, i) =>
    make(
      "time",
      time(intake.plan.start + Math.floor((r.planned_s * i) / 4)).slice(0, 5),
    ),
  );
  el("track-axis").replaceChildren(...axis);
  inspect(0);
  el("gap-count").textContent = `${gaps.gap_count} 段`;
  el("gap-list").replaceChildren(
    ...(gaps.gaps.length
      ? gaps.gaps.map((row) => {
          const button = make("button", undefined, "gap");
          const summary = make(
            "span",
            row.codes.map((code) => causes[code] || code).join("、"),
          );
          summary.append(make("small", `${time(row.start)} · ${row.decision}`));
          button.append(summary, make("time", `${row.seconds} 秒`));
          button.onclick = () =>
            inspect(
              soak.sections.findIndex((item) => item.start === row.start),
            );
          return button;
        })
      : [make("p", "保温期间无断档", "empty")]),
  );
  evidence();
}
function evidence() {
  if (!snapshot) return;
  const { intake, calibration, alignment } = snapshot;
  let columns, entries;
  switch (el("evidence").value) {
    case "calibration":
      columns = ["热区", "采集时间", "读数行", "校准后", "校准行"];
      entries = calibration.corrected.map((row) => [
        row.zone,
        time(row.time),
        row.row,
        temp(row.corrected_mc),
        row.calibration_row,
      ]);
      entries.unshift(
        ...calibration.isolated.map((row) => [
          row.raw?.zone || "—",
          "隔离",
          row.row,
          row.message,
          "—",
        ]),
      );
      break;
    case "alignment":
      columns = ["热区", "起点", "终点", "有效读数", "读数行"];
      entries = Object.entries(alignment.zones).flatMap(([zone, spans]) =>
        spans.map((row) => [
          zone,
          time(row.start),
          time(row.end),
          temp(row.value_mc),
          row.reading_rows.join("、"),
        ]),
      );
      break;
    default:
      columns = ["热区", "采集时间", "来源行", "采集值", "判定"];
      entries = intake.points.map((row) => [
        row.zone,
        time(row.time),
        row.row,
        temp(row.value_mc),
        "采信",
      ]);
      entries.unshift(
        ...[...intake.isolated, ...intake.notices].map((row) => [
          row.raw?.zone || "—",
          row.raw?.time?.slice?.(11, 19) || "—",
          row.row,
          row.raw?.value ?? "—",
          row.message,
        ]),
      );
  }
  const table = make("table");
  const head = table.createTHead().insertRow();
  columns.forEach((label) => head.append(make("th", label)));
  const body = table.createTBody();
  entries.forEach((entry) => {
    const row = body.insertRow();
    entry.forEach((value, index) =>
      row.append(make("td", value, index === 0 ? "" : "num")),
    );
  });
  el("evidence-table").replaceChildren(table);
}
el("evidence").onchange = evidence;
el("sample").onchange = (event) => load(event.target.value);
el("upload").onchange = async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const result = await api("/api/sources", { method: "POST", body: file });
    const option = new Option(file.name, result.source, true, true);
    el("sample").add(option);
    load(result.source);
  } catch (error) {
    el("reading-status").textContent = error.message;
  } finally {
    event.target.value = "";
  }
};
el("sign-form").onsubmit = async (event) => {
  event.preventDefault();
  const requested = source;
  const button = event.submitter;
  button.disabled = true;
  try {
    const result = await api("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, operator: el("operator").value }),
    });
    if (source !== requested) return;
    archived = result.id;
    el("run-feedback").textContent =
      `${result.reused ? "归档已存在" : "归档成功"} · ${result.approval.decision}`;
    el("export").href = `/api/runs/${archived}/export`;
    el("run-actions").hidden = false;
    await loadCorrection(archived);
  } catch (error) {
    el("run-feedback").textContent = error.message;
  } finally {
    button.disabled = false;
  }
};
el("rerun").onclick = async () => {
  try {
    const result = await api(`/api/runs/${archived}/rerun`, { method: "POST" });
    el("run-feedback").textContent =
      `重跑一致 · ${result.manifest.digest.slice(0, 12)}`;
  } catch (error) {
    el("run-feedback").textContent = error.message;
  }
};
const stamp = (value) =>
  value
    ? new Date(value * 1000).toLocaleString("zh-CN", {
        timeZone: "Asia/Shanghai",
        hour12: false,
      })
    : "—";
const short = (value) => (value ? value.slice(0, 12) : "—");
function cellLine(label, value, cls) {
  const line = make("div", undefined, cls);
  line.append(make("span", label), make("strong", value));
  return line;
}
function renderCorrectionChain(chain) {
  const box = el("correction-chain");
  if (!chain) {
    box.replaceChildren(make("p", "归档炉批后可送入迟到更正记录。", "empty"));
    return;
  }
  const list = make("div", undefined, "chain");
  const base = make("div", undefined, "chain-row");
  base.append(
    make("b", "原始凭证"),
    make("code", short(chain.base.id)),
    make("span", `签核 ${chain.base.approval.status} · ${chain.base.approval.decision}`),
    make("span", "只读", "tag lock"),
  );
  list.append(base);
  if (!chain.corrections.length) {
    list.append(make("p", "尚无更正结论。", "empty"));
  }
  chain.corrections.forEach((row) => {
    const item = make("div", undefined, `chain-row ${row.status.toLowerCase()}`);
    item.append(
      make("b", row.status === "FORMAL" ? "正式结论" : "待核对平"),
      make("code", short(row.id)),
      make("span", `替换 ${short(row.supersedes)}`),
      make(
        "span",
        row.status === "FORMAL"
          ? `签核 ${row.approval.status} · ${row.approval.decision}`
          : row.pending?.message || "尚未对平",
      ),
      make(
        "span",
        `登记 ${row.recorder} · 收到 ${row.received_at.join("、") || "—"}`,
      ),
      make(
        "span",
        `达标 ${row.result.proven_s}s · 缺证 ${row.result.unproven_s}s · 最长 ${row.result.longest_s}s`,
        "num",
      ),
    );
    if (row.correction_rows.length) {
      item.append(make("span", `更正原校准行 ${row.correction_rows.join("、")}`));
    }
    list.append(item);
  });
  box.replaceChildren(
    make("h3", "结论链"),
    list,
    make(
      "p",
      chain.current_kind === "correction"
        ? `当前生效 ${short(chain.current)}`
        : "当前生效为原始凭证",
      "chain-current",
    ),
  );
}
function renderCorrection(record) {
  correction = record;
  const base = el("correction-base");
  const evidence = el("correction-evidence");
  const diff = el("correction-diff");
  el("correction-state").textContent = record
    ? record.status === "FORMAL"
      ? "已生成正式结论"
      : "待核对平"
    : "待原始凭证";
  if (!record) {
    base.replaceChildren();
    evidence.replaceChildren();
    diff.replaceChildren();
    return;
  }
  base.replaceChildren(
    cellLine("基础凭证", short(record.base_run)),
    cellLine("替换结论", `${short(record.supersedes)}（${record.supersedes_kind === "run" ? "原签核" : "上次更正"}）`),
    cellLine(
      "签核",
      record.approval
        ? `${record.approval.status} · ${record.approval.decision}`
        : record.pending?.message || "—",
    ),
    cellLine("登记人", record.recorder),
    cellLine("结论摘要", short(record.digest), "mono"),
  );
  const rows = record.corrections.map((entry) =>
    make("div", undefined, "evidence-row"),
  );
  record.corrections.forEach((entry, index) => {
    const row = rows[index];
    row.append(
      make("b", `第 ${entry.index} 条`),
      make(
        "span",
        entry.replaces_row
          ? `替换原校准行 ${entry.replaces_row}`
          : "追加校准窗口",
      ),
      make(
        "span",
        `${entry.zone} ${stamp(entry.start)}–${time(entry.end)} · 偏移 ${temp(entry.offset_mc)}`,
      ),
      make("span", entry.reason || "未填依据"),
      make("code", entry.document || "无文号"),
      make("time", entry.received_at ? stamp(entry.received_at) : "未记到达时间"),
    );
  });
  const adopted = [make("h3", "采用的更正证据"), ...rows];
  if (record.pending) {
    adopted.push(
      make(
        "p",
        `${record.pending.message}（时长差 ${record.pending.difference_s ?? "—"} 秒，行数差 ${record.pending.reading_difference ?? "—"}）`,
        "alert",
      ),
    );
  }
  evidence.replaceChildren(...adopted);
  const d = record.diff;
  const summary = [
    ["达标", d.before.proven_s, d.after.proven_s],
    ["失温", d.before.cold_s, d.after.cold_s],
    ["缺证", d.before.unproven_s, d.after.unproven_s],
    ["最长连续", d.before.longest_s, d.after.longest_s],
    ["断档段数", d.before.gap_count, d.after.gap_count],
  ];
  const table = make("table");
  const head = table.createTHead().insertRow();
  ["项目", "替换前", "替换后", "变化"].forEach((label) =>
    head.append(make("th", label)),
  );
  const body = table.createTBody();
  summary.forEach(([label, before, after]) => {
    const row = body.insertRow();
    row.append(
      make("td", label),
      make("td", before, "num"),
      make("td", after, "num"),
      make("td", before === after ? "不变" : after - before > 0 ? `+${after - before}` : String(after - before), "num"),
    );
  });
  const callout = [];
  const replaced = d.calibration.replaced.filter((row) => row.before_mc !== row.after_mc);
  replaced.forEach((row) => {
    callout.push(
      make(
        "p",
        `校准行 ${row.row}（${row.zone}）偏移 ${temp(row.before_mc)} → ${temp(row.after_mc)}`,
      ),
    );
  });
  const zones = Object.keys(d.alignment);
  if (zones.length) {
    callout.push(make("p", `受影响热区：${zones.join("、")}（窗口与有效读数见对齐证据）`));
  }
  const changedSections = d.soak.sections.length;
  if (changedSections) {
    const first = d.soak.sections[0];
    callout.push(
      make(
        "p",
        `${changedSections} 段保温判定改写${first.after ? `，如 ${stamp(first.after.start)} 起 ${states[first.before?.state] || "—"} → ${states[first.after.state]}` : ""}`,
      ),
    );
  }
  if (d.gaps.length) {
    callout.push(make("p", `${d.gaps.length} 段断档证据随更正消失或改写`));
  }
  const alert = record.pending
    ? make("p", "尚未对平，不能作为正式结论发布。", "alert")
    : make("p", "原签核凭证保持原样，差异已记入本条结论。", "note");
  diff.replaceChildren(
    make("h3", "前后差异"),
    table,
    ...callout,
    alert,
  );
}
async function loadCorrection(runId) {
  renderCorrection(null);
  renderCorrectionChain(null);
  if (!runId) return;
  try {
    const chain = await api(`/api/runs/${runId}/corrections`);
    renderCorrectionChain(chain);
  } catch (error) {
    el("correction-feedback").textContent = error.message;
  }
}
el("correction-file").onchange = async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  if (!archived) {
    el("correction-feedback").textContent = "请先归档原始凭证，再送入更正记录";
    event.target.value = "";
    return;
  }
  try {
    const payload = JSON.parse(await file.text());
    const corrections = Array.isArray(payload)
      ? payload
      : payload.corrections || [payload];
    const record = await api("/api/corrections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        base_run: archived,
        recorder: el("operator").value || "值班员",
        corrections,
      }),
    });
    renderCorrection(record);
    el("correction-feedback").textContent = record.reused
      ? `更正已存在，未重复生成结论 · ${record.status === "FORMAL" ? "正式" : "待核"}`
      : `更正结论已生成 · ${record.status === "FORMAL" ? "正式" : "待核对平"}`;
    await loadCorrection(record.base_run);
  } catch (error) {
    el("correction-feedback").textContent = error.message;
  } finally {
    event.target.value = "";
  }
};
load(source);
