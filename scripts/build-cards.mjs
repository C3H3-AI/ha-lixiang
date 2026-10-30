#!/usr/bin/env node
/**
 * 把开发用的多文件卡片，合并成**单文件** `lixiang-all.js`。
 *
 * 为什么需要
 * ----------
 * 车主反馈：「不能把13个js文件合并为一个？」—— 用户只想要**一个资源、一张卡**。
 * 多文件对开发友好（每页一个文件、好维护），但对外发布时：
 *   · 用户要理解"哪个文件对应哪个页面"，漏一个就空白；
 *   · 外壳还得靠相对路径 `import.meta.url` 动态 import 13 个文件，
 *     用户把文件挪到别处（如 /local/）就可能全部加载失败；
 *   · 首屏 14 个请求。
 * 合并成一个文件后：**1 个资源 = 全部功能**，没有相对路径依赖。
 *
 * 做法（无第三方依赖，纯文本变换）
 * --------------------------------
 * 每个文件各自包一层 IIFE，保留原有的模块级作用域 —— 因为 12 张卡都各自声明了
 * 同名顶层常量（`CARD_TAG` / `STYLE` / `lxNavigate` / `__iconBase` …），
 * 13 组重名，直接拼接必然 `Identifier has already been declared`。
 * 有 ESM 导入/导出的 3 个文件（base / info-page / vehicle-info-page）把
 * 导出挂到 `window.__LXB.<模块名>`，导入方改成从该注册表解构。
 *
 * 所有 `customElements.define` 都带 `if (!customElements.get(...))` 守卫，
 * 因此与单文件资源并存也不会重复定义报错（已核对 18/18）。
 *
 * 用法
 * ----
 *   node scripts/build-cards.mjs              # 写入 lixiang-all.js
 *   node scripts/build-cards.mjs --stdout     # 打印到 stdout（供测试比对是否过期）
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DIR = path.join(HERE, "..", "custom_components", "lixiang_auto", "www", "lixiang-cards");
const OUT = path.join(DIR, "lixiang-all.js");

/** 依赖顺序：base → info-page → vehicle-info-page → 其余（彼此独立）→ 外壳 → 总览 */
const ORDER = [
  "lixiang-base.js",
  "lixiang-info-page.js",
  "lixiang-vehicle-info-page.js",
  "lixiang-app-home.js",
  "lixiang-charge-page.js",
  "lixiang-energy-page.js",
  "lixiang-health-page.js",
  "lixiang-setting-page.js",
  "lixiang-scene-page.js",
  "lixiang-climate-page.js",
  "lixiang-seat-page.js",
  "lixiang-location-page.js",
  "lixiang-task-page.js",
  "lixiang-ad-page.js",
  "lixiang-sentry-page.js",
  "lixiang-bindings-card.js",
  "lixiang-overview-card.js",
  "lixiang-app.js",           // 外壳最后（它会引用各子卡片元素名）
  "lixiang-assets.js",
  "lixiang-auto-bind.js",
];

/** 这些模块有 ESM 导出 —— 需要把导出挂到注册表供后面的文件解构 */
const EXPORTING = new Set(["lixiang-base.js", "lixiang-info-page.js"]);
const MODKEY = { "lixiang-base.js": "base", "lixiang-info-page.js": "info" };

function transform(file, src) {
  const imports = [];
  let body = src.replace(
    /^\s*import\s+\{([^}]*)\}\s+from\s+["']\.\/([\w.-]+)["'];?\s*$/gm,
    (_, names, dep) => {
      const key = MODKEY[dep];
      imports.push(key ? `const {${names}} = window.__LXB.${key};` : "");
      return "";
    },
  );

  // 记录导出名（供 return / 注册表使用）
  const exported = [];
  body = body.replace(/^\s*export\s+(const|function|class)\s+(\w+)/gm, (_, kind, name) => {
    exported.push(name);
    return `${kind} ${name}`;
  });
  body = body.replace(/^\s*export\s*\{([^}]*)\};?\s*$/gm, (_, names) => {
    names.split(",").forEach((n) => {
      const clean = n.trim().split(/\s+as\s+/).pop().trim();
      if (clean && clean !== "default") exported.push(clean);
    });
    return "";
  });
  body = body.replace(/^\s*export\s+default\s+[^;]*;?\s*$/gm, "");

  // 统一缩进，避免 IIFE 包裹后首行贴边
  body = body.replace(/\s+$/, "");

  const head = [
    `/* ===================== ${file} ===================== */`,
    ...imports.filter(Boolean),
  ].join("\n");

  if (EXPORTING.has(file)) {
    const key = MODKEY[file];
    const ret = exported.length ? `  return { ${[...new Set(exported)].join(", ")} };\n` : "";
    return `window.__LXB = window.__LXB || {};\nwindow.__LXB.${key} = (function () {\n${head}\n${body}\n${ret}})();\n`;
  }
  return `${head}\n(function () {\n${body}\n})();\n`;
}

function build() {
  const parts = [
    "/* eslint-disable */",
    "/**",
    " * ⚠️ 自动生成，请勿手改 —— 改源文件后运行 `node scripts/build-cards.mjs`。",
    " * 内容来源：custom_components/lixiang_auto/www/lixiang-cards/*.js",
    " * 单文件版：1 个资源即含全部卡片与总卡片外壳，没有相对路径依赖。",
    " */",
    "window.__LXB = window.__LXB || {};",
    "",
  ];
  for (const file of ORDER) {
    let src;
    try {
      src = readFileSync(path.join(DIR, file), "utf8");
    } catch {
      continue; // 文件不存在则跳过（保持构建稳健）
    }
    parts.push(transform(file, src));
  }
  return parts.join("\n");
}

const out = build();
if (process.argv.includes("--stdout")) {
  process.stdout.write(out);
} else {
  writeFileSync(OUT, out);
  const kb = (Buffer.byteLength(out) / 1024).toFixed(0);
  process.stdout.write(`✅ 已生成 ${path.relative(process.cwd(), OUT)}（${kb} KB）\n`);
}
