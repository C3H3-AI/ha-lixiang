/**
 * lixiang-location-page —— 车辆位置（二级页，对齐 App）
 *
 * App 实测结构（截图 1260×2844 @3x）：
 *   地图占 64%，车辆图标居中，左下「闪灯/鸣笛」浮动按钮
 *   地址卡：完整地址 + 距您 xx m + 导航按钮
 *   驻车照片：3 路（俯视/前/后）+ 时间 + 重新拍照
 *
 * 实体：
 *   device_tracker.车辆位置（lat/lon）
 *   button.闪灯 / 鸣笛 / 远程拍照
 *   sensor.360 拍照状态 / 拍照信息
 *
 * 能力边界：
 *   ⚠️ 驻车照片图片本身不在集成里（只有状态），需 App 查看
 *   ✅ 闪灯/鸣笛/拍照 可触发
 */

const CARD_TAG = "lixiang-location-page";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
let __fontBase = DEFAULT_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("${__fontBase}/roboto_medium_numbers.ttf"); font-display:swap; }
  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  .root { background:var(--lx-bg); color:var(--lx-t1); padding-bottom:20px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }

  /* ── 地图区 ── */
  .mapwrap { position:relative; height:340px; background:#E8EEF4; overflow:hidden; }
  .mapwrap iframe { width:100%; height:100%; border:0; }
  .mapwrap .ph { position:absolute; inset:0; display:flex; flex-direction:column;
                 align-items:center; justify-content:center; gap:10px;
                 font-size:12.5px; color:var(--lx-t3); text-align:center; padding:0 30px; }
  .mapwrap .ph .car { width:44px; height:62px; }
  .back { position:absolute; left:14px; top:14px; width:38px; height:38px;
          border-radius:50%; background:rgba(255,255,255,.95); display:flex;
          align-items:center; justify-content:center; cursor:pointer; z-index:3;
          box-shadow:0 1px 5px rgba(0,0,0,.12); }
  .back img { width:19px; height:19px; opacity:.75; }
  /* 浮动按钮 */
  .floats { position:absolute; left:14px; bottom:14px; display:flex; gap:9px; z-index:3; }
  .fbtn { display:inline-flex; align-items:center; gap:6px; font-size:13px;
          padding:9px 15px; border-radius:22px; background:rgba(255,255,255,.97);
          box-shadow:0 2px 8px rgba(0,0,0,.13); cursor:pointer;
          transition:transform .13s; white-space:nowrap; }
  .fbtn:active { transform:scale(.94); }
  .fbtn img { width:17px; height:17px; }
  .fbtn.busy { opacity:.55; }

  /* ── 地址卡 ── */
  .addr { padding:16px 20px 14px; display:flex; align-items:flex-start; gap:12px; }
  .addr .tx { flex:1; min-width:0; }
  .addr .a { font-size:16px; font-weight:500; line-height:1.4; }
  .addr .d { font-size:13px; color:var(--lx-t3); margin-top:6px; }
  .nav { width:46px; height:46px; border-radius:50%; background:var(--lx-card);
         display:flex; align-items:center; justify-content:center; cursor:pointer;
         flex:0 0 auto; transition:transform .13s; }
  .nav:active { transform:scale(.92); }
  .nav img { width:22px; height:22px; }

  /* ── 驻车照片 ── */
  .sec { padding:12px 0 0; border-top:8px solid var(--lx-card); }
  .sechd { display:flex; align-items:center; gap:10px; padding:14px 20px 10px; }
  .sechd .t { font-size:16px; font-weight:500; }
  .sechd .ts { font-size:12.5px; color:var(--lx-t3); margin-top:3px; }
  .sechd .ra { margin-left:auto; display:inline-flex; align-items:center; gap:6px;
               font-size:13px; padding:8px 14px; border-radius:20px;
               background:var(--lx-card); cursor:pointer; }
  .sechd .ra img { width:16px; height:16px; }
  .photos { display:flex; gap:10px; padding:0 20px 6px; overflow-x:auto;
            scrollbar-width:none; }
  .photos::-webkit-scrollbar { display:none; }
  .ph { flex:0 0 auto; width:150px; height:100px; border-radius:12px;
        background:#2A2A2E; position:relative; overflow:hidden;
        display:flex; align-items:flex-end; }
  .ph img { width:100%; height:100%; object-fit:cover; }
  .ph .lbl { position:absolute; left:8px; top:8px; font-size:11px; color:#fff;
             background:rgba(0,0,0,.45); padding:2px 7px; border-radius:6px; }
  .ph .none { position:absolute; inset:0; display:flex; align-items:center;
              justify-content:center; font-size:11px; color:rgba(255,255,255,.5);
              text-align:center; padding:0 10px; line-height:1.5; }
  .tip { padding:10px 20px 0; font-size:11.5px; color:var(--lx-t3); line-height:1.6; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9; }
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

class LixiangLocationPage extends HTMLElement {
  setConfig(c) { this._config = c || {}; this._busy = {}; this._built = false; }
  set hass(h) { this._hass = h; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 18; }
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
  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
  _txt(id) { const s = this._st(id);
             return (s && !["unknown","unavailable"].includes(s.state)) ? s.state : null; }

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
    root.className = "root";
    root.innerHTML = `
      <div class="mapwrap" id="mapwrap">
        <div class="ph" id="mapph">
          <img class="car" src="${__iconBase}/icon_car_loc.webp" alt="">
          <div id="coords">定位获取中…</div>
        </div>
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return.webp" alt=""></div>
        <div class="floats">
          <div class="fbtn" id="btn-flash" role="button" tabindex="0" aria-label="闪灯">
            <img src="${__iconBase}/ic_home_lightning.png" alt="" onerror="this.style.visibility='hidden'">闪灯</div>
          <div class="fbtn" id="btn-horn" role="button" tabindex="0" aria-label="鸣笛">
            <img src="${__iconBase}/ic_home_dialogue.png" alt="" onerror="this.style.visibility='hidden'">鸣笛</div>
        </div>
      </div>

      <div class="addr">
        <div class="tx">
          <div class="a" id="v-addr">地址获取中…</div>
          <div class="d" id="v-dist"></div>
        </div>
        <div class="nav" id="btn-nav" role="button" tabindex="0" aria-label="导航到车辆">
          <img src="${__iconBase}/ic_home_navigation.webp" alt=""></div>
      </div>

      <div class="sec">
        <div class="sechd">
          <div><div class="t">驻车照片</div><div class="ts" id="v-photots">—</div></div>
          <div class="ra" id="btn-photo" role="button" tabindex="0" aria-label="重新拍照">
            <img src="${__iconBase}/ic_home_photo.png" alt="" onerror="this.style.visibility='hidden'">重新拍照</div>
        </div>
        <div class="photos" id="photos"></div>
        <div class="tip">驻车照片由车辆摄像头拍摄。集成当前只能触发拍照与读取状态，
          图片本身需在理想 App 中查看。</div>
      </div>
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

    const flash = () => this._press("btn_flash", "闪灯");
    const horn = () => this._press("btn_horn", "鸣笛");
    const photo = () => this._press("btn_photo", "远程拍照");
    [["#btn-flash", flash, "闪灯"], ["#btn-horn", horn, "鸣笛"],
     ["#btn-photo", photo, "重新拍照"]].forEach(([sel, fn, label]) => {
      const el = this.querySelector(sel); if (!el) return;
      this._a11y(el, label, fn);
      el.addEventListener("click", fn);
    });

    // 导航
    const nav = () => {
      const dt = this._st(this._eid("tracker"));
      const la = dt && dt.attributes.latitude, lo = dt && dt.attributes.longitude;
      if (la == null || lo == null) { this._toast("暂无定位", "err"); return; }
      // 用系统地图 URL scheme（手机端可唤起）
      const url = `https://uri.amap.com/marker?position=${lo},${la}&name=我的车`;
      window.open(url, "_blank");
    };
    this._a11y(this.querySelector("#btn-nav"), "导航到车辆", nav);
    this.querySelector("#btn-nav").addEventListener("click", nav);

    this._built = true;
  }

  _toast(msg, kind) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, 2400);
  }

  async _press(field, label) {
    const eid = this._eid(field);
    if (!eid) { this._toast(`${label} 未接入`, "err"); return; }
    if (this._busy[field]) return;
    this._busy[field] = true;
    const el = this.querySelector(field === "btn_flash" ? "#btn-flash"
              : (field === "btn_horn" ? "#btn-horn" : "#btn-photo"));
    if (el) el.classList.add("busy");
    try {
      await this._hass.callService("button", "press", { entity_id: eid });
      this._toast(`${label} 已触发`, "ok");
    } catch (e) {
      this._toast(`${label} 失败：${(e && e.message) || "未知"}`, "err");
    } finally {
      delete this._busy[field];
      if (el) el.classList.remove("busy");
    }
  }

  _update() {
    if (!this._built) return;
    const q = s => this.querySelector(s);

    // 定位
    const dt = this._st(this._eid("tracker"));
    const la = dt && dt.attributes.latitude, lo = dt && dt.attributes.longitude;
    const coords = q("#coords");
    if (la != null && lo != null) {
      coords.textContent = `${Number(la).toFixed(5)}, ${Number(lo).toFixed(5)}`;
      const wrap = q("#mapwrap");
      // 若配置了地图 iframe 则嵌入；否则显示静态坐标 + 车辆图标
      if (this._config.map_iframe && !wrap.dataset.done) {
        const f = document.createElement("iframe");
        f.src = this._config.map_iframe
          .replace("{lat}", la).replace("{lon}", lo);
        f.title = "车辆地图";
        wrap.insertBefore(f, wrap.firstChild);
        wrap.dataset.done = "1";
      }
    } else {
      coords.textContent = "暂无定位（车辆可能离线）";
    }

    // 地址（HA 无反向地理编码时显示坐标 + 提示）
    const addrState = this._txt(this._eid("address"));
    const addrEl = q("#v-addr");
    if (dt && dt.attributes.address) addrEl.textContent = dt.attributes.address;
    else if (addrState && !/^\d+$/.test(String(addrState))) addrEl.textContent = String(addrState);
    else if (la != null && lo != null) addrEl.textContent = `坐标 ${Number(la).toFixed(4)}, ${Number(lo).toFixed(4)}`;
    else addrEl.textContent = "地址不可用";

    // 距离（本机到车；浏览器定位不可用时隐藏）
    const distEl = q("#v-dist");
    if (this._myPos && la != null && lo != null) {
      const d = this._haversine(this._myPos[0], this._myPos[1], la, lo);
      distEl.textContent = d < 1000 ? `距您 ${Math.round(d)}m` : `距您 ${(d/1000).toFixed(1)}km`;
    } else distEl.textContent = "";

    // 拍照时间
    const info = this._txt(this._eid("photo_info"));
    const stt = this._txt(this._eid("photo_status"));
    q("#v-photots").textContent = info || stt || "暂无记录";

    // ★ 2026-10-03：驻车照片改为【真实图片】
    //   链路（抓包逆向）：VSS 拍照时间 → 构造 5 路 OSS key →
    //   lixiang_auto.get_svm_photo 换签名 URL → <img src>。
    //   URL 有时效，所以缓存 2 分钟（够一次浏览，又不至于显示过期图）。
    this._renderPhotos(q, info);
  }

  /** 渲染 5 路驻车照片（前/后/左/右/俯视）。 */
  async _renderPhotos(q, photoTime) {
    const box = q("#photos");
    if (!box) return;
    const ANGLES = [["Top", "俯视"], ["Front", "前"], ["Rear", "后"],
                    ["Left", "左"], ["Right", "右"]];

    // 首次：占位骨架（避免空白闪烁）
    if (!box.dataset.init) {
      box.dataset.init = "1";
      box.innerHTML = ANGLES.map(([k, lbl]) =>
        `<div class="ph" data-a="${k}"><div class="none">${lbl}视图<br>加载中…</div>
         <div class="lbl">${lbl}</div></div>`).join("");
    }

    const stamp = String(photoTime || "");
    const now = Date.now();
    if (this._phCache && this._phCache.stamp === stamp &&
        now - this._phCache.at < 120000) {
      this._paintPhotos(box, this._phCache.urls, ANGLES);
      return;
    }
    if (this._phBusy) return;
    this._phBusy = true;
    try {
      const res = await this._hass.callService(
        "lixiang_auto", "get_svm_photo",
        photoTime ? { time: photoTime } : {}, undefined, false, true);
      const payload = (res && (res.result || res.response)) || {};
      const first = Object.values(payload)[0] || {};
      const urls = first.urls || {};
      this._phCache = { stamp, urls, at: Date.now() };
      this._paintPhotos(box, urls, ANGLES, first.error);
    } catch (err) {
      this._paintPhotos(box, {}, ANGLES, String(err && err.message || err));
    } finally {
      this._phBusy = false;
    }
  }

  /** 把 URL 填进对应方位；缺失的显示原因而不是假装有图。 */
  _paintPhotos(box, urls, angles, err) {
    const list = Object.entries(urls || {});
    angles.forEach(([key, lbl]) => {
      const cell = box.querySelector(`.ph[data-a="${key}"]`);
      if (!cell) return;
      const hit = list.find(([k]) => k && k.includes(`picIn${key}.jpg`));
      if (hit) {
        cell.innerHTML = `<img src="${hit[1]}" alt="${lbl}视图" loading="lazy"
             style="width:100%;height:100%;object-fit:cover;border-radius:8px">
           <div class="lbl">${lbl}</div>`;
      } else {
        const why = err ? "获取失败" : (list.length ? "该方位无图" : "尚未拍照");
        cell.innerHTML = `<div class="none">${lbl}视图<br>（${why}）</div>
           <div class="lbl">${lbl}</div>`;
      }
    });
  }

  _haversine(lat1, lon1, lat2, lon2) {
    const R = 6371000, toRad = (x) => x * Math.PI / 180;
    const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat/2)**2 +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2)**2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangLocationPage);
window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TAG,
  name: "车辆位置（二级页）",
  description: "地图定位 + 地址 + 距离 + 闪灯/鸣笛 + 驻车照片入口",
  preview: true,
});
