/**
 * lx_bind_sim.js —— 在 Node 里跑前端实体自动发现引擎（测试用，不随卡片发布）
 *
 * 为什么需要：
 *   卡片"点不动"这类事故（2026-10-09：首页「后视镜加热」绑到只读 sensor、
 *   「充电口盖」完全没有字段、`cover.open` / `switch.open` 服务不存在）
 *   静态查子串是查不出来的 —— 只有真正跑一遍 resolve() 才能发现。
 *
 * 用法：
 *   node lx_bind_sim.js <entities.json> <lixiang-auto-bind.js>
 *
 * entities.json 形如：
 *   { "entities": { "switch.x": { "entity_id":"switch.x", "original_name":"后视镜加热",
 *                                 "platform":"lixiang_auto", "device_id":"dev1" }, ... },
 *     "devices":  { "dev1": { "identifiers": [["lixiang_auto","VIN"]] } },
 *     "states":   { "switch.x": { "state": "off", "attributes": {} } } }
 *
 * 输出：JSON —— { pool, resolved, missing, domainViolations }
 */
const fs = require("fs");

const live = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const src = fs.readFileSync(process.argv[3], "utf8");

const hass = {
  entities: live.entities || {},
  devices: live.devices || {},
  states: live.states || {},
};

const fakeWindow = {};
new Function("window", src)(fakeWindow);

const Engine = fakeWindow.LixiangAutoBind;
if (typeof Engine !== "function") {
  console.error("引擎未导出 window.LixiangAutoBind");
  process.exit(2);
}
const defs = fakeWindow.LIXIANG_FIELD_DEFS || {};
const inst = new Engine(hass, {});
const resolved = inst.resolve();

const missing = Object.entries(defs)
  .filter(([f, r]) => !(r && r.meta) && !resolved[f])
  .map(([f]) => f);

// 规则声明了 domain 的字段，解析结果必须落在该 domain 内
const domainViolations = Object.entries(resolved)
  .filter(([f, eid]) => {
    const rule = defs[f];
    return rule && rule.domain && eid.split(".")[0] !== rule.domain;
  })
  .map(([f, eid]) => ({ field: f, entity: eid, expected: defs[f].domain }));

console.log(JSON.stringify({
  pool: inst._pool().length,
  resolved,
  missing,
  domainViolations,
}, null, 2));
