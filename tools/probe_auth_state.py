"""一次性探测：车端到底有没有「授权驾驶」的实时状态字段。

★ 2026-10-17 起因（车主三次实机观察）：
   · App 远程授权 → 显示「已授权」；随后开锁 → 锁车 → 变回「授权驾驶」
   · 手机与车没有蓝牙连接；HA 点授权后 App 也显示「已授权」
   → 该状态**服务端/车端真实存在**，且**随锁车清除**
   而我们绑的 binary_sensor.车辆授权（Vehicle.Provision.Authorize.State）
   在锁车期间**纹丝不动**（实测 08:51→08:54），是账号绑定关系，不是它。

本脚本只读不写：逐条探测候选路径（服务端对任一无效 path 返回 400，
必须单条试），打印哪些路径真实存在及其取值。

用法（测试机 /config 下）：
    python3 probe_auth_state.py            # 探测一次
    python3 probe_auth_state.py --watch    # 每 5s 打印一次，用于观察锁车前后变化
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/config/custom_components")

from custom_components.lixiang_auto.li_api import LiApiClient  # noqa: E402

CFG = Path("/config/.storage/core.config_entries")

# 候选路径：覆盖官方包线索（LXVehicleBLE / Provision / ICCE / 授权）
CANDIDATES = [
    # 我们现在用的（实测长期 true，是账号绑定关系）
    "Vehicle.Provision.Authorize.State",
    # ★ 官方 smali VSSPathValue 注解里的另外两条（2026-10-17 探测发现）
    "Vehicle.Provision.Process.Complete",
    "Vehicle.Provision.Process.FinishSuccess",
    # BLE 组（官方 vehicleStateKey:'BLE'）
    "Vehicle.Ble.ConnectState",
    "Vehicle.Ble.BleConnectState",
    "Vehicle.Ble.ConnectionState",
    "Vehicle.Ble.State",
    # ICCE / 数字钥匙
    "Vehicle.Provision.Icce.State",
    "Vehicle.Provision.Authorize.IcceState",
    "Vehicle.DigitalKey.State",
    # 锁相关（对照：应随锁车变化）
    "Vehicle.Body.LockStatus.LockStatus",
    "Vehicle.Cabin.Door.LockStatus",
]


def load_api() -> LiApiClient:
    d = json.loads(CFG.read_text(encoding="utf-8"))
    entries = d["data"]["entries"] if isinstance(d["data"], dict) else d["data"]
    for e in entries:
        if isinstance(e, dict) and e.get("domain") == "lixiang_auto":
            x = e["data"]
            return LiApiClient(
                phone=x.get("phone", ""), password=x.get("password", ""),
                vin=x.get("vin", ""), hac_key=x.get("hac_key", ""),
                key_id=x.get("key_id", ""), xdev=x.get("x_chj_deviceid", ""),
                app_token=x.get("app_token", ""), device_id=x.get("device_id"),
                refresh_token=x.get("refresh_token", ""),
                main_bearer=x.get("main_bearer", "") or x.get("access_token", ""),
                session_cookies=x.get("session_cookies") or [],
            )
    raise SystemExit("找不到 lixiang_auto 配置条目")


def probe(api: LiApiClient, path: str):
    """单条探测：返回 (状态, 值)。状态 ∈ ok / invalid / error"""
    try:
        out = api.get_vss_state([path])
    except Exception as err:  # noqa: BLE001
        msg = str(err)
        if "400" in msg or "invalid_path" in msg:
            return "invalid", None
        return "error", msg[:120]
    if path in out:
        return "ok", out[path].get("value")
    return "invalid", None


def main() -> int:
    api = load_api()
    print(f"VIN: {api._vin[:8]}…   候选 {len(CANDIDATES)} 条\n")
    alive = []
    for p in CANDIDATES:
        st, val = probe(api, p)
        mark = {"ok": "✅", "invalid": "·", "error": "⚠️"}[st]
        print(f"  {mark} {p:<46} {st:<8} {val}")
        if st == "ok":
            alive.append(p)
        time.sleep(0.25)
    print(f"\n真实存在的路径 {len(alive)} 条: {alive}")

    if "--watch" in sys.argv and alive:
        print("\n=== 观察模式：每 5s 打印（现在去解锁/锁车看变化）===")
        try:
            while True:
                vals = {}
                for p in alive:
                    _, v = probe(api, p)
                    vals[p] = v
                print(f"  {time.strftime('%H:%M:%S')} " + " | ".join(
                    f"{p.split('.')[-1]}={v}" for p, v in vals.items()))
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())