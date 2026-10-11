"""车辆信息落盘缓存 —— 防止顶掉用户手机 App（2026-10-11）。

事故链条（★ 用户实测现象：「App 的任务大师无法连接，禁用集成 + 重新登录 App 才恢复」）
--------------------------------------------------------------------------------
1. 角色判定需要 `get_vehicles()`（车辆列表）
2. 它走 `saos_vehicle` token（audience `7gbeHMwBPMZA5SU1b2awIo`）
3. ★ 该 audience 白名单**只认主 App client（lixiang）**
   （`li_api._exchange_client_order` 注释：A/C ❌ → B/D ✅ 实测）
4. → 先撞一次 livis 被拒 → **回退 lixiang client 换取**
5. → 理想账号**单设备登录** → **顶掉用户手机 App**
6. 而 `current_vehicle()` 原本**无任何缓存** → 启动 1 次 + 角色判定每 6h 1 次

用户判断「参数必须写 lixiang 才能确定」是对的 —— 而且写 `livis` 也躲不掉，
因为代码会自动回退。

修复
----
角色信息**仅用于展示策略**（家人账号的只读实体默认禁用），不值得每次
顶掉用户 App → 加落盘缓存（7 天）。命中缓存则**完全不发请求**。
"""
from __future__ import annotations

import importlib.util
import json
import re
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"

# ★ 直接按文件加载：走包会触发 __init__（import homeassistant），本机无该模块
_SPEC = importlib.util.spec_from_file_location(
    "_lixiang_vehicle_role", CC / "vehicle_role.py")
vr = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(vr)

VEHICLE = {"vin": "TESTVIN", "vehicleType": "owned", "vehicleRoleId": 1}


class FakeApi:
    """记录被调用次数 —— 用来证明"缓存命中时不发请求"。"""

    def __init__(self, payload=None, boom=False):
        self.calls = 0
        self._payload = payload if payload is not None else [dict(VEHICLE)]
        self._boom = boom

    def get_vehicles(self):
        self.calls += 1
        if self._boom:
            raise RuntimeError("网络失败")
        return self._payload


class TestCacheHitAvoidsRequest:
    """★ 核心价值：缓存命中 = 零请求 = 零顶号风险。"""

    def test_hit_does_not_call_api(self, tmp_path):
        vr.save_cached_vehicle(str(tmp_path), VEHICLE)
        api = FakeApi()
        got = vr.current_vehicle(api, str(tmp_path))
        assert got == VEHICLE
        assert api.calls == 0, "缓存命中却仍发请求 → 又会顶一次 App"

    def test_miss_calls_api_and_saves(self, tmp_path):
        api = FakeApi()
        got = vr.current_vehicle(api, str(tmp_path))
        assert got == VEHICLE
        assert api.calls == 1
        # 落盘了，下次就不必再请求
        assert (tmp_path / "lixiang_vehicle_info.json").exists()
        api2 = FakeApi()
        assert vr.current_vehicle(api2, str(tmp_path)) == VEHICLE
        assert api2.calls == 0, "首次成功后应能靠缓存免请求"

    def test_expired_calls_api_again(self, tmp_path):
        vr.save_cached_vehicle(str(tmp_path), VEHICLE)
        p = tmp_path / "lixiang_vehicle_info.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        d["saved_at"] = int(time.time()) - vr.VEHICLE_CACHE_TTL - 10
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        api = FakeApi()
        vr.current_vehicle(api, str(tmp_path))
        assert api.calls == 1, "过期后应重新获取"

    def test_without_config_dir_keeps_old_behavior(self):
        """不传 config_dir → 行为同旧版（直接联网）。向后兼容。"""
        api = FakeApi()
        assert vr.current_vehicle(api) == VEHICLE
        assert api.calls == 1


class TestFailureFallback:
    """★ 联网失败时用**过期缓存兜底** —— 避免"失败→重试→再顶一次"。"""

    def test_expired_cache_used_on_error(self, tmp_path):
        vr.save_cached_vehicle(str(tmp_path), VEHICLE)
        p = tmp_path / "lixiang_vehicle_info.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        d["saved_at"] = int(time.time()) - vr.VEHICLE_CACHE_TTL - 10
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        api = FakeApi(boom=True)
        assert vr.current_vehicle(api, str(tmp_path)) == VEHICLE, \
            "联网失败时应回落到过期缓存（有数据比没有好）"

    def test_no_cache_and_error_returns_none(self, tmp_path):
        api = FakeApi(boom=True)
        assert vr.current_vehicle(api, str(tmp_path)) is None

    def test_api_called_once_per_miss(self, tmp_path):
        """失败后不应在同一次调用里反复重试（每次都换 token → 反复顶号）。"""
        api = FakeApi(boom=True)
        vr.current_vehicle(api, str(tmp_path))
        assert api.calls == 1


class TestPersistence:
    def test_perms_0600(self, tmp_path):
        vr.save_cached_vehicle(str(tmp_path), VEHICLE)
        p = tmp_path / "lixiang_vehicle_info.json"
        assert oct(p.stat().st_mode)[-3:] == "600"

    def test_atomic_no_tmp_left(self, tmp_path):
        vr.save_cached_vehicle(str(tmp_path), VEHICLE)
        assert not (tmp_path / "lixiang_vehicle_info.json.tmp").exists()

    def test_saved_at_recorded(self, tmp_path):
        vr.save_cached_vehicle(str(tmp_path), VEHICLE)
        d = json.loads((tmp_path / "lixiang_vehicle_info.json").read_text(encoding="utf-8"))
        assert isinstance(d["saved_at"], int)

    def test_corrupt_file_treated_as_miss(self, tmp_path):
        (tmp_path / "lixiang_vehicle_info.json").write_text("{坏了", encoding="utf-8")
        assert vr.load_cached_vehicle(str(tmp_path)) is None
        api = FakeApi()
        assert vr.current_vehicle(api, str(tmp_path)) == VEHICLE
        assert api.calls == 1

    def test_wrong_shape_rejected(self, tmp_path):
        (tmp_path / "lixiang_vehicle_info.json").write_text('{"x":1}', encoding="utf-8")
        assert vr.load_cached_vehicle(str(tmp_path)) is None

    def test_missing_file(self, tmp_path):
        assert vr.load_cached_vehicle(str(tmp_path)) is None

    def test_empty_config_dir_safe(self):
        assert vr.load_cached_vehicle("") is None
        assert vr.save_cached_vehicle("", VEHICLE) is False


class TestCallSitesWired:
    """★ 守卫：调用点必须传 config_dir，否则缓存形同虚设（白写）。"""

    INIT = CC / "__init__.py"
    COORD = CC / "coordinator.py"

    def test_no_bare_current_vehicle_call(self):
        """不能再有无 config_dir 的 current_vehicle(api) 调用。"""
        for f in (self.INIT, self.COORD):
            s = f.read_text(encoding="utf-8")
            bare = re.findall(r"current_vehicle\(\s*(?:self\.)?\w+\s*\)", s)
            assert not bare, (
                f"{f.name} 里还有不传 config_dir 的调用 {bare} —— "
                "那会每次都换 saos_vehicle token 顶掉用户 App")

    def test_startup_probe_uses_cache(self):
        s = self.INIT.read_text(encoding="utf-8")
        # 精确定位到"角色探测"这段代码（不是 docstring 里出现的词）
        i = s.index("from .vehicle_role import current_vehicle as _cv")
        blk = s[i:i + 700]
        assert "current_vehicle" in blk, "启动角色探测应经 current_vehicle（带缓存）"
        assert "li_api.get_vehicles()" not in blk, \
            "启动探测不应直接调 get_vehicles（那会绕过缓存、换 saos token 顶 App）"

    def test_role_judgement_uses_cache(self):
        s = self.COORD.read_text(encoding="utf-8")
        i = s.index("current_vehicle")
        blk = s[max(0, i - 300):i + 200]
        assert "_config_dir(" in blk, "角色判定应传 config_dir"

    def test_documented_why(self):
        """模块头必须写明"为什么必须缓存"——否则后人可能删掉缓存。"""
        s = (CC / "vehicle_role.py").read_text(encoding="utf-8")
        head = s[:s.index("__all__") if "__all__" in s else 4000]
        assert "saos_vehicle" in head and "顶" in head, \
            "必须写明 saos_vehicle 白名单 + 顶号后果"
        assert "只认主 App client" in head or "lixiang" in head

    def test_ttl_is_long(self):
        """★ TTL 必须足够长 —— 每次过期都意味着一次顶号风险。"""
        assert vr.VEHICLE_CACHE_TTL >= 86400, \
            "TTL 太短 → 频繁换 token → 频繁顶用户 App"


class TestTTLNotAccidental:
    def test_ttl_days_documented(self):
        s = (CC / "vehicle_role.py").read_text(encoding="utf-8")
        i = s.index("VEHICLE_CACHE_TTL")
        blk = s[max(0, i - 500):i + 120]
        assert "顶" in blk or "App" in blk, "TTL 处应说明为什么这么长"
