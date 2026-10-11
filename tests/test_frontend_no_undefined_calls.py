"""前端卡片「调用了不存在的方法」守卫（2026-10-11）。

事故
----
车主在真机上拖动地图，HA 前端日志报：

```
Uncaught error from Chrome 144.0.0.0 on Android 10
TypeError: this._positionTiles is not a function
  at move (/lixiang_auto/lixiang-cards/lixiang-location-page.js:562:14)
```

`_positionTiles()` 在拖动回调里被调用，但**从未定义** → 地图一拖就崩。

★ 这是同类问题**第二次**出现（第一次是 `_st()` 未定义，被
  `test_frontend_bindings.py` 抓到）。所以这里把检测**独立**出来并加固。

判定规则
--------
`this._x()` 调用要被接受，必须满足其一：
1. 本文件里有定义（含 `async` / `get` / `set` 前缀）
2. 是**带守卫**的防御性调用 —— `if (this._x) …` / `this._x && …` / `if (this._x …`
   （本仓库确实有这种写法：`if (this._cleanupScroll) { … }`，方法可能不存在）

★ 教训：上一版扫描用 `^\\s*`（`\\s` 含换行）导致**跨行误匹配**，把所有方法都报成缺失；
  改用 `^[ \\t]*` 后才准确。所以本文件带**自检**，证明检测真的能发现问题。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"

_METHOD_DEF = re.compile(r'^[ \t]*(?:async\s+|get\s+|set\s+)?(_[A-Za-z]\w*)\s*\(', re.M)
_ASSIGN_DEF = re.compile(r'(?:this\.)?(_[A-Za-z]\w*)\s*=\s*(?:async\s+)?(?:function|\()')
_CALL = re.compile(r'this\.(_[A-Za-z]\w*)\s*\(')


def _defs(src: str) -> set[str]:
    return set(_METHOD_DEF.findall(src)) | set(_ASSIGN_DEF.findall(src))


def _guarded(src: str, name: str, pos: int) -> bool:
    """该调用点前 60 字符内是否有存在性守卫。"""
    head = src[max(0, pos - 60):pos]
    return bool(
        re.search(r'if\s*\(\s*this\.' + name + r'\s*\)', head)
        or re.search(r'this\.' + name + r'\s*&&', head)
        or re.search(r'if\s*\(\s*this\.' + name + r'\b', head)
    )


def find_unguarded_undefined(src: str) -> list[str]:
    """返回「无守卫且未定义」的方法名（排序去重）。"""
    defined = _defs(src)
    out: set[str] = set()
    for m in _CALL.finditer(src):
        name = m.group(1)
        if name in defined:
            continue
        if _guarded(src, name, m.start()):
            continue
        out.add(name)
    return sorted(out)


class TestNoUndefinedCalls:
    def test_all_cards_clean(self):
        problems = {}
        for p in sorted(CARDS.glob("*.js")):
            miss = find_unguarded_undefined(p.read_text(encoding="utf-8"))
            if miss:
                problems[p.name] = miss
        assert not problems, (
            "以下卡片调用了「无守卫且未定义」的方法（运行时会 TypeError）：\n"
            + "\n".join(f"  {k}: {v}" for k, v in problems.items()))

    def test_position_tiles_now_defined(self):
        """★ 回归锁定：`_positionTiles` 必须同时有【定义】和【调用】。

        事故前它只有调用 —— 拖动地图立刻崩。
        """
        s = (CARDS / "lixiang-location-page.js").read_text(encoding="utf-8")
        assert "_positionTiles" in _defs(s), "_positionTiles 又变成未定义了"
        # 且必须仍在拖动回调里被调用（否则拖动不再跟随）
        i = s.index("const move = (e) =>")
        assert "_positionTiles()" in s[i:i + 400], "拖动回调应调用 _positionTiles"


class TestDetectorSelfCheck:
    """★ 证明检测器真能发现问题（否则这守卫就是装饰品）。"""

    def test_catches_the_original_bug(self):
        src = ('class X {\n'
               '  _drawMap() {}\n'
               '  wire() {\n'
               '    const move = (e) => { this._positionTiles(); };\n'
               '  }\n'
               '}\n')
        assert find_unguarded_undefined(src) == ["_positionTiles"]

    def test_accepts_defined_method(self):
        src = 'class X {\n  m() { this._ok(); }\n  _ok() {}\n}\n'
        assert find_unguarded_undefined(src) == []

    def test_accepts_guarded_call(self):
        """仓库里真实存在的写法：`if (this._cleanupScroll) { … }`。"""
        src = ('class X {\n'
               '  m() { if (this._cleanupScroll) { this._cleanupScroll(); this._cleanupScroll = null; } }\n'
               '}\n')
        assert find_unguarded_undefined(src) == []

    def test_accepts_async_and_get_set_defs(self):
        src = ('class X {\n'
               '  m() { this._fetch(); this._g(); this._s(); }\n'
               '  async _fetch() {}\n'
               '  get _g() { return 1; }\n'
               '  set _s(v) {}\n'
               '}\n')
        assert find_unguarded_undefined(src) == []

    def test_does_not_cross_lines(self):
        """★ 上一版扫描的坑：`\\s` 含换行会跨行误匹配 → 把一切报成缺失。"""
        src = ('class X {\n'
               '  _something() {\n'
               '    this._other();\n'
               '  }\n'
               '  _other() {}\n'
               '}\n')
        assert find_unguarded_undefined(src) == []