#!/usr/bin/env python3
"""VSS 路径有效性审计 —— 找出服务端会拒绝的路径。

为什么需要它
------------
服务端对**任一无效路径**返回 400 `invalid_path`，导致**整批** VSS 请求失败。
而轮询路径来自 signals.py（`by_freq` / `paths_for`），**不按车型过滤** ——
也就是说一个无效路径会：

  ① 让那个实体永远拿不到数据（状态 unknown / 显示错误）
  ② 每一轮都让整批失败 → coordinator 触发二分重试 → 长期白白多花请求

本仓库已经因此踩过两次：
  · `Vehicle.Body.DoorSwitchStatus.FrontTrunkDoor`（前备箱，2026-09-28 修）
  · `Vehicle.Body.SeatLDoor.DoorStatus` / `SeatRDoor.DoorStatus`（滑门，2026-09-28 修）

用法
----
在**能访问理想 API 的环境**里跑（例如 HA 测试机容器内）：

    docker cp tools/audit_vss_paths.py <容器>:/tmp/
    docker exec <容器> python3 /tmp/audit_vss_paths.py

它会分批请求，遇到 400 就二分定位到具体路径，最后列出所有无效路径
及其对应的信号 key。

退出码：0 = 全部有效；1 = 发现无效路径（可用于 CI，但需要真实凭据，
故默认不接入 CI，人工定期跑）。
"""

from __future__ import annotations

import json
import sys
import time


def main() -> int:
    # 允许以包内模块方式导入（在 HA 容器里）
    sys.path.insert(0, "/config")
    try:
        from custom_components.lixiang_auto import signals as sg
        from custom_components.lixiang_auto.li_api import LiApiClient
        import custom_components.lixiang_auto.li_api as L
        import custom_components.lixiang_auto.const as C
    except Exception as err:  # noqa: BLE001
        print(f"导入失败（需在 HA 环境运行）: {err}")
        return 2

    d = json.load(open("/config/.storage/core.config_entries"))
    e = [x for x in d["data"]["entries"] if x.get("domain") == "lixiang_auto"][0]["data"]
    api = LiApiClient(
        phone=e.get("phone", ""), password=e.get("password", ""), vin=e["vin"],
        hac_key=e.get("hac_key") or C.DEFAULT_HAC_KEY,
        key_id=e.get("key_id") or C.DEFAULT_KEY_ID,
        xdev=e.get("x_chj_deviceid") or C.DEFAULT_XDEV,
        app_token=e.get("app_token") or C.DEFAULT_APP_TOKEN,
        device_id=e.get("device_id", ""), refresh_token=e.get("refresh_token", ""))

    paths = sorted({s.path for s in sg.SIGNALS.values() if s.path})
    print(f"待审计路径: {len(paths)}")

    state = {"tok": None, "reqs": 0}

    def call(batch):
        state["reqs"] += 1
        if state["tok"] is None:
            state["tok"] = api._get_scoped("vss", L.SCOPE_VSS, L.AUD_VSS)
        body = json.dumps({"vin": api._vin, "paths": batch})
        return api._signed_call(
            "POST", "/ssp-cloud-vss-service/mobile/vss/get-batch", body, state["tok"])

    def probe(batch: list[str]) -> list[str]:
        """返回 batch 中的无效路径。"""
        if not batch:
            return []
        try:
            call(batch)
            return []
        except Exception as ex:  # noqa: BLE001
            msg = str(ex)
            if "invalid_path" in msg:
                if len(batch) == 1:
                    return batch
                mid = len(batch) // 2
                return probe(batch[:mid]) + probe(batch[mid:])
            if "401" in msg or "Unauthorized" in msg:
                state["tok"] = None
                time.sleep(1)
                return probe(batch)
            return []  # 其他错误不计入 invalid_path

    bad: list[str] = []
    B = 40
    for i in range(0, len(paths), B):
        bad += probe(paths[i:i + B])

    print(f"请求次数: {state['reqs']}")
    print(f"\n❌ 无效路径: {len(bad)} 个")
    for p in bad:
        keys = [k for k, s in sg.SIGNALS.items() if s.path == p]
        print(f"   {p}")
        print(f"      ← 信号: {keys}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
