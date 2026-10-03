"""从 VSS 直接取 fileKeys（2026-10-03 决定性修正）。

## 为什么改

此前 `svm_photo_filekeys()` **自己拼路径**：

    vehicle/svm_photo/{车型}/{日期}/{VIN}/data/data_center/upload/{时间戳}picIn{方位}.jpg

拼出来的 key 在 OSS 里**不存在** → 接口返回 `data:{}` → 卡片永远显示「图片已过期」。

## 真正的做法（依据 APK 的 XPhotoDataHandle.smali）

`sget` / `invoke-` 序列逐行可读：

    item = map.get("Vehicle.360Svm.Park.Filekey")
    json = item.getDp().getValue()
    fileKeys = new Gson().fromJson(json, JsonObject.class)
                     .get("fileKeys").getAsJsonObject()   ← ★ 服务端直接给
    map = gson.fromJson(fileKeys, Map.class)
    list = new ArrayList<>(map.values())
    → translatePhoto(list, model)  →  /ois/file/service/urls?fileKeys=<list>

**关键**：文件名里的时间戳与 `picTime` **并不相同**：

    picTime   = "2026-09-05 20:27:20"
    文件名    = "20260905202717"                 ← 差 3 秒

所以拼路径**必然**失败，必须用服务端给的 fileKeys。

## 另外修正的方位名

APK 的 CarPhotoAdapter 里是 `picInRear/picInFront/picInRight/picInLeft/picInTop`
—— 第 5 个是 `picInTop`（不是 `picTopview`，那是 UI 层的 label）。
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "custom_components" / "lixiang_auto" / "li_api.py"


def _load(fn_name: str):
    """从 li_api.py 提取方法源码并 exec（避开 HA 依赖链）。

    兼容两种情况：带 `@staticmethod` 与不带。
    """
    import re
    src = API.read_text(encoding="utf-8")
    m = re.search(
        rf"^(    (?:@staticmethod\n    )?def {fn_name}\(.*?)(?=^    (?:@staticmethod\n    )?def |\Z)",
        src, re.M | re.S)
    assert m, f"找不到 {fn_name}"
    block = textwrap.dedent(m.group(1))
    ns: dict = {"json": json, "staticmethod": staticmethod}
    exec(block, ns)
    return ns[fn_name]


# 结构照真实 VSS 返回（值用构造数）
SAMPLE = {
    "picProduct": 0,
    "picTime": "2026-09-05 20:27:20",
    "picTimestamp": 1788611240947,
    "process": False,
    "fileKeys": {
        "picInRear": "vehicle/svm_photo/X04/20260905/VIN0000000000000"
                     "/data/data_center/upload/20260905202717picInRear.jpg",
        "picInFront": "vehicle/svm_photo/X04/20260905/VIN0000000000000"
                      "/data/data_center/upload/20260905202717picInFront.jpg",
        "picInRight": "vehicle/svm_photo/X04/20260905/VIN0000000000000"
                      "/data/data_center/upload/20260905202717picInRight.jpg",
        "picInLeft": "vehicle/svm_photo/X04/20260905/VIN0000000000000"
                     "/data/data_center/upload/20260905202717picInLeft.jpg",
        "picInTop": "vehicle/svm_photo/X04/20260905/VIN0000000000000"
                    "/data/data_center/upload/20260905202717picInTop.jpg",
    },
}


class TestFilekeysFromVss:
    def test_extracts_five(self):
        fn = _load("svm_filekeys_from_vss")
        got = fn(json.dumps(SAMPLE))
        assert len(got) == 5
        assert set(got) == {"picInRear", "picInFront", "picInRight",
                            "picInLeft", "picInTop"}

    def test_accepts_dict_too(self):
        fn = _load("svm_filekeys_from_vss")
        assert fn(SAMPLE) == fn(json.dumps(SAMPLE))

    def test_stamp_differs_from_pictime(self):
        """★ 核心：文件名时间戳 ≠ picTime —— 这就是不能拼路径的原因。"""
        fn = _load("svm_filekeys_from_vss")
        got = fn(json.dumps(SAMPLE))
        assert "20260905202717" in got["picInRear"]
        assert "20260905202720" not in got["picInRear"], \
            "若用了 picTime 拼路径就会得到 20260905202720（OSS 里不存在）"

    @pytest.mark.parametrize("bad,desc", [
        (None, "None"), ("", "空串"), ("not json", "非法 JSON"),
        ("{}", "空对象"), ('{"picTime":"x"}', "无 fileKeys"),
        ('{"fileKeys":{}}', "fileKeys 空"), ('{"fileKeys":null}', "fileKeys null"),
        ("[]", "数组"), ('"str"', "纯字符串"), ("123", "数字"),
    ])
    def test_bad_input_returns_empty(self, bad, desc):
        fn = _load("svm_filekeys_from_vss")
        assert fn(bad) == {}, f"{desc} 应返回空 dict"

    def test_filters_non_string_values(self):
        fn = _load("svm_filekeys_from_vss")
        got = fn('{"fileKeys":{"a":1,"b":"","c":"x"}}')
        assert got == {"c": "x"}, "非字符串/空串应被过滤"


class TestPicTime:
    def test_reads_pictime(self):
        fn = _load("svm_pic_time")
        assert fn(json.dumps(SAMPLE)) == "2026-09-05 20:27:20"

    def test_falls_back_to_timestamp(self):
        fn = _load("svm_pic_time")
        assert fn('{"picTimestamp":1788611240947}') == "1788611240947"

    def test_bad_input_empty(self):
        fn = _load("svm_pic_time")
        for bad in (None, "", "nope", "{}"):
            assert fn(bad) == ""


class TestServiceUsesVss:
    """服务必须【优先用 VSS 的 fileKeys】，而不是拼路径。"""

    def _svc(self) -> str:
        src = (ROOT / "custom_components" / "lixiang_auto" / "__init__.py")
        s = src.read_text(encoding="utf-8")
        i = s.index("async def _handle_get_svm_photo")
        return s[i:s.index("hass.services.async_register(DOMAIN, SERVICE_GET_SVM_PHOTO")]

    def test_prefers_vss_filekeys(self):
        body = self._svc()
        assert "svm_filekeys_from_vss" in body, "服务未使用 VSS 的 fileKeys"
        # VSS 路径必须出现在拼路径兜底【之前】
        i_vss = body.index("svm_filekeys_from_vss")
        i_fallback = body.index("svm_photo_filekeys")
        assert i_vss < i_fallback, "VSS 取法必须在兜底拼路径之前"

    def test_reads_correct_signal(self):
        body = self._svc()
        assert "Vehicle.360Svm.Park.Filekey" in body
