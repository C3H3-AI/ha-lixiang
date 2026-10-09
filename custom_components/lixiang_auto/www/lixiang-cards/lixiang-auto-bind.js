/**
 * lixiang-auto-bind —— 实体自动发现引擎（供所有理想卡片复用）
 *
 * 设计目标：用户**不用手填 90 个实体 ID**。
 *   配置只需（任选其一）：
 *     · vin: HLX32XXXXXXXXXXXX      ← 最精确
 *     · 或什么都不填（自动认领第一辆理想车）
 *
 * 原理：
 *   ① 从 hass.entities（实体注册表）按 platform==='lixiang_auto' 过滤
 *   ② 用【中文名】匹配（original_name），而非实体 ID 字符串
 *      —— 实体 ID 里的拼音会随 HA 版本/语言变化，中文名稳定
 *   ③ 用 device_id 归属校验（多车时不会串）
 *
 * 匹配策略（三道，逐级放宽）：
 *    exact  完全等于 name
 *    contains 包含 name
 *    regex  正则
 */

const AUTO_BIND = {
  /* ── 车辆标识 ── */
  _meta: { platform: "lixiang_auto" },

  /* ── 字段映射表 ─────────────────────────────────────────────
   * 值可以是：
   *   "充电上限"                  → 精确名
   *   ["充电上限", "电池充电上限"] → 多个候选名（按序尝试）
   *   { any: ["充电", "上限"] }   → 必须同时包含（更稳）
   *   { re: "^充电.*上限$" }      → 正则
   *   { domain: "lock" }          → 只要域名匹配即取（唯一时）
   * ──────────────────────────────────────────────────────────── */
  fields: {
    /* 顶部状态 */
    title:          { meta: true },                      // 由车型名生成
    range_elec:     ["纯电续航(CLTC)", "纯电续航(CLTC)", "纯电续航"],
    range_fuel:     ["燃油续航(CLTC)", "燃油续航"],
    battery:        ["电池电量"],
    status:         { any: ["行驶", "状态"] },            // 行驶状态
    online:         ["在线状态"],
    /* 里程 */
    month_km:       ["本月里程", "本月陪伴里程"],
    partner_km:     ["陪伴里程"],
    partner_days:   ["陪伴天数"],
    total_km:       ["总里程"],
    ad_km:          ["辅助驾驶里程"],
    ad_days:        ["辅助驾驶天数"],
    noa_km:         ["NOA 里程", "NOA里程"],
    lcc_km:         ["LCC 里程", "LCC里程"],
    acc_km:         ["ACC 里程", "ACC里程"],
    /* 空调 */
    room_temp:      ["车内温度"],
    target_temp:    ["空调设定温度"],
    ac:             { domain: "climate" },
    /* 位置 */
    address:        ["位置服务"],
    tracker:        { domain: "device_tracker" },
    /* 充电 */
    charge_status:  ["充电状态"],
    charge_complete:["充电完成状态"],
    charge_limit:   ["充电上限"],
    charge_mode:    ["充电模式"],
    charge_power:   ["充电功率(CLTC)", "充电功率(WLTC)"],
    charge_remain:  ["剩余充电时间"],
    ac_gun:         ["交流充电枪"],
    dc_gun:         ["直流充电枪"],
    port_cover:     ["充电口盖"],
    fault_charge:   ["充电故障"],
    appointment:    ["预约充电"],
    month_kwh:      ["本月充电量"],
    total_kwh:      ["累计充电量"],
    /* 健康 */
    tire_lf:        ["胎压 左前"],
    tire_rf:        ["胎压 右前"],
    tire_lr:        ["胎压 左后"],
    tire_rr:        ["胎压 右后"],
    temp_lf:        ["胎温 左前"],
    temp_rf:        ["胎温 右前"],
    temp_lr:        ["胎温 左后"],
    temp_rr:        ["胎温 右后"],
    warn_lf:        ["胎压告警 左前"],
    warn_rf:        ["胎压告警 右前"],
    warn_lr:        ["胎压告警 左后"],
    warn_rr:        ["胎压告警 右后"],
    pack_voltage:   ["电池包电压"],
    fault_dcdc:     ["DCDC 故障"],
    /* 场景 */
    scene_mode:     ["场景模式"],
    /* 里程能耗页字段 */
    ac_temp:        ["空调设定温度"],
    aqi:            ["空气污染指数"],
    /* 座椅（9 个 fan + 方向盘加热）*/
    steer_heat:     { name: "方向盘加热", domain: "switch" },
    seat_fl_heat:   { name: "主驾座椅加热", domain: "fan" },
    seat_fl_vent:   { name: "主驾座椅通风", domain: "fan" },
    seat_fr_heat:   { name: "副驾座椅加热", domain: "fan" },
    seat_fr_vent:   { name: "副驾座椅通风", domain: "fan" },
    seat_rl_heat:   { name: "二排左座椅加热", domain: "fan" },
    seat_rl_vent:   { name: "二排左座椅通风", domain: "fan" },
    seat_rc_heat:   { name: "二排中座椅加热", domain: "fan" },
    seat_rr_heat:   { name: "二排右座椅加热", domain: "fan" },
    seat_rr_vent:   { name: "二排右座椅通风", domain: "fan" },
    /* 位置页 */
    photo_info:     { any: ["360", "拍照", "信息"], domain: "sensor" },
    photo_status:   { any: ["360", "拍照", "状态"], domain: "sensor" },
    vehicle_cfg:    ["车辆配置"],
    /* 保养 */
    maint_sparkplug:      { name: "火花塞" },
    maint_acfilter:       { name: "空调滤芯" },
    maint_brake_oil:      { name: "刹车油" },
    maint_coolfuild:      { name: "冷却液" },
    maint_engine_oil:     { name: "机油" },
    maint_engine_level2:  { name: "保养二级" },
    elec_km:        ["耗电行驶"],
    fuel_l:         ["本月耗油量", "耗油总量"],
    partner_days:   ["陪伴天数"],
    /* 充电页兼容别名（卡片用短名，引擎用长名）*/
    status_charge:  ["预约充电状态", "充电状态"],
    complete:       ["充电完成状态"],
    limit:          ["充电上限"],
    mode:           ["充电模式", "预约充电模式"],
    power:          ["充电功率(CLTC)", "充电功率(WLTC)"],
    remain:         ["剩余充电时间"],
    soc:            ["电池电量"],
    fault:          ["充电故障"],
    month_times:    null,   // 集成无「次数」实体 → 由卡片从月度统计算（见 charge-page）
    /* 健康页别名 */
    lv_battery:     { any: ["低压", "电源"] },
    fault_stop:     { any: ["故障", "停止充电"] },
    /* 快捷按钮（按域名 + 名称）*/
    lock:           { domain: "lock" },
    window:         { name: "车窗", domain: "cover" },
    trunk:          { name: "尾门", domain: "cover" },
    /* ★ 2026-10-09 修正：首页「授权驾驶」按钮此前绑到 binary_sensor（车辆授权，只读）
       → 点击只会弹「只读，无法控制」。集成里真实的可执行实体是
       button.<车名>_授权驾驶（cmdKey=remoteVehAuth），状态显示另用 auth_state。 */
    auth:           { name: "授权驾驶", domain: "button" },
    auth_state:     { name: "车辆授权", domain: "binary_sensor" },
    find:           { name: "寻车", domain: "button" },
    /* ★ 2026-10-09 修正：后视镜加热此前绑 binary_sensor 且用 any 分支（会命中只读的
       sensor「左后视镜」）→ 按钮点不动。真正的控制在 switch「后视镜加热」（rmCtrl）。 */
    mirror:         { name: "后视镜加热", domain: "switch" },
    /* ★ 2026-10-09 新增：充电口盖控制（cpCtrl）。注意与只读的
       binary_sensor「充电口盖」（port_cover，用于充电页展示）区分开。 */
    port:           { name: "充电盖", domain: "switch" },
    /* 设置（可控制）*/
    sentry:         { name: "哨兵模式", domain: "switch" },
    ac_fast_hot:    { name: "快速制热", domain: "switch" },
    ac_fast_cold:   { name: "快速制冷", domain: "switch" },
    /* ★ 2026-10-09 修正：switch 实体名是「除雪除冰」，不是「除霜」；
       原 any:["除霜"] 会命中只读的 sensor「除霜模式」→ 空调页按钮点不动。 */
    ac_defrost:     { name: "除雪除冰", domain: "switch" },
    steer_heat:     { name: "方向盘加热", domain: "switch" },
    batt_warm:      { name: "电池保温", domain: "switch" },
    /* 远程操作 */
    btn_find:       { name: "寻车", domain: "button" },
    /* ★ 2026-10-09 修正：button 实体名是「授权驾驶」（旧规则找「远程启动」永远无命中）*/
    btn_start:      { name: "授权驾驶", domain: "button" },
    btn_flash:      { name: "闪灯", domain: "button" },
    btn_horn:       { name: "鸣笛", domain: "button" },
    btn_photo:      { name: "远程拍照", domain: "button" },
  },
};

/* ─────────────────────────── 引擎实现 ─────────────────────────── */

class LixiangAutoBind {
  constructor(hass, config) {
    this._hass = hass;
    this._config = config || {};
    this._cache = null;
  }

  /** 主入口：返回 { fieldName: entity_id } */
  resolve() {
    if (this._cache) return this._cache;
    const h = this._hass;
    if (!h || !h.entities) { this._cache = {}; return this._cache; }

    // ① 圈定本集成的实体
    const pool = this._pool();
    if (!pool.length) { this._cache = {}; return this._cache; }

    // ② 逐字段匹配
    const out = {};
    for (const [field, rule] of Object.entries(AUTO_BIND.fields)) {
      if (rule && rule.meta) continue;
      if (rule == null) continue;   // 显式禁用该字段
      const hit = this._match(field, rule, pool);
      if (hit) out[field] = hit;
    }
    this._cache = out;
    return out;
  }

  /** 池：本集成的实体（可被 vin 进一步收窄）*/
  _pool() {
    const h = this._hass;
    const vin = this._config.vin || "";
    let devIds = null;
    if (vin) {
      devIds = new Set(
        Object.values(h.devices || {})
          .filter((d) => (d.identifiers || []).some((i) => String(i).includes(vin)))
          .map((d) => d.id)
      );
    }
    const list = [];
    for (const e of Object.values(h.entities)) {
      const isMine = e.platform === "lixiang_auto"
        || (devIds && devIds.has(e.device_id));
      if (!isMine) continue;
      if (vin && devIds && devIds.size && !devIds.has(e.device_id)) continue;
      const st = h.states[e.entity_id];
      if (!st) continue;   // 未启用/不可用
      list.push({
        id: e.entity_id,
        name: e.original_name || e.name || "",
        domain: e.entity_id.split(".")[0],
        device: e.device_id,
      });
    }
    return list;
  }

  /** 单字段匹配（三道策略）*/
  _match(field, rule, pool) {
    // 显式配置优先
    const explicit = this._config[field];
    if (typeof explicit === "string" && explicit.includes(".")) return explicit;

    // { domain: "lock" } —— 域名唯一匹配
    if (rule && typeof rule === "object" && rule.domain && !rule.name && !rule.any && !rule.re) {
      const cands = pool.filter((x) => x.domain === rule.domain);
      return cands.length === 1 ? cands[0].id : null;
    }

    // { name, domain } —— 名称 + 域名
    if (rule && typeof rule === "object" && rule.name) {
      const cands = pool.filter((x) =>
        (!rule.domain || x.domain === rule.domain) && x.name.includes(rule.name));
      return cands.length ? cands[0].id : null;
    }

    // { any: [...] } —— 必须同时包含
    //   ★ 2026-10-09 修复：此前忽略 rule.domain，导致 { any:["后视镜"], domain:"binary_sensor" }
    //     命中只读的 sensor「左后视镜」，卡片按钮点不动（真事故）。
    if (rule && typeof rule === "object" && rule.any) {
      const cands = pool.filter((x) =>
        (!rule.domain || x.domain === rule.domain) &&
        rule.any.every((w) => x.name.includes(w)));
      if (cands.length) return cands[0].id;
      return null;
    }

    // { re: "..." } —— 正则
    if (rule && typeof rule === "object" && rule.re) {
      const re = new RegExp(rule.re);
      const cands = pool.filter((x) => re.test(x.name));
      return cands.length ? cands[0].id : null;
    }

    // 字符串 或 数组 —— 精确名优先，再退到包含
    const names = Array.isArray(rule) ? rule : [rule];
    for (const want of names) {
      const exact = pool.find((x) => x.name === want);
      if (exact) return exact.id;
    }
    for (const want of names) {
      const part = pool.find((x) => x.name.includes(want));
      if (part) return part.id;
    }
    return null;
  }

  /**
   * 摘要（人可读，供 console / 诊断卡展示）。
   * 返回 { model, series, poolSize, matched, missing, version }
   */
  summary(detected) {
    const dg = this.diagnose();
    const ok = dg.fields.filter((f) => f.ok);
    const miss = dg.fields.filter((f) => !f.ok);
    return {
      model: (detected && detected.model) || "",
      series: (detected && detected.series) || "",
      poolSize: dg.poolSize,
      total: dg.fields.length,
      matched: ok.length,
      missing: miss.map((f) => f.field),
      rate: dg.fields.length
        ? ((ok.length / dg.fields.length) * 100).toFixed(1) + "%" : "0%",
      bindings: dg.fields.filter((f) => f.ok)
        .reduce((a, f) => (a[f.field] = f.entity, a), {}),
    };
  }

  /** console 打表（默认开启，便于用户/开发者排查；tags 传 false 可关）*/
  logToConsole(detected, enabled) {
    if (enabled === false) return;
    const sm = this.summary(detected);
    /* eslint-disable no-console */
    console.groupCollapsed(
      `%c[理想卡片] 自动发现 ${sm.matched}/${sm.total} (${sm.rate})` +
      (sm.model ? ` · ${sm.model}` : ""),
      "color:#0A58F6;font-weight:600");
    console.log("实体池:", sm.poolSize, "| 车系:", sm.series || "(未识别)");
    console.table(
      Object.entries(sm.bindings).map(([field, entity]) => ({ 字段: field, 实体: entity }))
    );
    if (sm.missing.length) {
      console.log("未匹配字段（该功能可能在本车型不存在）:", sm.missing);
    }
    console.groupEnd();
    /* eslint-enable no-console */
  }

  /** 诊断：返回匹配详情（供卡片显示"自动发现结果"）*/
  diagnose() {
    const pool = this._pool();
    const out = [];
    for (const [field, rule] of Object.entries(AUTO_BIND.fields)) {
      if (rule && rule.meta) continue;
      const hit = this._match(field, rule, pool);
      out.push({ field, entity: hit || null, ok: !!hit });
    }
    return { poolSize: pool.length, fields: out };
  }
}

window.LixiangAutoBind = LixiangAutoBind;
window.LIXIANG_FIELD_DEFS = AUTO_BIND.fields;
