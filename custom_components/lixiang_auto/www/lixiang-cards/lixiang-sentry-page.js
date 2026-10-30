// —— 图标回退（内置资源）——
const __lxIconFallback = (typeof window !== "undefined" && (window.__lxIconFallback = window.__lxIconFallback || function (img) {
  if (img.dataset.lxFb) return;
  img.dataset.lxFb = "1";
  const s = img.getAttribute("src") || "";
  const rel = s.replace(/^\/local\/lixiang-icons\//, "");
  if (rel === s) return;
  img.src = "/lixiang_auto/lixiang-icons/" + rel;
})) || function (img) {};

/**
 * lixiang-sentry-page —— 哨兵视频（二级页，从车控首页「哨兵模式」卡进入）
 *
 * 数据链路（2026-10-28，接口规格由 L7 车主实测 + APK RN bundle 反编译互证）：
 *   ① lixiang_auto.get_sentinel_videos  → 近 7 天事件列表
 *        eventId / startTs(ms) / status / videos:[{coverFilekey, eventDirection, videoFilekey}]
 *   ② lixiang_auto.get_file_urls        → filekey 换有时效的签名 URL
 *   ③ 封面用 coverFilekey，视频用 videoFilekey（点击时才换，不预加载）
 *
 * ⚠️ 硬限制：官方视频是 **H.265 / 1920×1536 / 约 20s / 7MB**
 *   Safari 能直接播；Chrome 桌面多数不能（看硬件解码）；Firefox 不支持。
 *   因此不做"黑屏 video"，而是先探测 canPlayType，不支持就给「下载观看」。
 */

const CARD_TAG = "lixiang-sentry-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";
let __iconBase = DEFAULT_ICON_BASE;
const __iconFallback = BUILTIN_ICON_BASE;

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询**）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase / __iconFallback 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const probe = new Image();
        probe.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach((f) => { try { f(); } catch (e) { /* 忽略 */ } });
        };
        probe.src = DEFAULT_ICON_BASE + "/ic_home_return_left.webp";
      }
    }
  }
}

// 统一导航助手（先问外壳，外壳不在则回退 HA 路由）
function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

/** eventDirection 编码 → 中文（未知就原样显示） */
const DIR_MAP = {
  FL: "左前", FR: "右前", BL: "左后", BR: "右后",
  F: "前方", R: "后方", L: "左侧", RT: "右侧",
  FRONT: "前方", REAR: "后方", LEFT: "左侧", RIGHT: "右侧",
  "1": "前方", "2": "后方", "3": "左侧", "4": "右侧",
};

const STYLE = `
  .root { display:block; font-family:"Licium",-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
          color:var(--lx-t1,#1A1A1A); background:var(--lx-bg,#FFF); }
  * { box-sizing:border-box; }
  .topbar { display:flex; align-items:center; gap:10px; padding:14px 16px 10px; }
  .back { width:32px; height:32px; display:flex; align-items:center; justify-content:center;
          cursor:pointer; border-radius:10px; -webkit-tap-highlight-color:transparent; }
  .back:hover { background:var(--lx-card,#F7F7F9); }
  .back img { width:18px; height:18px; opacity:.7; }
  h1 { font-size:17px; font-weight:600; margin:0; }
  .sw { margin-left:10px; flex:0 0 auto; border:none; cursor:pointer;
        background:var(--lx-card,#F7F7F9); color:var(--lx-t2,#666);
        font-size:12px; padding:6px 12px; border-radius:10px; font-family:inherit; }
  .sw.on { background:rgba(10,88,246,.10); color:var(--lx-blue,#0A58F6); }
  .sw:disabled { opacity:.5; cursor:default; }
  .sub { margin-left:auto; font-size:12px; color:var(--lx-t3,#9A9A9A); }

  .body { padding:0 16px 24px; }
  .hint { font-size:12px; color:var(--lx-t3,#9A9A9A); line-height:1.7;
          background:var(--lx-card,#F7F7F9); border-radius:12px; padding:10px 12px; margin-bottom:12px; }
  .hint b { color:var(--lx-t2,#666); font-weight:600; }

  .state { padding:40px 16px; text-align:center; font-size:13px; color:var(--lx-t3,#9A9A9A); }
  .state.err { color:var(--lx-red,#FF3B30); }
  .state button { margin-top:12px; padding:8px 18px; border-radius:10px; border:none;
                  background:var(--lx-blue,#0A58F6); color:#fff; font-size:13px; cursor:pointer; }

  .list { display:grid; gap:12px; }
  .ev { background:var(--lx-card,#F7F7F9); border-radius:16px; overflow:hidden; }
  .ev-top { display:flex; align-items:center; gap:10px; padding:12px 14px; }
  .ev-ic { width:22px; height:22px; flex:0 0 auto; opacity:.75; }
  .ev-meta { min-width:0; flex:1; }
  .ev-time { font-size:14px; font-weight:600; }
  .ev-dir { font-size:12px; color:var(--lx-t3,#9A9A9A); margin-top:2px; }
  .ev-tag { font-size:11px; padding:2px 8px; border-radius:8px;
            background:rgba(10,88,246,.10); color:var(--lx-blue,#0A58F6); flex:0 0 auto; }

  .thumbs { display:flex; gap:8px; padding:0 14px 12px; overflow-x:auto; }
  .thumb { position:relative; flex:0 0 auto; width:132px; height:88px; border-radius:12px;
           overflow:hidden; background:#00000010; cursor:pointer; }
  .thumb img { width:100%; height:100%; object-fit:cover; display:block; }
  .thumb .ph { width:100%; height:100%; display:flex; align-items:center; justify-content:center;
               font-size:11px; color:var(--lx-t3,#9A9A9A); }
  .thumb .play { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; }
  .thumb .play i { width:34px; height:34px; border-radius:50%; background:rgba(0,0,0,.45);
                   display:flex; align-items:center; justify-content:center; }
  .thumb .play i::after { content:""; width:0; height:0; margin-left:3px;
                   border-left:11px solid #fff; border-top:7px solid transparent; border-bottom:7px solid transparent; }
  .thumb .dir { position:absolute; left:6px; bottom:6px; font-size:11px; color:#fff;
                background:rgba(0,0,0,.45); padding:1px 7px; border-radius:7px; }

  .player { padding:0 14px 14px; }
  .player video { width:100%; border-radius:12px; background:#000; display:block; }
  .fallback { display:flex; flex-direction:column; gap:8px; padding:12px; border-radius:12px;
              background:#FFFFFF; font-size:12px; color:var(--lx-t2,#666); line-height:1.6; }
  .fallback a { display:inline-block; padding:9px 16px; border-radius:10px; text-decoration:none;
                background:var(--lx-blue,#0A58F6); color:#fff; font-size:13px; text-align:center; }
  .close { font-size:12px; color:var(--lx-t3,#9A9A9A); text-align:right; cursor:pointer; }
`;

class LixiangSentryPage extends HTMLElement {
  constructor() {
    super();
    this._config = {};
    this._built = false;
    this._data = null;          // {count, events} 或 {error}
    this._loading = false;
    this._urlCache = {};        // filekey → 签名 URL（本次会话内复用）
    this._openKey = null;       // 当前展开播放的 filekey
  }

  setConfig(c) {
    this._config = c || {};
    if (this._config.icon_base) __iconBase = String(this._config.icon_base).replace(/\/+$/, "");
    if (this._built && this._hass) this._load();
  }

  set hass(h) {
    const first = !this._hass;
    this._hass = h;
    if (!this._built) this._build();
    else {
      this._syncSentry();
      if (first) this._load();
    }
  }
  get hass() { return this._hass; }

  _build() {
    if (this._built) return;
    this._built = true;
    const root = document.createElement("div");
    root.className = "root";
    root.innerHTML = `
      <style>${STYLE}</style>
      <div class="topbar">
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return_left.webp" onerror="__lxIconFallback(this)" alt=""></div>
        <h1>哨兵视频</h1>
        <span class="sub" id="sub"></span>
        <button type="button" class="sw" id="sw" aria-label="切换哨兵模式">
          <span id="sw-t">哨兵 —</span>
        </button>
      </div>
      <div class="body">
        <div class="hint" id="hint" style="display:none"></div>
        <div id="content"><div class="state">正在加载…</div></div>
      </div>`;
    this.appendChild(root);
    this._root = root;

    const back = root.querySelector("#back");
    const goBack = () => lxNavigate(this, this._config.back || "/lixiang/app");
    back.addEventListener("click", goBack);
    back.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); goBack(); }
    });

    const sw = root.querySelector("#sw");
    if (sw) sw.addEventListener("click", () => this._toggleSentry());
    this._syncSentry();

    this._load();
  }

  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try {
      const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config || {}).resolve() || {};
    } catch (e) { /* 绑定失败不影响视频列表 */ }
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }

  _eid(f) {
    const m = (this._config || {})[f];
    if (typeof m === "string" && m.includes(".")) return m;
    return (this._autoBind() || {})[f] || null;
  }

  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }

  /** 哨兵开关：复用首页同一套绑定（sentry → switch 实体） */
  _syncSentry() {
    const btn = this._root && this._root.querySelector("#sw");
    const txt = this._root && this._root.querySelector("#sw-t");
    if (!btn || !txt) return;
    const eid = this._eid("sentry");
    if (!eid) { btn.style.display = "none"; return; }
    btn.style.display = "";
    const st = this._st(eid);
    const on = Boolean(st) && String(st.state) === "on";
    btn.classList.toggle("on", on);
    txt.textContent = on ? "哨兵 已开" : "哨兵 已关";
  }

  async _toggleSentry() {
    const eid = this._eid("sentry");
    if (!eid) return;
    const st = this._st(eid);
    const on = Boolean(st) && String(st.state) === "on";
    try {
      await this._hass.callService("switch", on ? "turn_off" : "turn_on",
        { entity_id: eid });
    } catch (e) {
      console.warn("[sentry] 切换失败", e);
    }
  }

  /** 拉事件列表 */
  async _load() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    this._render({ state: "loading" });
    try {
      const res = await this._hass.callService(
        "lixiang_auto", "get_sentinel_videos",
        { limit: Number(this._config.limit) || 20 },
        undefined, true, true,
      );
      // HA callService 的响应包装为 {response: {VIN: {count, events}}}；
      // 单 VIN 时 response 内再解一层，多 VIN 时先选对应 VIN。
      const outer = (res && res.response) || res;
      let payload = null;
      if (outer && typeof outer === "object") {
        const vin = this._config.vin;
        if (vin && outer[vin] && typeof outer[vin] === "object") {
          payload = outer[vin];
        } else if ("count" in outer || "events" in outer || "error" in outer) {
          payload = outer;
        } else {
          const values = Object.values(outer).filter(x => x && typeof x === "object");
          if (values.length) payload = values[0];
        }
      }
      this._data = payload || { error: "未取到数据" };
    } catch (e) {
      this._data = { error: (e && e.message) || "调用服务失败" };
    }
    this._loading = false;
    this._render({ state: "done" });
  }

  _render() {
    const content = this._root.querySelector("#content");
    const sub = this._root.querySelector("#sub");
    const hint = this._root.querySelector("#hint");
    const d = this._data;

    if (!d) { content.innerHTML = '<div class="state">正在加载…</div>'; return; }
    if (d.error) {
      sub.textContent = "";
      hint.style.display = "none";
      content.innerHTML = `<div class="state err">加载失败：${this._esc(d.error)}
        <div><button id="retry">重试</button></div></div>`;
      const b = content.querySelector("#retry");
      if (b) b.addEventListener("click", () => this._load());
      return;
    }

    const events = Array.isArray(d.events) ? d.events : [];
    sub.textContent = events.length ? `共 ${events.length} 条` : "";

    // H.265 兼容提示（只在首次展示列表时给一次，避免干扰）
    const hevcOk = this._canHevc();
    if (!hevcOk && events.length) {
      hint.style.display = "";
      hint.innerHTML = "当前浏览器<b>不支持 H.265</b>，视频将提供「下载观看」。";
    } else {
      hint.style.display = "none";
    }

    if (!events.length) {
      content.innerHTML = '<div class="state">近 7 天没有哨兵视频</div>';
      return;
    }

    content.innerHTML = '<div class="list">' + events.map((ev, i) => {
      const t = this._fmtTs(ev.startTs);
      const vids = Array.isArray(ev.videos) ? ev.videos : [];
      const thumbs = vids.map((v, j) => {
        const key = v.videoFilekey || "";
        const dir = this._dirText(v.eventDirection);
        return `<div class="thumb" data-i="${i}" data-j="${j}" role="button" tabindex="0"
                     aria-label="播放 ${this._esc(dir)}">
          <div class="ph" data-cover="${this._esc(v.coverFilekey || "")}">封面加载中…</div>
          <div class="play"><i></i></div>
          ${dir ? `<span class="dir">${this._esc(dir)}</span>` : ""}
        </div>`;
      }).join("");
      return `<div class="ev">
        <div class="ev-top">
          <img class="ev-ic" src="${__iconBase}/ic_home_sentry.png" onerror="this.style.visibility='hidden'" alt="">
          <div class="ev-meta">
            <div class="ev-time">${this._esc(t)}</div>
            <div class="ev-dir">${vids.length} 个视角</div>
          </div>
          ${ev.status === 0 ? '<span class="ev-tag">上传中</span>' : ""}
        </div>
        <div class="thumbs">${thumbs}</div>
        <div class="player" id="pl-${i}"></div>
      </div>`;
    }).join("") + "</div>";

    // 封面：批量换 URL 后填 img
    this._fillCovers(content);
    // 点击缩略图 → 播放
    content.querySelectorAll(".thumb").forEach((el) => {
      const open = () => this._open(Number(el.dataset.i), Number(el.dataset.j));
      el.addEventListener("click", open);
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
      });
    });
  }

  /** 批量把 coverFilekey 换成签名 URL 并填进缩略图 */
  async _fillCovers(content) {
    const phs = Array.from(content.querySelectorAll(".ph"));
    const keys = phs.map((p) => p.dataset.cover).filter(Boolean);
    if (!keys.length) {
      phs.forEach((p) => { p.textContent = "无封面"; });
      return;
    }
    const urls = await this._urlsOf(keys);
    phs.forEach((p) => {
      const k = p.dataset.cover;
      const u = k && urls[k];
      if (!u) { p.textContent = "无封面"; return; }
      const img = document.createElement("img");
      img.alt = "";
      img.onerror = () => { p.textContent = "封面加载失败"; };
      img.src = u;
      p.replaceWith(img);
    });
  }

  /** 换一个或多个 filekey 的签名 URL（带会话内缓存） */
  async _urlsOf(keys) {
    const out = {};
    const need = [];
    keys.forEach((k) => {
      if (!k) return;
      if (this._urlCache[k]) out[k] = this._urlCache[k];
      else need.push(k);
    });
    if (!need.length) return out;
    try {
      const res = await this._hass.callService(
        "lixiang_auto", "get_file_urls", { file_keys: need.join(",") },
        undefined, true, true,
      );
      const outer = (res && res.response) || res;
      let payload = null;
      if (outer && typeof outer === "object") {
        const vin = this._config.vin;
        if (vin && outer[vin] && typeof outer[vin] === "object") payload = outer[vin];
        else if ("urls" in outer) payload = outer;
        else {
          const values = Object.values(outer).filter(x => x && typeof x === "object");
          if (values.length) payload = values[0];
        }
      }
      const urls = (payload && payload.urls) || {};
      Object.keys(urls).forEach((k) => {
        if (urls[k]) { out[k] = urls[k]; this._urlCache[k] = urls[k]; }
      });
    } catch (e) {
      // 换链失败不影响列表展示
      console.warn("[sentry] 换签名链接失败", e);
    }
    return out;
  }

  /** 打开某个视频：能播就内联播，不能播给下载 */
  async _open(i, j) {
    const ev = (this._data && this._data.events || [])[i];
    const v = ev && (ev.videos || [])[j];
    if (!v) return;
    const box = this._root.querySelector("#pl-" + i);
    if (!box) return;
    if (this._openKey === v.videoFilekey) {       // 再点一次收起
      box.innerHTML = "";
      this._openKey = null;
      return;
    }
    this._openKey = v.videoFilekey;
    box.innerHTML = '<div class="state" style="padding:16px">正在获取视频…</div>';
    const urls = await this._urlsOf([v.videoFilekey]);
    const url = urls[v.videoFilekey];
    if (!url) {
      box.innerHTML = '<div class="fallback">获取视频链接失败，请稍后重试。</div>';
      return;
    }
    if (this._canHevc()) {
      box.innerHTML = '<video controls playsinline preload="metadata"></video>' +
        '<div class="close" role="button" tabindex="0">收起</div>';
      const video = box.querySelector("video");
      video.src = url;
      video.onerror = () => {
        box.innerHTML = this._fallbackHtml(url);
        this._wireFallback(box);
      };
    } else {
      box.innerHTML = this._fallbackHtml(url);
    }
    this._wireFallback(box);
  }

  _fallbackHtml(url) {
    return `<div class="fallback">
      当前浏览器不支持 H.265 编码，无法内联播放。
      <a href="${this._esc(url)}" target="_blank" rel="noopener" download>下载观看</a>
      <div class="close" role="button" tabindex="0">收起</div>
    </div>`;
  }

  _wireFallback(box) {
    box.querySelectorAll(".close").forEach((el) => {
      const close = () => { box.innerHTML = ""; this._openKey = null; };
      el.addEventListener("click", close);
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); close(); }
      });
    });
  }

  /** 浏览器能否解 H.265（Safari 可以，多数 Chrome 桌面不行，Firefox 不支持） */
  _canHevc() {
    try {
      const v = document.createElement("video");
      return Boolean(
        v.canPlayType('video/mp4; codecs="hvc1"') ||
        v.canPlayType('video/mp4; codecs="hev1"')
      );
    } catch (e) { return false; }
  }

  _dirText(d) {
    if (!d) return "";
    const k = String(d).toUpperCase().replace(/[^A-Z0-9]/g, "");
    return DIR_MAP[k] || String(d);
  }

  _fmtTs(ms) {
    const n = Number(ms);
    if (!Number.isFinite(n) || n <= 0) return "时间未知";
    const d = new Date(n);
    const p = (x) => String(x).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} `
      + `${p(d.getHours())}:${p(d.getMinutes())}`;
  }

  _esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  getCardSize() { return 12; }

  static getStubConfig() { return {}; }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangSentryPage);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c && c.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "理想汽车 · 哨兵视频",
    description: "查看近 7 天哨兵视频事件（只读）",
    preview: false,
  });
}
