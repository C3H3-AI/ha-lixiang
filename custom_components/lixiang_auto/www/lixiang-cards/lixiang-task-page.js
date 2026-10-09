/**
 * lixiang-task-page —— 车控任务（对齐 App「任务大师」，但落地为 HA 自动化）
 *
 * 背景：
 *   App 的「任务大师」是【云端规则引擎】—— 规则存理想服务器，
 *   集成没有对应 API，无法读写。
 *
 * 但 App 的模型 = IFTTT = HA automation：
 *   任务名称  → alias
 *   如果      → trigger
 *   就执行    → action
 *
 * 本卡片用【同样的交互】创建 **HA 自动化**，效果等价甚至更强：
 *   · 本地执行（不依赖网络，更快）
 *   · 可联动其他品牌设备
 *   · 可发通知 / 调脚本
 *
 * 写入 API：POST /api/config/automation/config/{id}
 */

const CARD_TAG = "lixiang-task-page";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
let __fontBase = DEFAULT_FONT_BASE;

/* ── 车控常用模板（对应 App 社区的常见任务）──
 * entity_id: null 的占位符在卡片运行时用自动发现结果填充 */
function buildPresets(card) {
  const eid = (f) => card._eid(f);
  return PRESET_DEFS.map((p) => {
    const t = Object.assign({}, p.trigger);
    if (!t.entity_id) {
      t.entity_id = eid(t._field
        || (t.platform === "numeric_state" && t.below != null ? "battery"
            : (t.above != null ? "room_temp" : "status")));
    }
    delete t._field;
    const action = p.action.map((a) => {
      const b = JSON.parse(JSON.stringify(a));
      if (b.target && b.target.entity_id === null) b.target.entity_id = eid(p.actionField || "ac");
      return b;
    }).filter((a) => !(a.target && !a.target.entity_id));
    return Object.assign({}, p, { trigger: t, action });
  }).filter((p) => p.trigger.entity_id && p.action.length);
}
const PRESET_DEFS = [
  { name: "无人关闭通风", icon: "ic_home_fan_on.webp", color: "#34C759", actionField: "ac",
    desc: "离车后自动关闭空调通风",
    trigger: { platform: "state", entity_id: null, to: "已驻车（P 档）", for: "00:05:00" },
    action: [{ service: "climate.turn_off", target: { entity_id: null } }] },
  { name: "有人自动通风", icon: "ic_home_fan_on.webp", color: "#34C759", actionField: "ac",
    desc: "车内温度过高时开启空调",
    trigger: { platform: "numeric_state", entity_id: null, above: 30 },
    action: [{ service: "climate.turn_on", target: { entity_id: null } }] },
  { name: "离车关遮阳帘防晒", icon: "ic_home_control.webp", color: "#0A58F6", actionField: "sunshade",
    desc: "锁车后关闭遮阳帘",
    trigger: { platform: "state", entity_id: null, to: "locked", _field: "lock" },
    action: [{ service: "cover.close_cover", target: { entity_id: null } }] },
  { name: "低电量提醒", icon: "ic_home_battery.webp", color: "#FF9500", actionField: "sentry",
    desc: "电量低于 20% 时发通知",
    trigger: { platform: "numeric_state", entity_id: null, below: 20 },
    action: [{ service: "persistent_notification.create",
               data: { title: "理想 L6 电量偏低", message: "建议尽快充电" } }] },
  { name: "哨兵模式自动开启", icon: "ic_home_sentry.png", color: "#FF3B30", actionField: "ac",
    desc: "驻车 10 分钟后开启哨兵",
    trigger: { platform: "state", entity_id: null, to: "已驻车（P 档）", for: "00:10:00", _field: "status" },
    action: [{ service: "switch.turn_on", target: { entity_id: null } }] },
  { name: "长途驾驶疲劳缓解", icon: "ic_home_control.webp", color: "#FF9500", actionField: "ac",
    desc: "连续驾驶 2 小时后提醒休息",
    trigger: { platform: "state", entity_id: null, to: "行驶中", for: "02:00:00", _field: "status" },
    action: [{ service: "persistent_notification.create",
               data: { title: "该休息了", message: "已连续驾驶 2 小时" } }] },
];

const STYLE = `
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_medium.ttf");  font-weight:500; font-display:swap; }
  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F5F5F7; --lx-bg:#FFF; --lx-line:#EDEDF0; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
    .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
    .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
            --lx-card:#F5F5F7; --lx-bg:#FFF; --lx-line:#EDEDF0; --lx-blue:#0A58F6; }
  .root { background:var(--lx-bg); color:var(--lx-t1); padding-bottom:20px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }

  .topbar { display:flex; align-items:center; height:52px; padding:0 16px; position:relative; }
  .back { width:34px; height:34px; border-radius:50%; background:var(--lx-card);
          display:flex; align-items:center; justify-content:center; cursor:pointer; }
  .back img { width:18px; height:18px; opacity:.7; }
  .topbar h1 { position:absolute; left:0; right:0; text-align:center;
               font-size:18px; font-weight:500; margin:0; pointer-events:none; }
  .help { margin-left:auto; font-size:15px; color:var(--lx-t2); cursor:pointer;
          padding:6px 8px; position:relative; z-index:2; }

  /* Tabs */
  .tabs { display:flex; gap:26px; padding:6px 20px 0; border-bottom:1px solid var(--lx-line); }
  .tab { font-size:15.5px; color:var(--lx-t2); padding:10px 0 12px; cursor:pointer;
         position:relative; }
  .tab.on { color:var(--lx-t1); font-weight:500; }
  .tab.on::after { content:""; position:absolute; left:0; right:0; bottom:-1px;
                   height:2.5px; background:var(--lx-blue); border-radius:2px; }

  .sorts { display:flex; gap:20px; padding:16px 20px 6px; }
  .sort { font-size:14.5px; color:var(--lx-t3); cursor:pointer; }
  .sort.on { color:var(--lx-t1); font-weight:500; }

  /* 任务卡列表 */
  .list { padding:6px 16px 0; }
  .item { display:flex; align-items:center; gap:13px; background:var(--lx-card);
          border-radius:16px; padding:15px 16px; margin-bottom:10px; cursor:pointer;
          transition:transform .13s; }
  .item:active { transform:scale(.985); }
  .item .ic { width:38px; height:38px; border-radius:11px; display:flex;
              align-items:center; justify-content:center; flex:0 0 auto; }
  .item .ic img { width:21px; height:21px; }
  .item .tx { flex:1; min-width:0; }
  .item .n { font-size:16px; display:flex; align-items:center; gap:7px; }
  .item .n .new { font-size:10px; background:var(--lx-blue); color:#fff;
                  padding:2px 6px; border-radius:5px; font-weight:500; }
  .item .a { font-size:12.5px; color:var(--lx-t3); margin-top:5px; }
  .item .ar { color:var(--lx-t3); font-size:17px; flex:0 0 auto; }
  .item.on .n { color:var(--lx-blue); }

  /* 创建区 */
  .create { margin:18px 16px 0; }
  .field { background:var(--lx-card); border-radius:18px; padding:16px;
           margin-bottom:14px; }
  .field .lbl { font-size:15px; font-weight:500; margin-bottom:4px; }
  .field .hint { font-size:12.5px; color:var(--lx-t3); line-height:1.55;
                 margin-bottom:12px; }
  .nameinput { width:100%; border:none; background:transparent; font-size:16px;
               color:var(--lx-t1); outline:none; font-family:inherit;
               padding:10px 0; }
  .nameinput::placeholder { color:#C7C7CC; }
  .addbox { border:1.5px dashed var(--lx-line); border-radius:14px; padding:22px;
            display:flex; flex-direction:column; align-items:center; gap:6px;
            cursor:pointer; color:var(--lx-t2); }
  .addbox .p { font-size:26px; line-height:1; font-weight:300; }
  .addbox .t { font-size:14.5px; }
  .chips { display:flex; flex-direction:column; gap:8px; }
  .chip { background:var(--lx-bg); border-radius:12px; padding:12px 14px;
          font-size:13.5px; display:flex; align-items:center; gap:9px; }
  .chip .x { margin-left:auto; color:var(--lx-t3); cursor:pointer; padding:0 4px;
             font-size:16px; }
  .confirm { text-align:center; border-radius:26px; padding:15px; font-size:16px;
             background:#1A1A1A; color:#fff; cursor:pointer; transition:opacity .2s; }
  .confirm.dis { background:#E5E5EA; color:#AEAEB2; cursor:not-allowed; }
  .confirm:not(.dis):active { transform:scale(.985); }

  /* 底部固定 */
  .bottom { display:flex; align-items:center; gap:12px; margin:18px 16px 0; }
  .share { font-size:14.5px; color:var(--lx-t2); cursor:pointer; }
  .mk { flex:1; text-align:center; background:#1A1A1A; color:#fff;
        border-radius:24px; padding:14px; font-size:15px; cursor:pointer; }

  .empty { text-align:center; color:var(--lx-t3); font-size:13px; padding:30px 0; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9;
           max-width:82%; text-align:center; line-height:1.5; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  .toast.ok { background:rgba(28,150,70,.92); }
  .toast.err { background:rgba(200,40,40,.92); }
  /* 无障碍：键盘焦点 + 动效偏好 */
  [role="button"]:focus-visible, [role="switch"]:focus-visible,
  .btn:focus-visible, button:focus-visible {
    outline:2.5px solid var(--lx-blue); outline-offset:2px; border-radius:8px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.01ms !important;
      transition-duration:.01ms !important; } }
`;

class LixiangTaskPage extends HTMLElement {
  setConfig(c) {
    this._config = c || {};
    if (this._config.icon_base) __iconBase = this._config.icon_base;
    if (this._config.font_base) __fontBase = this._config.font_base; this._tab = "discover"; this._sort = "rec";
    this._mine = []; this._draft = null; this._built = false;
  }
  set hass(h) { this._hass = h; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 20; }
  disconnectedCallback() { if (this._tt) clearTimeout(this._tt); }

  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try { const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config || {}).resolve() || {};
    } catch (e) {}
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }
  _eid(f) {
    const m = (this._config || {})[f];
    if (typeof m === "string" && m.includes(".")) return m;
    return (this._autoBind() || {})[f] || null;
  }

  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role","button"); el.setAttribute("tabindex","0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); handler(e); }
    });
  }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const root = document.createElement("div");
    root.className = "root"; root.dataset.theme = (this._config && this._config.theme) || "light";
    root.innerHTML = `
      <div class="topbar">
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return.webp" alt=""></div>
        <h1>任务大师</h1>
        <div class="help" id="help" role="button" tabindex="0" aria-label="帮助">帮助</div>
      </div>

      <div class="tabs">
        <div class="tab on" data-tab="discover" role="button" tabindex="0">发现</div>
        <div class="tab" data-tab="mine" role="button" tabindex="0">我的任务</div>
        <div class="tab" data-tab="create" role="button" tabindex="0">创建任务</div>
      </div>

      <div id="body"></div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    const back = () => {
      const p = (this._config.nav || {}).back || "/lixiang/app";
      history.pushState(null, "", p);
      this.dispatchEvent(new CustomEvent("location-changed", { bubbles:true, composed:true }));
    };
    this._a11y(this.querySelector("#back"), "返回", back);
    this.querySelector("#back").addEventListener("click", back);

    const help = () => this._toast(
      "App 的「任务大师」规则存在理想云端，集成无法读写。本页创建的是 HA 自动化" +
      "（本地执行，可联动其他设备），效果等价。", null, 5200);
    this._a11y(this.querySelector("#help"), "帮助", help);
    this.querySelector("#help").addEventListener("click", help);

    this.querySelectorAll(".tab").forEach(t => {
      const act = () => { this._tab = t.dataset.tab; this._render(); };
      this._a11y(t, t.textContent, act);
      t.addEventListener("click", act);
    });

    this._built = true;
  }

  /** 模板（延迟构造：实体由自动发现提供） */
  _presets() {
    if (!this._presetCache) this._presetCache = buildPresets(this);
    return this._presetCache;
  }

  _toast(msg, kind, ms) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, ms || 2600);
  }

  /** 我的任务：枚举 automation 实体（由本卡片创建的） */
  _myTasks() {
    const out = [];
    const h = this._hass; if (!h) return out;
    for (const id of Object.keys(h.states)) {
      if (!id.startsWith("automation.")) continue;
      const s = h.states[id];
      const a = s.attributes || {};
      const isMine = (a.id && String(a.id).startsWith("lx_"))
        || /理想|车辆|车控|哨兵|充电|座椅|空调/.test(a.friendly_name || "");
      if (isMine) out.push({ id, eid: id, alias: a.friendly_name || id,
                             on: s.state === "on", last: a.last_triggered });
    }
    return out;
  }

  _render() {
    const box = this.querySelector("#body");
    this.querySelectorAll(".tab").forEach(t =>
      t.className = "tab" + (t.dataset.tab === this._tab ? " on" : ""));

    if (this._tab === "discover") { box.innerHTML = this._discoverHtml(); this._bindDiscover(); }
    else if (this._tab === "mine") { box.innerHTML = this._mineHtml(); this._bindMine(); }
    else { box.innerHTML = this._createHtml(); this._bindCreate(); }
  }

  /* ── 发现（模板库）── */
  _discoverHtml() {
    return `
      <div class="sorts">
        <span class="sort on" data-s="rec">推荐</span>
        <span class="sort" data-s="hot">最热</span>
        <span class="sort" data-s="new">飙升</span>
      </div>
      <div class="list">
        ${this._presets().map((p, i) => `
          <div class="item" data-i="${i}">
            <div class="ic" style="background:${p.color}22">
              <img src="${__iconBase}/${p.icon}" alt="" onerror="this.style.visibility='hidden'"></div>
            <div class="tx">
              <div class="n">${p.name}<span class="new">NEW</span></div>
              <div class="a">${p.desc}</div>
            </div>
            <div class="ar">›</div>
          </div>`).join("")}
      </div>
      <div class="bottom">
        <span class="share" id="share" role="button" tabindex="0">分享码添加</span>
        <div class="mk" id="mk" role="button" tabindex="0">创建任务</div>
      </div>`;
  }

  _bindDiscover() {
    this.querySelectorAll(".sort").forEach(s => {
      const act = () => {
        this._sort = s.dataset.s;
        this.querySelectorAll(".sort").forEach(x =>
          x.className = "sort" + (x.dataset.s === this._sort ? " on" : ""));
      };
      this._a11y(s, s.textContent, act);
      s.addEventListener("click", act);
    });
    this.querySelectorAll(".item").forEach(it => {
      const p = this._presets()[Number(it.dataset.i)];
      const act = () => this._applyPreset(p);
      this._a11y(it, p.name, act);
      it.addEventListener("click", act);
    });
    const mk = this.querySelector("#mk");
    if (mk) { const a = () => { this._tab = "create"; this._render(); };
      this._a11y(mk, "创建任务", a); mk.addEventListener("click", a); }
    const sh = this.querySelector("#share");
    if (sh) { const a = () => this._toast("分享码需在理想 App 内使用（云端功能）");
      this._a11y(sh, "分享码添加", a); sh.addEventListener("click", a); }
  }

  /* ── 我的任务 ── */
  _mineHtml() {
    const list = this._myTasks();
    if (!list.length) {
      return `<div class="empty">还没有任务<br>
        <span style="font-size:12px">到「发现」里选一个模板，或自己创建</span></div>
        <div class="bottom"><div class="mk" id="mk2" role="button" tabindex="0">创建任务</div></div>`;
    }
    return `<div class="list">${list.map(t => `
      <div class="item${t.on ? " on" : ""}" data-eid="${t.eid}">
        <div class="ic" style="background:${t.on ? "#0A58F622" : "#8E8E9322"}">
          <img src="${__iconBase}/ic_home_control.webp" alt=""></div>
        <div class="tx">
          <div class="n">${t.alias}</div>
          <div class="a">${t.on ? "已启用" : "已停用"}${t.last ? " · 上次 " + String(t.last).slice(0, 16) : ""}</div>
        </div>
        <div class="ar">›</div>
      </div>`).join("")}</div>
      <div class="bottom"><div class="mk" id="mk3" role="button" tabindex="0">创建任务</div></div>`;
  }

  _bindMine() {
    this.querySelectorAll(".item").forEach(it => {
      const eid = it.dataset.eid;
      const act = async () => {
        try {
          await this._hass.callService("automation", this._hass.states[eid].state === "on" ? "turn_off" : "turn_on",
            { entity_id: eid });
          this._toast("已切换", "ok"); this._render();
        } catch (e) { this._toast("操作失败", "err"); }
      };
      this._a11y(it, it.querySelector(".n").textContent, act);
      it.addEventListener("click", act);
    });
    const mk = this.querySelector("#mk2") || this.querySelector("#mk3");
    if (mk) { const a = () => { this._tab = "create"; this._render(); };
      this._a11y(mk, "创建任务", a); mk.addEventListener("click", a); }
  }

  /* ── 创建 ── */
  _createHtml() {
    const d = this._draft;
    const trg = d && d.trigger ? `<div class="chips"><div class="chip">
        <span>${this._describeTrigger(d.trigger)}</span>
        <span class="x" data-del="t">×</span></div></div>` : "";
    const act = d && d.action && d.action.length ? `<div class="chips">
        ${d.action.map((a, i) => `<div class="chip">
          <span>${this._describeAction(a)}</span>
          <span class="x" data-del="a" data-i="${i}">×</span></div>`).join("")}</div>` : "";
    const canConfirm = !!(d && d.name && d.action && d.action.length);
    return `
      <div class="create">
        <div class="field">
          <input class="nameinput" id="tname" placeholder="任务名称"
            value="${d && d.name ? d.name : ""}" aria-label="任务名称">
        </div>
        <div class="field">
          <div class="lbl">如果</div>
          <div class="hint">发生以下情况时，任务将自动运行。不添加时，任务将手动运行</div>
          ${trg || `<div class="addbox" id="addtrg" role="button" tabindex="0">
            <div class="p">＋</div><div class="t">添加</div></div>`}
        </div>
        <div class="field">
          <div class="lbl">就执行</div>
          <div class="hint">执行哪些操作？</div>
          ${act || `<div class="addbox" id="addact" role="button" tabindex="0">
            <div class="p">＋</div><div class="t">添加</div></div>`}
        </div>
        <div class="confirm${canConfirm ? "" : " dis"}" id="confirm"
          role="button" tabindex="0">确定</div>
      </div>`;
  }

  _bindCreate() {
    if (!this._draft) this._draft = { name: "", trigger: null, action: [] };
    const nm = this.querySelector("#tname");
    if (nm) nm.addEventListener("input", (e) => { this._draft.name = e.target.value; });

    const at = this.querySelector("#addtrg");
    if (at) { const a = () => this._pickTrigger();
      this._a11y(at, "添加触发条件", a); at.addEventListener("click", a); }
    const aa = this.querySelector("#addact");
    if (aa) { const a = () => this._pickAction();
      this._a11y(aa, "添加操作", a); aa.addEventListener("click", a); }

    this.querySelectorAll("[data-del]").forEach(x => {
      const a = () => {
        if (x.dataset.del === "t") this._draft.trigger = null;
        else this._draft.action.splice(Number(x.dataset.i), 1);
        this._render();
      };
      this._a11y(x, "删除", a); x.addEventListener("click", a);
    });

    const cf = this.querySelector("#confirm");
    if (cf) {
      const a = () => {
        if (cf.className.includes("dis")) {
          this._toast("请填写任务名称并至少添加一个操作", "err"); return;
        }
        this._save();
      };
      this._a11y(cf, "确定", a); cf.addEventListener("click", a);
    }
  }

  _describeTrigger(t) {
    if (t.platform === "state") {
      const s = this._hass && this._hass.states[t.entity_id];
      const nm = s ? (s.attributes.friendly_name || t.entity_id) : t.entity_id;
      return `${nm} 变为「${t.to}」${t.for ? " 持续 " + this._forText(t.for) : ""}`;
    }
    if (t.platform === "numeric_state") {
      const s = this._hass && this._hass.states[t.entity_id];
      const nm = s ? (s.attributes.friendly_name || t.entity_id) : t.entity_id;
      const cmp = t.above != null ? `高于 ${t.above}` : `低于 ${t.below}`;
      return `${nm} ${cmp}`;
    }
    if (t.platform === "time") return `每天 ${t.at}`;
    return JSON.stringify(t).slice(0, 40);
  }
  _forText(f) {
    const m = String(f).match(/(\d+):(\d+):(\d+)/);
    if (!m) return f;
    const h = +m[1], mi = +m[2];
    return h ? `${h} 小时` : `${mi} 分钟`;
  }
  _describeAction(a) {
    const svc = a.service || "";
    const tgt = (a.target && a.target.entity_id) || (a.data && a.data.entity_id) || "";
    const s = this._hass && this._hass.states[tgt];
    const nm = s ? (s.attributes.friendly_name || tgt) : tgt;
    const MAP = { "climate.turn_on": "开启空调", "climate.turn_off": "关闭空调",
      "switch.turn_on": "开启", "switch.turn_off": "关闭",
      "cover.close_cover": "关闭", "cover.open_cover": "打开",
      "lock.lock": "上锁", "lock.unlock": "解锁",
      "persistent_notification.create": "发送通知" };
    return `${svc} ${MAP[svc] ? "（" + MAP[svc] + "）" : ""} ${nm}`.trim();
  }

  /** 触发条件选择（简化为常用几项） */
  async _pickTrigger() {
    const OPTS = [
      { label: "驻车后", t: { platform: "state", entity_id: this._eid("status"), to: "已驻车（P 档）", for: "00:05:00" } },
      { label: "开始行驶", t: { platform: "state", entity_id: this._eid("status"), to: "行驶中" } },
      { label: "车辆上锁", t: { platform: "state", entity_id: this._eid("lock"), to: "locked" } },
      { label: "电量低于 20%", t: { platform: "numeric_state", entity_id: this._eid("battery"), below: 20 } },
      { label: "车内温度高于 30°C", t: { platform: "numeric_state", entity_id: this._eid("room_temp"), above: 30 } },
    ];
    const pick = await this._choose("选择触发条件", OPTS.map(o => o.label));
    if (pick == null) return;
    this._draft.trigger = OPTS[pick].t;
    this._render();
  }

  async _pickAction() {
    const act = this._eid("ac"), lock = this._eid("lock"), sentry = this._eid("sentry");
    const OPTS = [
      { label: "开启空调", a: act ? { service: "climate.turn_on", target: { entity_id: act } } : null },
      { label: "关闭空调", a: act ? { service: "climate.turn_off", target: { entity_id: act } } : null },
      { label: "开启哨兵模式", a: sentry ? { service: "switch.turn_on", target: { entity_id: sentry } } : null },
      { label: "关闭哨兵模式", a: sentry ? { service: "switch.turn_off", target: { entity_id: sentry } } : null },
      { label: "车辆上锁", a: lock ? { service: "lock.lock", target: { entity_id: lock } } : null },
      { label: "发送通知", a: { service: "persistent_notification.create",
          data: { title: "理想 L6", message: "任务已触发" } } },
    ].filter(o => o.a);
    const pick = await this._choose("选择操作", OPTS.map(o => o.label));
    if (pick == null) return;
    this._draft.action.push(OPTS[pick].a);
    this._render();
  }

  /** 轻量选择器（替代 window.prompt —— 后者在 HA 里体验差） */
  _choose(title, labels) {
    return new Promise((resolve) => {
      const ov = document.createElement("div");
      ov.style.cssText = `position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:20;
        display:flex;align-items:flex-end;justify-content:center;`;
      const sheet = document.createElement("div");
      sheet.style.cssText = `background:var(--lx-bg);color:var(--lx-t1);width:100%;
        max-width:460px;border-radius:20px 20px 0 0;padding:18px 0 26px;
        font-family:inherit;max-height:70vh;overflow:auto;`;
      sheet.innerHTML = `<div style="font-size:16px;font-weight:500;padding:0 20px 14px">${title}</div>`
        + labels.map((l, i) => `<div data-i="${i}" style="padding:15px 20px;
            font-size:15px;border-top:1px solid var(--lx-line);cursor:pointer">${l}</div>`).join("")
        + `<div id="cx" style="padding:15px 20px;font-size:15px;color:var(--lx-t3);
            border-top:8px solid var(--lx-card);cursor:pointer;text-align:center">取消</div>`;
      const close = (v) => { ov.remove(); resolve(v); };
      sheet.querySelectorAll("[data-i]").forEach(el => {
        const i = Number(el.dataset.i);
        const a = () => close(i);
        this._a11y(el, labels[i], a);
        el.addEventListener("click", a);
      });
      const cx = sheet.querySelector("#cx");
      const ca = () => close(null);
      this._a11y(cx, "取消", ca);
      cx.addEventListener("click", ca);
      ov.appendChild(sheet);
      ov.addEventListener("click", (e) => { if (e.target === ov) close(null); });
      this.appendChild(ov);
    });
  }

  async _applyPreset(p) {
    const id = "lx_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    const cfg = {
      alias: p.name, description: p.desc,
      trigger: [p.trigger], action: p.action, mode: "single",
    };
    try {
      await this._saveCfg(id, cfg);
      this._toast(`已创建「${p.name}」`, "ok", 3200);
      this._tab = "mine"; this._render();
    } catch (e) {
      this._toast("创建失败：" + ((e && e.message) || "未知"), "err", 4000);
    }
  }

  async _save() {
    const d = this._draft;
    const id = "lx_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    const cfg = { alias: d.name, trigger: d.trigger ? [d.trigger] : [], action: d.action, mode: "single" };
    try {
      await this._saveCfg(id, cfg);
      this._toast(`已创建「${d.name}」`, "ok", 3200);
      this._draft = null;
      this._tab = "mine"; this._render();
    } catch (e) {
      this._toast("创建失败：" + ((e && e.message) || "未知"), "err", 4000);
    }
  }

  async _saveCfg(id, cfg) {
    const h = this._hass;
    const tok = h.auth && h.auth.data ? h.auth.data.access_token : null;
    const res = await fetch(`/api/config/automation/config/${id}`, {
      method: "POST",
      headers: Object.assign({ "Content-Type": "application/json" },
        tok ? { Authorization: "Bearer " + tok } : {}),
      body: JSON.stringify(cfg),
    });
    if (!res.ok) {
      const t = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} ${t.slice(0,80)}`);
    }
    return res.json().catch(() => ({}));
  }

  _update() {
    if (!this._built) return;
    // 首屏与切换 tab 时重绘（保持输入内容：create 页由 _draft 承载）
    this._render();
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangTaskPage);
window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TAG,
  name: "任务大师（HA 版）",
  description: "用 App 的交互创建 HA 自动化：模板库 + 如果/就执行 + 我的任务",
  preview: true,
});
