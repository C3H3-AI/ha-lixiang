"""驻车照片（SVM）链路测试（2026-10-03）。

## 依据

从抓包 ``data/2026-05-05_licar_captures.json``（lixiang-reverse 仓库）
里的**真实请求**逆向出完整链路：

    GET /chehejia-service-ois-app/ois/file/service/urls
        ?fileKeys=<逗号分隔的 OSS key>&identify=vehicle

    OSS key 模板：
      vehicle/svm_photo/{车型代码}/YYYYMMDD/{VIN}/data/data_center/upload/
          {YYYYMMDDHHmmss}pic{方位}.jpg

抓包原文（VIN 已脱敏）：

    vehicle/svm_photo/X04/20260505/{VIN}/data/data_center/upload/
        20260505202638picInRear.jpg

方位 5 路：Front / Rear / Left / Right / Top

## 为什么这些测试值得存在

模板一旦写错（大小写、段数、时间格式），接口会返回空 URL 而**不报错**
—— 卡片只是不显示图片，用户无从判断是「没拍照」还是「我们拼错了 key」。
所以必须有测试钉住模板，且必须与抓包原文逐字符比对。
"""

from __future__ import annotations

import re
import textwrap
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "custom_components" / "lixiang_auto" / "li_api.py"

TEST_VIN = "HLX32TESTVIN00000"


def _src() -> str:
    return API.read_text(encoding="utf-8")


class _Fake:
    """svm_photo_filekeys 用到的 self 属性替身。"""

    SVM_ANGLES = ("Front", "Rear", "Left", "Right", "Top")
    _vin = TEST_VIN
    _car_type_code = ""


def _call_filekeys(when, car_type=""):
    """执行 li_api.py 里 **原样** 的 svm_photo_filekeys 源码。

    不 import li_api（会拉起 HA 依赖链）。用 textwrap.dedent 保持
    内部缩进不变 —— 手工正则去缩进会改坏代码（实测踩过）。
    """
    src = _src()
    m = re.search(r"^    def svm_photo_filekeys\(self,.*?(?=^    def )",
                  src, re.M | re.S)
    assert m, "找不到 svm_photo_filekeys 方法"
    body = textwrap.dedent(m.group(0).split("\n", 1)[1])

    ns: dict = {"datetime": datetime, "re": re}
    exec("def _fn(self, when, car_type=''):\n"
         + textwrap.indent(body, "    "), ns)  # noqa: S102
    return ns["_fn"](_Fake(), when, car_type)


class TestFilekeyTemplate:
    """OSS key 模板必须与抓包原文一致。"""

    def test_matches_capture_verbatim(self):
        """★ 核心断言：与抓包原文逐字符比对。"""
        keys = _call_filekeys("2026-05-05 20:26:38", "X04")
        assert len(keys) == 5
        expect_rear = (f"vehicle/svm_photo/X04/20260505/{TEST_VIN}"
                       "/data/data_center/upload/20260505202638picInRear.jpg")
        assert keys[1] == expect_rear, f"与抓包不一致:\n  得到 {keys[1]}\n  期望 {expect_rear}"

    def test_accepts_datetime_object(self):
        a = _call_filekeys(datetime(2026, 5, 5, 20, 26, 38), "X04")
        b = _call_filekeys("2026-05-05 20:26:38", "X04")
        assert a == b, "datetime 与字符串入参应产生相同 key"

    def test_five_angles(self):
        keys = _call_filekeys("2026-05-05 20:26:38", "X04")
        assert len(keys) == 5
        for ang in ("Front", "Rear", "Left", "Right", "Top"):
            assert any(k.endswith(f"picIn{ang}.jpg") for k in keys), f"缺方位 {ang}"

    def test_structure(self):
        k = _call_filekeys("2026-05-05 20:26:38", "X04")[0]
        assert k.startswith("vehicle/svm_photo/")
        assert "/data/data_center/upload/" in k
        assert re.search(r"/upload/\d{14}picIn\w+\.jpg$", k), k

    def test_invalid_string_returns_empty(self):
        assert _call_filekeys("not-a-date", "X04") == []

    def test_car_type_default(self):
        keys = _call_filekeys("2026-05-05 20:26:38")
        assert all("/X04/" in k for k in keys)


class TestEndpointWiring:
    """端点与参数拼接。"""

    def _fn_body(self, name: str) -> str:
        m = re.search(rf"^    def {name}\(.*?(?=^    def )", _src(), re.M | re.S)
        assert m, f"找不到 {name}"
        return m.group(0)

    def test_urls_endpoint(self):
        assert "/chehejia-service-ois-app/ois/file/service/urls" in _src()

    def test_identify_param(self):
        """抓包里带 identify=vehicle —— 缺了会拿不到 URL。"""
        assert "identify=vehicle" in _src()

    def test_filekeys_urlencoded(self):
        """fileKey 含 '/' 必须以 %2F 传输（抓包里就是这样）。"""
        assert "quote(" in self._fn_body("get_svm_photo_urls")

    def test_all_aggregate_endpoint(self):
        """补上的 travel/all/aggregate（抓包里有、此前集成漏了）。"""
        assert "/travel/all/aggregate/" in _src()

    def test_reuses_signed_call(self):
        """必须走 App 签名通道（裸请求会 401/100105）。"""
        for name in ("get_travel_all_aggregate", "get_svm_photo_urls"):
            assert "_signed_call_travel" in self._fn_body(name), f"{name} 未用签名通道"

    def test_100105_retry(self):
        """token 过期（100105）要重登重试 —— 与 travel 同根因。"""
        for name in ("get_travel_all_aggregate", "get_svm_photo_urls"):
            assert "100105" in self._fn_body(name), f"{name} 缺 100105 重试"

    def test_svm_angles_defined(self):
        assert 'SVM_ANGLES = ("Front", "Rear", "Left", "Right", "Top")' in _src()
