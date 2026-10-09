# 贡献指南

> 本项目所有改动**必须通过 Pull Request**，`main` 分支已开启保护。

---

## 工作流

```
① 从 main 建分支
     ./li-pr.sh start <类型> <简述>
     
② 改代码（在 HA 测试机）
     /media/duola/devdata/AI-workspace/home-assistant-nas/ha-test/config/custom_components/lixiang_auto/
     
③ ★ 验证（改完必跑，7 项检查）
     ./li-verify.sh
     
     ⚠️ 这步不能省 —— 2026-09-24 曾因跳过它导致 4 次
        HA 实体大面积不可用（详见 VERIFY.md）
     
④ 提交 + 开 PR（内置验证拦截）
     ./li-pr.sh submit
     
⑤ 人在 GitHub 上 review + 合并
     https://github.com/c3h3-ci/ha-lixiang/pulls
```

---

## 分支命名

| 类型 | 用途 | 例子 |
|---|---|---|
| `feat/` | 新功能 | `feat/optimize-login-flow` |
| `fix/` | Bug 修复 | `fix/trunk-door-semantics` |
| `refactor/` | 重构（不改行为）| `refactor/merge-route-id` |
| `docs/` | 文档 | `docs/add-contributing` |
| `ci/` | CI/构建 | `ci/add-hassfest` |
| `chore/` | 杂项 | `chore/bump-version` |
| `test/` | 只加/改测试 | `test/pr-guard` |
| `perf/` | 性能 | `perf/poll-tiers` |

### PR 标题格式（CI 强制）

```
<类型>(<范围>): <描述>
```

- **类型**：上面 8 种之一（`feat` / `fix` / `refactor` / `docs` / `ci` / `chore` / `test` / `perf`）
- **范围**：可选，小写（如 `fix(signals): …`、`ci(pr-guard): …`）
- **描述**：至少 4 个字符

由 `.github/workflows/pr-guard.yml` 检查，不合规**直接失败**。

### 关联 Issue

若本次改动对应某个 Issue，在描述里写 `Fixes #N` / `Closes #N` ——
合并时会自动关闭该 Issue 并留痕。缺了只是**警告**，不阻断。

---

## PR 要求

### 必须

- [ ] **已在测试机验证**（HA 重启无错误、实体正常）
- [ ] **敏感信息扫描通过**（`./li-pr.sh submit` 会自动跑）
- [ ] **CI 通过**（hassfest + HACS + lint）

### ★★ 测试必须真的能失败（2026-09-28 实测教训）

**没有失败能力的测试 = 装饰品。** 提交涉及新保护逻辑的 PR 时，必须做一次**变异测试**：
把保护删掉，确认测试**确实失败**，再恢复。

**2026-09-28 真实案例**（充电只读守卫）：

```
第一次：用桩（stub）模拟"li_api 会调用守卫"
  → 把 li_api.py 里真正的守卫调用删掉，572 个测试【照样全过】
  → 桩把真实缺陷完全掩盖了

第二次：改成源码子串检查
  assert "ensure_job_channel_supported(" in body
  → 但 body 里那段【注释】正好写着
     "理由见 ensure_job_channel_supported() 的 docstring"
  → 注释里的函数名让子串检查【恒为真】，删掉真调用后测试照样通过

第三次（正确）：用 AST 只认真正的调用节点
  for c in ast.walk(n):
      if isinstance(c, ast.Call): ...
  → 才真正抓住
```

**两条规则**：

1. **对代码做子串断言前，必须先剥掉注释** —— 否则注释会替代码"背书"。
   优先用 `ast` 而非字符串匹配。
2. **桩不能替代对真实调用链的断言** —— 桩验证的是"我假设调用会发生"，
   不是"调用真的发生了"。两者都要有。

**验收动作**：新保护逻辑的 PR，请在描述里附一句
「已做变异测试：删掉 X → N 个测试失败」。

### ★ CI「失败但 0 个 job」= 工作流文件坏了，不是代码问题

```bash
# 看 jobs 数：0 说明 GitHub 根本没启动工作流
curl -s -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/c3h3-ci/ha-lixiang/actions/runs/<RUN_ID>/jobs" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['total_count'])"
```

**先在本地验证 YAML 能解析**，再怀疑代码：

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/validate.yml'))"
```

**2026-09-27 实际踩坑**：`validate.yml` 里内嵌 `python3 -c "` 多行字符串，
Python 代码从**第 1 列**开始 ⇒ 提前终止 YAML 块标量 ⇒ 整份文件无法解析 ⇒ **0 jobs**。
main 和所有分支的 CI 都是坏的，且**看起来像代码问题**。

> 写多行脚本时用 `python3 - <<'PY' ... PY` heredoc，并让它与 `run:` 的块标量**同缩进**
> （块标量会自动去掉公共缩进，终止符落到第 0 列）。
> 注意：`echo "$X" | python3 - <<'PY'` 里 **heredoc 会覆盖管道**，
> `sys.stdin` 读到的是脚本自身 —— 数据请走环境变量。

### 建议

- [ ] 附上变更原因的说明（尤其是"为什么这样改"）
- [ ] 涉及信号语义的改动，**必须附 App 源码依据**（文件:行号）
- [ ] 涉及行为变更的，附验证方法

---

## ⚠️ PR 合并后的规则

**PR 合并后，不要继续在同一个分支上提交！**

```
❌ 错误做法：
   ① ./li-pr.sh start feat xxx      → 建分支
   ② 改代码 + 提交 + 开 PR #11
   ③ 人合并 PR #11
   ④ 又在同一分支上提交修复         → ★ 推不进 main！
      （PR 已关闭，新 commit 无处可去）

✅ 正确做法：
   ① PR 合并后，立刻切回 main 并 pull
   ② 从 main 建【新分支】做后续改动
   ③ 开新 PR
```

**2026-09-24 实际踩坑**：PR #11 合并后又在原分支提交了 2 个修复，
导致 main 上是有 bug 的版本（缺 `to_binary_descriptions` 等），
需要 PR #12 补救。

**2026-09-28 又踩了一次（同一规则）**：PR #5 合并后继续用
`fix/i6-fuel-frunk-fridge-steering` 分支提交，新提交卡在【已关闭的 PR】上
无处可去，只能复用同一个分支再开 PR #7 补救；中途还建错分支
（`fix/per-seat-and-path-audit`）又删掉。

> **两次踩同一个规则，说明"写进文档"不够。** 现在由
> `.github/workflows/pr-guard.yml` **机器强制**：一旦检测到该分支
> 有已合并的 PR，PR 直接失败并给出改法。

### 检查方法

```bash
# 提 PR 前确认：当前分支是否已合并到 main？
git log --oneline origin/main..HEAD    # 有输出 = 有新 commit（正常）
git branch -r --merged origin/main | grep "$(git branch --show-current)"
#   ↑ 有输出 = 该分支已合并 → ★ 应改用新分支！
```

---

## 禁止

- ❌ 直接推 `main`
  > ✅ **2026-09-27 起 main 已真正开启分支保护**（此前只有文档声称、实际未开）：
  > ```
  > GET /repos/c3h3-ci/ha-lixiang/branches/main → protected: true
  >   必需状态检查：lint & security / hassfest / HACS validate（strict）
  >   允许强推：false    允许删除：false
  > ```
  > 即：直接推 main 会被拒绝；PR 必须等这 3 个 CI 全绿且分支是最新的才能合并。
  > 用 `./scripts/li-status.sh` 第 ⑤ 项可随时复查。
- ❌ 提交真实个人数据（手机号/密码/VIN/设备ID）
- ❌ 未经验证的信号语义猜测（必须读 App 源码）

---

## 双副本同步

集成在 HA 测试机运行时是两份代码：

```
测试机（HA 运行）                     仓库（发布）
config/custom_components/     ←→    ha-lixiang/
      lixiang_auto/                    custom_components/lixiang_auto/
```

`./scripts/li-pr.sh submit` 会自动同步 + 检查。

> ⚠️ HA 无法从软链接加载 custom_component，所以必须双副本。

### ★★ 同步方向：仓库 → 测试机 才是「部署」

这条踩过坑，务必分清：

```
✅ 部署（仓库 → 测试机）：把【已合并】的代码送上去跑
     rsync -a --delete <仓库>/custom_components/lixiang_auto/  <测试机>/...

❌ 反向覆盖（测试机 → 仓库）：测试机一旦落后，就会用旧代码覆盖新代码
     —— 等于静默回退已合并、甚至已发布的功能
```

### ★ 两种工作流，`li-pr.sh submit` 都已支持（2026-09-28 补）

原先脚本**只支持 test-first**（在测试机上改 → 把改动收回仓库）。
但更常见的是 **repo-first**（在仓库里改 → 部署到测试机验证），
此时 `submit` 会走「测试机 → 仓库」并检测到「仓库领先」而中止 ——
中止本身没错，但**没有提供另一条路**，于是只能绕过脚本手工 `docker cp`，
脚本内置的安全检查 / 强制验证 / 提交信息规范全部失效。

现在 `submit` **自动判定方向**：

| 情形 | 行为 |
|---|---|
| 仓库有未提交的组件改动 | **部署**（仓库 → 测试机）—— repo-first |
| 两侧一致 | 什么都不做 |
| 有差异，测试机内容全等于仓库历史版本 | 测试机只是**落后** → **部署**对齐 |
| 有差异，测试机有非历史版本的内容 | 测试机有**新工作** → 同步回来 |

```bash
./scripts/li-pr.sh submit              # 自动判定
./scripts/li-pr.sh submit --deploy     # 强制 repo-first
./scripts/li-pr.sh submit --from-test  # 强制 test-first
./scripts/li-pr.sh deploy              # 只部署，不提交
```

> 也可用 `LI_SYNC_MODE=deploy|from-test` 强制。
> 部署后 HA 需重启才加载新代码。

### ★ 脚本约定：`--dry-run` 不得有副作用

`li-pr.sh clean --dry-run` 曾经【无条件】执行 `git checkout main`：
本意只是"看看会删什么"，结果把工作分支悄悄切回了 main，
紧接着的提交就落到了 main 上 —— 而 main 有分支保护，推不上去，
只能手工把提交搬回分支。

**规则**：任何 `--dry-run` / `--check` / 只读模式都不得改动工作区、
分支、tag 或远端。验证时不能只看源码文本，还应**实际跑一次并断言
当前分支未变**（见 `tests/test_pr_guard.py::TestLiPrScriptSafety`）。

**2026-09-27 实测**：`v1.1.1` 时点上测试机落后仓库 12 个文件。
旧版 `li-pr.sh submit` 会无条件 `rsync --delete 测试机 → 仓库`，后果：

| 文件 | 后果 |
|---|---|
| `fan.py` | `wheel_heat` 消失 → **PR #5 被回退** |
| `manifest.json` | 版本退回 `1.1.0` |
| `signals.py` | 退回「前备箱/滑门」之前 → 相关功能丢失 |

**现已加固**：`submit` 会先检测测试机文件是否为
「HEAD 历史上的旧版本」，是则**中止并列出会被回退的提交**。
确需覆盖时显式放行：`LI_ALLOW_STALE_SYNC=1`。

> 原则：**测试机是部署目标，不是代码源头。**
> 要改代码就在仓库分支上改，然后部署到测试机。

---

## 版本发布

### ★ 发布是「四步」，缺一步都不算发布完

```bash
./bump.sh patch     # 1.0.0 → 1.0.1（修 bug）
./bump.sh minor     # 1.0.0 → 1.1.0（加功能）
./bump.sh major     # 1.0.0 → 2.0.0（破坏性变更）
```

| 步骤 | 操作 | 缺了会怎样 |
|---|---|---|
| ① | 改版本号 + CHANGELOG，**开 PR** | — |
| ② | PR 合并进 main | — |
| ③ | **打 tag**：`git tag -a v1.1.1 -m "..."` + `git push origin v1.1.1` | HACS 看不到新版本 |
| ④ | **建 GitHub Release** | HACS **仍然看不到**（HACS 读 Release，不读裸 tag）|

```bash
# ③ + ④ 的完整命令
git tag -a v1.1.1 -m "v1.1.1 — 一句话摘要"
git push origin v1.1.1
TOKEN=$(sed -n 's|https://[^:]*:\([^@]*\)@github.com|\1|p' ~/.git-credentials | head -1)
curl -X POST -H "Authorization: token $TOKEN" \
     -H "Accept: application/vnd.github+json" \
     https://api.github.com/repos/c3h3-ci/ha-lixiang/releases \
     -d '{"tag_name":"v1.1.1","name":"v1.1.1","body":"...","draft":false,"prerelease":false}'
```

### ★ Release 正文：自动生成 + 人工叙述

**别再手写发布说明** —— 手工正文会**漏**（只要没写进 CHANGELOG，
那个 PR 就不会出现在说明里）。

正文现在由两部分拼成：

| 部分 | 来源 | 讲什么 |
|---|---|---|
| **人工叙述** | `CHANGELOG.md` 的 `[版本]` 段 | 用户该关心什么 |
| **自动明细** | GitHub `generate-notes`（按 **label** 分类）| 每个 PR，完整不漏 |

自动明细的分类由 **`.github/release.yml`** 决定，而分类依据是 PR 的
**`type: <类型>` 标签** —— 那个标签**已经由 `pr-guard` 按标题自动打好了**：

```
PR 标题合规  →  pr-guard 自动打 type: fix  →  合并  →  Release 笔记自动归类到「🐛 问题修复」
```

> **所以笔记质量 = PR 分类质量。** 给 PR 打对标签（其实是"标题写对"），笔记就对了。
> 想排除某个 PR，给它打 `skip-changelog` 即可。

★ 自动明细取失败（网络等）时会**降级**为只用 CHANGELOG 段并给出警告 ——
**不会因为网络抖动阻断发布**。

### ★ 自动草稿 Release（`draft-release.yml`，2026-09-29 补）

**它解决的问题**：上面那个「tag 落后于 main」的坑，当时的解法是
「加巡检脚本让人记得跑」—— 但**靠人记得的机制就是会失效**（没人跑就等于没有）。

现在多了一层自动化：

```
manifest 版本号变了（合并进 main）→ workflow 自动检测
   ├─ CHANGELOG 没有该版本段 → ❌ 报错中止（避免建出空正文的草稿）
   ├─ tag 已存在            → ✓ 跳过（幂等）
   └─ 否则                  → ✅ 建一个【草稿】Release，正文取自 CHANGELOG
```

**★ 它是草稿，不是发布。** 维护者去 Releases 页面确认正文 → 点 **Publish** 才算发完。

> ⚠️ **改草稿的标题/正文后，务必复核 tag 绑定。**
> 2026-10-09 实测：`PATCH /releases/{id}` 只改 `name` / `body` 时，
> 草稿的 `tag_name` 会被置成 `untagged-<hash>` 占位符 —— 此时发布出去，
> HACS 解析不到版本（用户收不到更新，且不报错）。
> 改完跑一次这条命令即可确认/修复（按 tag 定位，找不到就失败，不乱改）：
>
> ```bash
> ./scripts/gh-release-bind.sh C3H3-AI/ha-lixiang v1.4.6
> ```
>
> 工作流里的自动校验是**按 release id** 定位的（不全局搜索草稿）——
> 因为 Release 列表是最终一致性的，"找第一个 untagged 草稿"会抓错对象，
> 把两个草稿的绑定互相串掉（v1.2.4 / v1.4.6 都踩过）。

**为什么不自动发布**（与本项目其他机制一致）：
- 版本号是**维护者**的决定 —— 不猜、不自动 bump
- 打 tag 是**不可逆**动作 —— workflow 只读检查 tag，**从不创建 tag**
- Release 正文可能需要人工调整

**与 `li-release.sh` 的分工**：

| | 谁做 | 做什么 |
|---|---|---|
| `draft-release.yml` | 自动 | 版本号变了就建**草稿**提醒 |
| `li-release.sh` | 人工 | 打**注释** tag + 建正式 Release |

> 两者不冲突：若你先跑了 `li-release.sh`，tag 已存在 → workflow 自动跳过。
> 若 workflow 先建了草稿，你跑 `li-release.sh` 时它会看到 tag 不存在而正常发布，
> 之后把草稿 Publish 或删掉即可（`gh release view` 会提示已存在）。

**守卫测试**：`tests/test_draft_release_workflow.py`（19 例）——
包括「必须是 draft」「不许自动打 tag」「不许自动 bump 版本」「必须幂等」
这些安全底线，防止以后被改坏。

### ★★ 现在用脚本：`./scripts/li-release.sh <版本号>`

上面 ③④ 手敲容易漏（**2026-09-28 实测：重建仓库后所有历史 tag 全丢，
漂了很久没人发现**，直到跑 `li-status.sh` 才暴露「没有任何 v* tag」；
Release 正文当时还是临时写 python 从 CHANGELOG 抽的，没有固化）。

```bash
./scripts/li-release.sh 1.2.1 --dry-run   # 只校验，不做任何写操作
./scripts/li-release.sh 1.2.1             # 完整发布（会二次确认）
./scripts/li-release.sh 1.2.1 --yes       # 跳过确认
```

它会：校验①在 main ②工作区干净 ③`manifest` 版本 == 目标 ④CHANGELOG 有该版本段
⑤tag 尚不存在 → 确认 tag 指向 main HEAD → 打**注释** tag 并推送 →
**从 CHANGELOG 自动抽 Release 正文** → 建 Release → 复查 `li-status.sh`。

> **版本号是维护者的决定**：脚本不猜版本、不自动 `bump.sh`，必须显式传入。
> 传错版本（与 `manifest.json` 不一致）会被直接拒绝。


> 1.0 之后不再标 prerelease（v0.11.0 之前才需要）。

### ★★ 2026-09-27 实际踩坑：tag 落后于 main

`v1.1.0` tag 之后 main 上又合入了 2 个提交（`8ce8866` 前备箱/滑门、`511a0ea` 安全修复），
但**从未打 tag / 发 release** —— 装 HACS 发布版的用户拿不到新功能，
且版本号与代码内容不一致。漂了很久没人发现，因为**没有任何机制会检查这件事**。

**现在有了** —— 提 PR 前 / 发版前先跑：

```bash
./scripts/li-status.sh          # 五项巡检，见下表
./scripts/li-status.sh --quiet  # 只在有告警时输出
```

> 脚本在仓库内（`scripts/li-status.sh`），clone 下来即可用。
> 可用环境变量覆盖默认值：`LI_REPO_DIR` / `LI_GH_REPO` / `LI_PROXY`。
> 本机默认走 `http://127.0.0.1:7890` 代理；代理不可达时自动改为直连。

### ★ ① 只对「影响用户的改动」告警

检查 ① 比较最新 tag 与 main 的差异，但**只看 HACS 会分发的内容**：

```
影响用户：custom_components/**  ·  hacs.json
不影响：  docs/ · README · CONTRIBUTING · CHANGELOG · .github/* · tests/
```

若 tag 之后只有文档/CI 改动，会显示 ✅ 而非告警 —— 用户拿到的内容完全相同，
发版没有意义。**反之只要有 `custom_components/` 改动就一定会告警。**

> 若每改一次 README 都告警，告警会退化成噪音、最后没人看 —— 
> 巡检脚本就是以这种方式失效的。（本逻辑已双向验证：
> 伪造 `custom_components/` 改动 → 正确告警。）

### 巡检项（`li-status.sh`）

| # | 检查 | 告警意味着 |
|---|---|---|
| ① | 未发布的提交（tag 之后 main 上还有多少）| 该发版了，或 tag 打漏了 |
| ② | 漂着的分支（落后 main 且未合并）| 有工作搁浅，需 rebase 或确认废弃 |
| ③ | 僵尸分支（已完全合并）| 可以删了 |
| ④ | CI 健康 | 最近有失败 |
| ⑤ | main 分支保护 | 保护被关掉了（正常情况下应为已开启）|

#### 三种输出级别：`✓` / `!` / `?`

| 标记 | 含义 | 计入「需要处理」 |
|---|---|---|
| `✓` | 正常 | 否 |
| `!` | **确实有问题** | 是 |
| `?` | **未能确认**（网络/API 失败）| **否** |

> ★ `?` 这一级是刻意加的。**「查不到」不等于「有问题」**：
> 一次网络抖动就报故障，误报累积成噪音后，巡检脚本本身就会被忽略 ——
> 那正是它要防的失效模式。
>
> 同理，②对分支的判断严格区分三种情况：
> **有开放 PR**（正常待合并）/ **确实没有 PR**（告警）/ **查不到**（`?`，不告警）。
> 宁可说「不知道」，也绝不把「没查到 PR」说成「没有 PR」——
> 那会误导人删掉正在评审的分支。

### ⚠️ 历史重写后必须重打 tag

为清除敏感信息做过 `git-filter-branch` 后，**tag 会留在旧历史上**，
且旧历史里的 CI 脚本可能仍含**真实凭据** —— 即使 main 已经干净。

```bash
# 检查：tag 是否都在 main 上
for t in $(git tag --list 'v*'); do
  git merge-base --is-ancestor "$t^{commit}" origin/main \
    && echo "✓ $t" || echo "✗ $t 不在 main（★ 危险）"
done

# 修复：把 tag 移到 main 上的对应提交，再 force push
git tag -f v1.0.0 <main上的对应commit>
git push --force origin --tags

# ★ 必须从公开仓库验证（本地看不算）
cd /tmp && git clone --depth=1 --branch v1.0.0 https://github.com/c3h3-ci/ha-lixiang.git chk
# 用你自己知道的敏感值去查（不要把真实值写进本文档或提交）
grep -rn "<你的手机号>\|<你的VIN>" chk/ || echo "干净"
```

**2026-09-27 实际踩坑**：6 个 tag（v0.9.0 ~ v1.1.0）全部指向历史重写前的记录，
其 `.github/workflows/validate.yml` 与 `.github/pre-commit.sh` 含**真实手机号/密码/VIN/设备ID**，
任何人都能 `git fetch` 到。已全部重指向 main 并验证干净。

---

## 技能文档（`docs/skills/`）

面向 AI 助手与贡献者的操作手册统一放在 **`docs/skills/<技能名>/`**：

```
docs/skills/lixiang-task-master/
├── SKILL.md              # 必须：带 YAML frontmatter（name + description）
├── references/           # 可选：详细参考资料
└── locales/              # 可选：多语言文案
```

### 规则

1. **位置固定为 `docs/skills/`** —— 不要放 `.mimocode/`、`.claude/` 等其它
   工具的目录（那是各工具的私有约定，本仓库不采用）
2. `SKILL.md` **必须带 frontmatter**（`name` + `description`），否则 AI 助手
   无法识别该技能
3. `docs/*.md` 被 `.gitignore` 忽略（逆向文档不公开），但 `docs/skills/**`
   有**显式白名单**，可正常提交
4. **改完技能文档必须同步到本机**，否则 AI 助手加载的仍是旧版：

```bash
./scripts/li-skills.sh status    # 查看仓库 ↔ 本机差异
./scripts/li-skills.sh install   # 同步到本机
./scripts/li-skills.sh check     # 一致性校验（不一致退出 1）
```

安装目标是 `${DSH_HOME:-~/.dsh}/skills/<技能名>/`。

### ⚠️ 教训（2026-10-08）

技能文档曾出现两类问题，都已修复，现在是脚本兜底：

| 问题 | 后果 |
|---|---|
| 放在 `.mimocode/skills/`（别的工具约定）| AI 助手**完全看不到**该技能（不在 skill catalog 里）|
| 仓库文档更新后本机未同步 | 内容漂移：本机是旧版、仓库是新版，两边说法不一致 |

同一时期还发现文档描述**滞后于代码**（PR #11 只改了代码与行内注释，
技能文档仍写着已删除的「scope 回退」机制和错误的签名归因）——
**改代码时请一并检查 `docs/skills/` 是否需要同步更新。**

> 技能内容里不要出现个人环境信息（本机绝对路径、内网 IP、Windows 用户名），
> 一律使用通用路径（如 `custom_components/lixiang_auto`）。

---

## 相关脚本

| 脚本 | 位置 | 作用 |
|---|---|---|
| `scripts/li-pr.sh` | 仓库内 | PR 工作流（建分支/提交/开 PR）|
| `scripts/li-status.sh` | 仓库内 | ★ 仓库巡检（未发布提交/漂着分支/CI/分支保护）|
| `scripts/li-verify.sh` | 仓库内 | 实机验证（7 项，含重启 HA + 真实数据）|
| `scripts/li-sync.sh` | 仓库内 | 双副本同步 + 敏感扫描 |
| `scripts/li-skills.sh` | 仓库内 | 技能文档同步 / 一致性校验（`docs/skills/` ↔ 本机）|
| `bump.sh` | `ha-lixiang/` | 版本号递增 |

### 提 PR 前的自检

```bash
./li-verify.sh             # 实机验证 7 项全过
./scripts/li-status.sh     # 仓库体检无告警
./scripts/li-skills.sh check   # 技能文档与本机一致（改过 docs/skills/ 时必做）
```
