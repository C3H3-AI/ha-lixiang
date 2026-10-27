"""哨兵视频列表（get_sentinel_videos）—— 解析层单测。

2026-10-27 新增。接口规格来自 L7 车主实测（issue #140）：
  GET /ssp-travel-x-service/v1-0/sentinel/videos/{VIN}
  data = 近 7 天事件列表；videoList 是 JSON 字符串（非数组）。
"""
from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

PKG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _li_api_module():
    """加载 li_api（绕过 ha-lixiang/__init__.py 的 HA 依赖）。

    模式取自 tests/test_command_error_label.py：HA 相关模块用 MagicMock 桩，
    lixiang_auto 包用只带 __path__ 的假模块替代，跳过 __init__。
    """
    if "homeassistant" not in sys.modules:
        ha = types.ModuleType("homeassistant")
        ha_exc = types.ModuleType("homeassistant.exceptions")
        ha_exc.HomeAssistantError = type("HomeAssistantError", (Exception,), {})
        for name in ("homeassistant.util", "homeassistant.helpers",
                     "homeassistant.config_entries", "homeassistant.const"):
            sys.modules.setdefault(name, MagicMock())
        sys.modules["homeassistant"] = ha
        sys.modules["homeassistant.exceptions"] = ha_exc
    if "lixiang_auto" not in sys.modules:
        pkg = types.ModuleType("lixiang_auto")
        pkg.__path__ = [str(PKG)]
        sys.modules["lixiang_auto"] = pkg
    importlib.invalidate_caches()
    return importlib.import_module("lixiang_auto.li_api")


def _mod():
    return _li_api_module()


def _parse(r: dict, limit: int = 20) -> dict:
    return _mod()._parse_sentinel_events(r, limit)


# ---------- 解析逻辑 ----------


def test_parse_normal_events():
    r = {"code": 0, "data": [
        {"eventId": "e1", "uploadStartTs": 1730000000000, "uploadStatus": 2,
         "videoList": json.dumps([
             {"coverFilekey": "c1", "eventDirection": "FL",
              "videoFilekey": "v1"}])},
    ]}
    out = _parse(r)
    assert out["count"] == 1
    ev = out["events"][0]
    assert ev["eventId"] == "e1"
    assert ev["videos"][0]["videoFilekey"] == "v1"


def test_parse_video_list_is_json_string():
    """videoList 是 JSON 字符串 —— 必须二次解析（规格关键点）。"""
    inner = [{"coverFilekey": "c", "eventDirection": "FR",
              "videoFilekey": "v"}]
    r = {"code": 0, "data": [
        {"eventId": "e", "uploadStartTs": 1, "uploadStatus": 1,
         "videoList": json.dumps(inner)}]}
    out = _parse(r)
    assert isinstance(out["events"][0]["videos"], list)
    assert out["events"][0]["videos"][0]["videoFilekey"] == "v"


def test_parse_video_list_empty_string():
    r = {"code": 0, "data": [
        {"eventId": "e", "uploadStartTs": 1, "uploadStatus": 0,
         "videoList": ""}]}
    out = _parse(r)
    assert out["events"][0]["videos"] == []


def test_parse_video_list_broken_json():
    r = {"code": 0, "data": [
        {"eventId": "e", "uploadStartTs": 1, "uploadStatus": 0,
         "videoList": "{not-json"}]}
    out = _parse(r)
    assert out["events"][0]["videos"] == []


def test_parse_dict_wrapped_data():
    """容错：data 有时是 {"events":[...]} 包一层。"""
    r = {"code": 0, "data": {"events": [
        {"eventId": "e", "uploadStartTs": 1, "uploadStatus": 1,
         "videoList": "[]"}]}}
    out = _parse(r)
    assert out["count"] == 1


def test_parse_limit():
    evs = [{"eventId": f"e{i}", "uploadStartTs": i, "uploadStatus": 1,
            "videoList": "[]"} for i in range(10)]
    out = _parse({"code": 0, "data": evs}, limit=3)
    assert out["count"] == 3


def test_parse_error_passthrough():
    out = _parse({"code": 100105, "msg": "用户未登录"})
    assert "error" in out


def test_parse_skips_non_dict_entries():
    r = {"code": 0, "data": ["junk", None,
                             {"eventId": "ok", "uploadStartTs": 1,
                              "uploadStatus": 1, "videoList": "[]"}]}
    out = _parse(r)
    assert out["count"] == 1 and out["events"][0]["eventId"] == "ok"


# ---------- services.yaml 注册 ----------

def test_service_registered():
    import yaml
    d = yaml.safe_load(open(
        "custom_components/lixiang_auto/services.yaml", encoding="utf-8"))
    assert "get_sentinel_videos" in d
    f = d["get_sentinel_videos"]["fields"]
    assert "vin" in f and "limit" in f


def test_service_constant_matches_yaml():
    src = open("custom_components/lixiang_auto/__init__.py",
               encoding="utf-8").read()
    assert 'SERVICE_GET_SENTINEL_VIDEOS = "get_sentinel_videos"' in src
