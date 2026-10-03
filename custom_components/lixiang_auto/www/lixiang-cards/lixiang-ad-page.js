/**
 * lixiang-ad-page —— 智驾统计（二级页）
 *
 * 数据源（真实实体）：
 *   sensor.li_xiang_l6_fu_zhu_jia_shi_li_cheng   辅助驾驶里程
 *   sensor.li_xiang_l6_fu_zhu_jia_shi_tian_shu   辅助驾驶天数
 *   sensor.li_xiang_l6_noa_li_cheng              NOA 里程
 *   sensor.li_xiang_l6_lcc_li_cheng              LCC 里程
 *   sensor.li_xiang_l6_acc_li_cheng              ACC 里程
 *   sensor.li_xiang_l6_zong_li_cheng             总里程（算占比）
 */

const CARD_TAG = "lixiang-ad-page";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";
let __fontBase = DEFAULT_FONT_BASE;   // setConfig 可覆盖

const STYLE = `
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("${__fontBase}/roboto_medium_numbers.ttf"); font-display:swap; }
  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-purple:#7B61FF;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  .root { position:relative; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:18px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }
  .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
    --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }

  .topbar { display:flex; align-items:center; height:48px; padding:0 16px; }
  .back { width:24px; height:24px; opacity:.75; cursor:pointer; }
  .topbar h1 { font-size:17px; font-weight:500; margin:0; flex:1; text-align:center; }
  .topbar .r { min-width:56px; }

  /* 主卡：智驾里程 + 占比 */
  .hero { margin:6px 20px 0; border-radius:18px; padding:20px 18px;
          background:linear-gradient(155deg,var(--lx-card) 0%,var(--lx-bg) 100%); }
  .hero .lbl { font-size:12.5px; color:var(--lx-t3); }
  .hero .big { font-family:"LxNum","Licium"; font-size:38px; font-weight:600;
               line-height:1.1; margin-top:6px; }
  .hero .big small { font-size:16px; font-weight:500; color:var(--lx-t2); margin-left:4px; }
  .hero .sub { font-size:12.5px; color:var(--lx-t3); margin-top:8px; }
  .hero .bar { height:8px; border-radius:20px; background:var(--lx-line);
               overflow:hidden; margin-top:14px; display:flex; }
  .hero .bar i { display:block; height:100%; transition:width .5s; }

  /* 三栏明细 */
  .grid { display:grid; grid-template-columns:repeat(3,1fr); gap:11px; padding:14px 20px 0; }
  .g { background:var(--lx-card); border-radius:16px; padding:14px 12px; }
  .g .l { font-size:11.5px; color:var(--lx-t3); display:flex; align-items:center; gap:5px; }
  .g .l i { width:8px; height:8px; border-radius:50%; display:inline-block; }
  .g .v { font-family:"LxNum","Licium"; font-size:19px; font-weight:600; margin-top:6px; }
  .g .v small { font-size:10.5px; color:var(--lx-t2); margin-left:2px; }
  .g .p { font-size:11px; color:var(--lx-t3); margin-top:4px; }

  .sect { padding:18px 20px 0; }
  .sect h2 { font-size:14px; font-weight:500; margin:0 0 10px; }
  .row { display:flex; align-items:center; gap:12px; padding:13px 16px;
         background:var(--lx-card); border-radius:14px; margin-bottom:10px; }
  .row img { width:22px; height:22px; }
  .row .tx { flex:1; }
  .row .nm { font-size:14px; }
  .row .sd { font-size:11.5px; color:var(--lx-t3); margin-top:3px; }
  .row .val { font-family:"LxNum","Licium"; font-size:16px; font-weight:600; }

  /* 说明 */
  .note { margin:18px 20px 0; padding:14px; border-radius:12px;
          background:var(--lx-card); font-size:12px; color:var(--lx-t2);
          line-height:1.65; }
  .note b { color:var(--lx-t1); }
  .note .it { display:flex; gap:8px; margin-top:8px; }
  .note .it:first-child { margin-top:0; }
  .note .dot { color:var(--lx-blue); }

  /* ── 键盘可达：统一焦点样式（无障碍）── */
  [role="button"]:focus-visible, .card:focus-visible, .entry:focus-visible,
  .row.click:focus-visible, .m:focus-visible, .yhead:focus-visible,
  .year .yhead:focus-visible, button:focus-visible, input:focus-visible {
    outline: 2px solid var(--lx-blue, #0A58F6);
    outline-offset: 2px;
    border-radius: 8px;
  }
  /* 尊重「减少动态效果」偏好 */
  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: .01ms !important; transition-duration: .01ms !important; }
  }

  .refresh { width:30px; height:30px; border-radius:50%; display:flex;
             align-items:center; justify-content:center; cursor:pointer;
             transition:background .15s, transform .3s; }
  .refresh:hover { background:var(--lx-card); }
  .refresh:active { transform:scale(.9); }
  .refresh img { width:17px; height:17px; opacity:.6; }
  .refresh.spin { animation:lspin .9s linear infinite; }
  @keyframes lspin { to { transform:rotate(360deg); } }

  /* ── 下拉刷新 ── */
  .ptr { position:absolute; left:0; right:0; top:0; height:0; overflow:hidden;
         display:flex; align-items:center; justify-content:center;
         transition:height .2s ease; pointer-events:none; }
  .ptr .sp { width:20px; height:20px; border-radius:50%;
             border:2.5px solid rgba(10,88,246,.18); border-top-color:var(--lx-blue);
             animation:lspin .8s linear infinite; }
  .ptr .tx { font-size:11.5px; color:var(--lx-t3); margin-left:8px; }
`;

class LixiangAdPage extends HTMLElement {

  /* ── 自动绑定（与 app-home 同一引擎，用户不用手填实体 ID）── */
  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try {
      const AB = window.LixiangAutoBind;
      if (AB && this._hass) {
        out = new AB(this._hass, this._config || {}).resolve() || {};
      }
    } catch (e) { /* 引擎不可用时退回手填 */ }
    // ★ 只有非空结果才缓存：hass.entities 未就绪时返回 {} ，
    //   若缓存会导致永久空绑定（真实踩过的坑）
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }

  /** 取实体：手填配置 > 自动发现 */
  _eid(field) {
    const c = this._config || {};
    const manual = c[field];
    if (typeof manual === "string" && manual.includes(".")) return manual;
    return (this._autoBind() || {})[field] || null;
  }

  /** 嵌套组也支持自动发现 */
  _eidIn(group, key) {
    const c = this._config || {};
    const m = (c[group] || {})[key];
    if (typeof m === "string" && m.includes(".")) return m;
    if (m && typeof m === "object" && m.entity) return m.entity;
    return (this._autoBind() || {})[key] || null;
  }

  /**
   * 让元素键盘可达（无障碍）。
   * 用法：this._a11y(el, "车锁", handler)
   */
  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role", "button");
    el.setAttribute("tabindex", "0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        e.stopPropagation();
        handler(e);
      }
    });
  }
  setConfig(c){ this._config=c||{}; this._built=false; }
  set hass(h){ this._hass=h; if(!this._built) this._build(); this._update(); }
  getCardSize(){ return 16; }

  disconnectedCallback() {
    // 清理定时器与监听，避免卡片被移除后仍持有引用（内存泄漏）
    if (this._tt) { clearTimeout(this._tt); this._tt = null; }
    if (this._poll) { clearInterval(this._poll); this._poll = null; }
    if (this._cleanupScroll) { this._cleanupScroll(); this._cleanupScroll = null; }
    this._fetching = false;
    this._fetchingYears = false;
  }
  _num(id){ const s=(id&&this._hass)?this._hass.states[id]:null;
    if(!s||["unknown","unavailable"].includes(s.state)) return null;
    const n=parseFloat(s.state); return isNaN(n)?null:n; }

  _build(){
    while(this.firstChild) this.removeChild(this.firstChild);
    const st=document.createElement("style"); st.textContent=STYLE; this.appendChild(st);
    const c=this._config;
    const root=document.createElement("div");
    root.className="root"; root.dataset.theme=c.theme||"light";
    root.innerHTML=`
      <div class="ptr" id="ptr"><div class="sp"></div><div class="tx">下拉刷新</div></div>
      <div class="topbar">
        <img class="back" id="back" src="${__iconBase}/ic_home_return.webp" alt="返回">
        <h1>智驾统计</h1>
        <div class="refresh" id="refresh" role="button" tabindex="0" aria-label="刷新">
          <img src="${__iconBase}/ic_home_return.webp" alt="" style="transform:rotate(-90deg)">
        </div>
      </div>
      <div class="hero">
        <div class="lbl">辅助驾驶总里程</div>
        <div class="big"><span id="h-ad">—</span><small>km</small></div>
        <div class="sub" id="h-sub">—</div>
        <div class="bar">
          <i id="b-noa" style="width:0%"></i>
          <i id="b-lcc" style="width:0%"></i>
          <i id="b-acc" style="width:0%"></i>
        </div>
      </div>
      <div class="grid">
        <div class="g"><div class="l"><i style="background:#0A58F6"></i>NOA</div>
          <div class="v"><span id="g-noa">—</span><small>km</small></div>
          <div class="p" id="p-noa">—</div></div>
        <div class="g"><div class="l"><i style="background:#34C759"></i>LCC</div>
          <div class="v"><span id="g-lcc">—</span><small>km</small></div>
          <div class="p" id="p-lcc">—</div></div>
        <div class="g"><div class="l"><i style="background:#FF9500"></i>ACC</div>
          <div class="v"><span id="g-acc">—</span><small>km</small></div>
          <div class="p" id="p-acc">—</div></div>
      </div>
      <div class="sect">
        <h2>使用情况</h2>
        <div class="row"><img src="${__iconBase}/ic_home_navigation.webp" alt="">
          <div class="tx"><div class="nm">累计使用天数</div>
            <div class="sd" id="d-sub">—</div></div>
          <div class="val"><span id="d-days">—</span> 天</div></div>
        <div class="row"><img src="${__iconBase}/ic_home_mileage.webp" alt="">
          <div class="tx"><div class="nm">占总里程比例</div>
            <div class="sd" id="t-sub">—</div></div>
          <div class="val"><span id="d-ratio">—</span>%</div></div>
        <div class="row"><img src="${__iconBase}/ic_home_dialogue.png" alt="" onerror="this.style.visibility='hidden'">
          <div class="tx"><div class="nm">日均智驾里程</div>
            <div class="sd">辅助驾驶里程 ÷ 使用天数</div></div>
          <div class="val"><span id="d-avg">—</span> km</div></div>
      </div>
      <div class="note">
        <div class="it"><span class="dot">·</span><span><b>NOA</b>（导航辅助驾驶）：在高精地图覆盖路段自动变道、进出匝道。</span></div>
        <div class="it"><span class="dot">·</span><span><b>LCC</b>（车道居中辅助）：保持车道居中并跟车行驶。</span></div>
        <div class="it"><span class="dot">·</span><span><b>ACC</b>（自适应巡航）：仅保持车速与车距，不做车道控制。</span></div>
        <div class="it"><span class="dot">·</span><span>数据来源为车端统计，可能存在延迟，请以车辆显示为准。</span></div>
      </div>
    `;
    this.appendChild(root);
    const _bk4 = this.querySelector("#back");
    this._a11y(_bk4, "返回", ()=>_bk4.click());
    _bk4.addEventListener("click", ()=>{
      const p=(c.nav||{}).back||"/lixiang/app";
      history.pushState(null,"",p);
      this.dispatchEvent(new CustomEvent("location-changed",{bubbles:true,composed:true}));
    });
    
    // 刷新：重新拉取实体状态
    const _rf = this.querySelector("#refresh");
    const _doRf = () => {
      const el = this.querySelector("#refresh");
      if (el) el.classList.add("spin");
      this._built = this._built;   // 触发 _update
      this._update(); if (this._fetchStats) this._fetchStats();
      setTimeout(() => { if (el) el.classList.remove("spin"); }, 700);
    };
    if (_rf) { this._a11y(_rf, "刷新", _doRf); _rf.addEventListener("click", _doRf); }

    // ── 下拉刷新（触摸手势，对齐 App）──
    (() => {
      const ptr = this.querySelector("#ptr");
      const rootEl = this.querySelector(".root");
      if (!ptr || !rootEl) return;
      let startY = 0, pulling = false, dist = 0;
      const TH = 64;
      rootEl.addEventListener("touchstart", (e) => {
        if (window.scrollY > 4) return;
        startY = e.touches[0].clientY; pulling = true; dist = 0;
      }, { passive: true });
      rootEl.addEventListener("touchmove", (e) => {
        if (!pulling) return;
        dist = e.touches[0].clientY - startY;
        if (dist > 0 && window.scrollY <= 4) {
          const h = Math.min(dist * 0.55, 70);
          ptr.style.height = h + "px";
          ptr.querySelector(".tx").textContent = h >= TH * 0.5 ? "松开刷新" : "下拉刷新";
        }
      }, { passive: true });
      rootEl.addEventListener("touchend", () => {
        if (!pulling) return;
        pulling = false;
        const h = parseFloat(ptr.style.height) || 0;
        if (h >= TH * 0.5) {
          ptr.style.height = "44px";
          ptr.querySelector(".tx").textContent = "刷新中…";
          Promise.resolve(this.this._update()).finally(() => {
            setTimeout(() => { ptr.style.height = "0px"; }, 500);
          });
        } else {
          ptr.style.height = "0px";
        }
        dist = 0;
      }, { passive: true });
    })();

    this._built=true;
  }

  _update(){
    if(!this._built) return;
    const c=this._config, q=s=>this.querySelector(s);
    const ad=this._num(this._eid("ad_km")), noa=this._num(this._eid("noa_km")),
          lcc=this._num(this._eid("lcc_km")), acc=this._num(this._eid("acc_km"));
    const total=this._num(this._eid("total_km")), days=this._num(this._eid("ad_days"));
    const fmt=(n)=> n==null ? "—" : Math.round(n).toLocaleString();

    q("#h-ad").textContent = fmt(ad);
    if (ad!=null && total!=null && total>0) {
      q("#h-sub").textContent = `占总里程 ${(ad/total*100).toFixed(1)}%（总里程 ${fmt(total)} km）`;
    } else q("#h-sub").textContent = "数据加载中…";

    // 占比条（以 NOA/LCC/ACC 之和为分母）
    const parts=[["noa",noa],["lcc",lcc],["acc",acc]];
    const sum=parts.reduce((a,[,v])=>a+(v||0),0);
    parts.forEach(([k,v])=>{
      const el=q(`#b-${k}`);
      if(!el) return;
      el.style.width = (sum>0 && v!=null) ? (v/sum*100)+"%" : "0%";
      el.style.background = k==="noa"?"#0A58F6":(k==="lcc"?"#34C759":"#FF9500");
    });
    [["noa",noa],["lcc",lcc],["acc",acc]].forEach(([k,v])=>{
      const vEl=q(`#g-${k}`), pEl=q(`#p-${k}`);
      if(vEl) vEl.textContent = fmt(v);
      if(pEl) pEl.textContent = (sum>0 && v!=null) ? `占智驾 ${(v/sum*100).toFixed(1)}%` : "—";
    });

    q("#d-days").textContent = days==null ? "—" : Math.round(days).toLocaleString();
    if (days!=null) {
      const startYear = new Date().getFullYear() - Math.floor(days/365);
      q("#d-sub").textContent = `自 ${startYear} 年起累计`;
    } else q("#d-sub").textContent = "—";

    if (ad!=null && total!=null && total>0) {
      const r=ad/total*100;
      q("#d-ratio").textContent = r.toFixed(1);
      q("#t-sub").textContent = `${fmt(ad)} ÷ ${fmt(total)} km`;
    } else { q("#d-ratio").textContent="—"; q("#t-sub").textContent="—"; }

    if (ad!=null && days!=null && days>0) q("#d-avg").textContent = (ad/days).toFixed(1);
    else q("#d-avg").textContent = "—";
  }
}

if(!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangAdPage);
window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TAG,
  name: "智驾统计（二级页）",
  description: "NOA/LCC/ACC 里程与占比、使用天数、日均里程",
  preview: true,
});
