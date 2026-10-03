"""Li Auto 理想汽车 API 客户端.

基于越狱 iOS 版逆向 + 端到端验证的请求方案:
- 签名: 11参数 \n 拼接 + 末尾 \n; HMAC key = hac_key 原始字节
- 认证: X-CHJ-TOKEN (APP- 前缀的静态令牌), 由 frida 从 app 抓取
- 已验证: GET /aisp-account-api/v1-0/vehicles 返回真实车辆

车辆实时状态(电量/续航/门锁)经 LiMesh+VSS 从车机同步到 iPad 本地库，
非本 HTTP 客户端直接提供；本客户端提供车辆配置/列表/命令类数据。
"""

from __future__ import annotations

import json
import logging
import uuid

import aiohttp

from .const import (
    API_APP,
    CONTENT_LANG,
    CONTENT_TYPE,
    DEFAULT_ACCEPT,
    DEVICE_MODEL,
    DEVICE_TYPE,
    EP_VEHICLE_BASICS,
    EP_VEHICLES,
    MODEL_NAME,
)
from .signer import LiCarSigner

_LOGGER = logging.getLogger(__name__)


class LiCarApiError(RuntimeError):
    """理想 API 错误"""


class LiCarClient:
    """理想汽车 API 客户端"""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        signer: LiCarSigner,
        app_token: str = "",          # X-CHJ-TOKEN (APP-xxx)
        vin: str | None = None,
    ) -> None:
        self._session = session
        self._signer = signer
        self._app_token = app_token
        self._vin = vin

    async def _request(self, method: str, path: str, body: str = "") -> dict:
        """带完整签名 header 的理想 API 请求（端到端验证方案）"""
        url = f"{API_APP}{path}"
        headers = self._signer.build_headers(method, body)
        # 补充理想 iOS app 实际发送的完整 header
        headers["X-CHJ-Version"] = self._signer.app_version
        headers["X-CHJ-DeviceType"] = DEVICE_TYPE
        headers["X-CHJ-ModelName"] = MODEL_NAME
        headers["X-CHJ-DeviceModel"] = DEVICE_MODEL
        headers["X-CHJ-Tag"] = "1"
        headers["X-CHJ-TOKEN"] = self._app_token
        headers["X-CHJ-TraceId"] = uuid.uuid4().__str__()
        headers["User-Agent"] = (
            f"m01/{self._signer.app_version} (iPad; iOS; Scale/2.00)"
        )
        if self._vin:
            headers["X-CHJ-VIN"] = self._vin
        headers["Content-Type"] = CONTENT_TYPE
        headers["Content-Language"] = CONTENT_LANG
        headers["Accept"] = DEFAULT_ACCEPT

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                data=body if body else None,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                data = await resp.json()
                if not data.get("success", True) and data.get("code", 0) != 0:
                    raise LiCarApiError(
                        f"{method} {path} failed: code={data.get('code')} "
                        f"msg={data.get('msg', data.get('message'))}"
                    )
                return data.get("data", data)
        except aiohttp.ClientError as err:
            raise LiCarApiError(f"Network error: {err}") from err

    async def get_vehicles(self) -> list[dict]:
        """获取车辆列表（已验证返回 vehicleBasicList）"""
        data = await self._request("GET", EP_VEHICLES)
        if isinstance(data, dict):
            lst = data.get("vehicleBasicList") or data.get("vehicles") \
                or data.get("list") or data.get("data")
            if isinstance(lst, list):
                return lst
        if isinstance(data, list):
            return data
        return []

    async def get_vehicle(self) -> dict | None:
        """获取当前 VIN 车辆详情"""
        if not self._vin:
            return None
        try:
            return await self._request("GET", f"/aisp-account-api/v1-0/vehicles/{self._vin}")
        except LiCarApiError:
            return None

    async def get_vehicle_basics(self) -> dict | None:
        """读取车辆基础信息 basics（含 vehicleStatus 在线标记 / deviceId / 配置）.

        已验证真实返回（用 iPad 提取凭证可读）。响应 data 可能是 string 包裹的
        JSON 或 list。basics 提供的是静态车辆信息 + 在线状态(vehicleStatus)，
        不含电量/续航（那走 LiMesh VSS 通道）。
        """
        if not self._vin:
            return None
        # basics 必须带 query 参数才返回该用户的车辆数据(裸路径返回 [])
        # 参数对齐已验证的完整 basics 请求
        query = (
            "?locked=0&includeVehicle=1"
            "&types=owned%2Ctransferring%2Cauthorized%2Cinviting"
            "&roleIds=1%2C10%2C11%2C13%2C15"
            "&vehicleInfo=1"
        )
        try:
            data = await self._request("GET", EP_VEHICLE_BASICS + query)
        except LiCarApiError:
            return None
        # 响应可能是 "{\"data\": [...]}" 的字符串, 或已解析 dict
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except Exception:
                return None
        if isinstance(data, dict):
            data = data.get("data", data)
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return None

    async def update(self) -> dict:
        """更新数据（coordinator 调用）: 读车辆列表 + 当前车 basics.

        静态接口的 X-CHJ-TOKEN 过期(240225)不影响实时信号通道 — 各自容错。
        """
        data: dict = {}
        # ★ 车辆列表改用 saos-vehicle-api（2026-09-23 修复）
        #   旧的 /aisp-account-api/v1-0/vehicles 依赖已过期的 X-CHJ-TOKEN
        #   → 每次轮询都返回 240225，产生固定噪声日志。已移除该调用。
        data["vehicles"] = []
        try:
            basics = await self.get_vehicle_basics()
        except LiCarApiError as err:
            _LOGGER.warning("basics 读取失败(不影响实时信号): %s", err)
            basics = None
        data["basics"] = basics
        if isinstance(basics, dict):
            vi = basics.get("vehicleInfo")
            if isinstance(vi, dict):
                data["vehicle_status"] = vi.get("vehicleStatus")
                data["device_id"] = vi.get("deviceId")
            data["vehicle_role"] = basics.get("vehicleRoleId")
        return data

    # ================== L6 实时状态/车控（后端，凭证到位即通） ==================
    # 说明: L6 的实时状态(电量/门锁等)鸿蒙App经 service-card + vss/get-batch HTTP 读取,
    #       需对应 aud 的 Bearer(由 auth.LiBearerTokenMgr 用主Bearer换取).
    #       实测 iOS 用纯 X-CHJ 凭证 service-card 返 data:null → 必须带 login aud Bearer.

    async def _bearer_request(
        self, method: str, path: str, bearer: str, body: str = ""
    ) -> dict:
        """带 Bearer(scope token) + X-CHJ-TOKEN 的请求(鸿蒙 service-card 认证方式)."""
        url = f"{API_APP}{path}"
        headers = self._signer.build_headers(method, body)
        headers["X-CHJ-TOKEN"] = self._app_token
        headers["Authorization"] = f"Bearer {bearer}"
        headers["Content-Type"] = CONTENT_TYPE
        headers["Content-Language"] = CONTENT_LANG
        headers["Accept"] = DEFAULT_ACCEPT
        if self._vin:
            headers["X-CHJ-VIN"] = self._vin
        try:
            async with self._session.request(
                method, url, headers=headers,
                data=body if body else None,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                return await resp.json()
        except aiohttp.ClientError as err:
            raise LiCarApiError(f"Network error: {err}") from err

    async def get_service_card(self, bearer: str) -> dict:
        """service-card 首页状态. 返回 data(含状态) 需带 login aud Bearer."""
        if not self._vin:
            return {}
        resp = await self._bearer_request(
            "GET", f"/saos-agg-api/service-card/card?vin={self._vin}", bearer
        )
        return resp.get("data") or {}

    async def get_vss_state(self, bearer: str, paths: list[str] | None = None) -> dict:
        """vss/get-batch 批量取车辆信号(VSS), 需带 vss:get-batch scope Bearer."""
        body = json.dumps({"paths": paths or []})
        resp = await self._bearer_request(
            "POST", "/ssp-cloud-vss-service/mobile/vss/get-batch", bearer, body
        )
        return resp

    # ---------------- 车控 ----------------
    async def send_vehicle_command(
        self, ctrl_bearer: str, command_key: str, extra: dict | None = None
    ) -> dict:
        """车控命令下发(cmd/send). command_key 如 lock/unlock/ac/find/window.
        需带车控 scope token(remoteVeh*Control:VIN). body 结构按需调整."""
        if not self._vin:
            return {}
        body = json.dumps({"vin": self._vin, "commandKey": command_key,
                           **(extra or {})})
        resp = await self._bearer_request(
            "POST", "/ssp-vehicle-control-service/ssp-vehicle-control/cmd/send",
            ctrl_bearer, body,
        )
        return resp
