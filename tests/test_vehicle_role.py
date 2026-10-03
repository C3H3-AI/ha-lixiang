"""账号角色推导（vehicle_role.py）测试

★ 断言依据：App 的 `assets/index.vehicle.js` 的 `setupVehicleUserRelation()`。
  每个用例都标注了 App 原文的对应分支。
"""

from __future__ import annotations

import pytest

import vehicle_role as vr


class TestRelationOfAuthorized:
    """authorized 类型 —— 我们账号所在的类别（App: 'authorized' 分支）。"""

    @pytest.mark.parametrize("role_id", ["15", 15])
    def test_role_15_is_family_shared(self, role_id):
        """App: `'15' === String(t.vehicleRoleId)` → FamilySharedAuthorized。"""
        v = {"vehicleType": "authorized", "vehicleRoleId": role_id}
        assert vr.relation_of(v) == vr.REL_FAMILY_SHARED
        assert vr.is_family(v) is True
        assert vr.is_owner(v) is False
        assert vr.is_test_driver(v) is False

    @pytest.mark.parametrize("role_id", ["10", "13", 10, 13])
    def test_role_10_13_is_experience_driving(self, role_id):
        """App: `'10' !== String(...) && '13' !== String(...) || → ExperienceDriving`。"""
        v = {"vehicleType": "authorized", "vehicleRoleId": role_id}
        assert vr.relation_of(v) == vr.REL_EXPERIENCE
        assert vr.is_test_driver(v) is True
        assert vr.is_owner(v) is False
        assert vr.is_family(v) is False

    def test_unknown_role_id_falls_back_to_family(self):
        """未知 roleId → 保守当家人共享（多禁用展示项，不误开权限）。"""
        v = {"vehicleType": "authorized", "vehicleRoleId": "99"}
        assert vr.relation_of(v) == vr.REL_FAMILY_SHARED


class TestRelationOfOwned:
    """owned 类型（App: 'owned' 分支）。"""

    def test_owned_is_owner(self):
        """App: owned + 非接收方 + 普通状态 → Owner。"""
        v = {"vehicleType": "owned", "vehicleRoleId": "11"}
        assert vr.relation_of(v) == vr.REL_OWNER
        assert vr.is_owner(v) is True
        assert vr.is_family(v) is False

    def test_owned_transferred_is_transfer_accepted(self):
        """App: state===Transferred → TransferAccepted。"""
        v = {"vehicleType": "owned", "vehicleState": "Transferred"}
        assert vr.relation_of(v) == vr.REL_TRANSFER_ACCEPTED

    def test_owned_reverse_activating_is_transfer_accepted(self):
        """App: state===ReverseActivating → TransferAccepted。"""
        v = {"vehicleType": "owned", "vehicleState": "ReverseActivating"}
        assert vr.relation_of(v) == vr.REL_TRANSFER_ACCEPTED

    def test_owned_registered_is_none(self):
        """App: state===Registered → None。"""
        v = {"vehicleType": "owned", "vehicleState": "Registered"}
        assert vr.relation_of(v) == vr.REL_NONE

    def test_receiver_is_transferring(self):
        """App: owned + isReceiver → Transferring。"""
        v = {"vehicleType": "owned", "isReceiver": True}
        assert vr.relation_of(v) == vr.REL_TRANSFERRING


class TestRelationOfInviting:
    def test_inviting_is_family_inviting(self):
        """App: 'inviting' → FamilyShareInviting。"""
        v = {"vehicleType": "inviting"}
        assert vr.relation_of(v) == vr.REL_FAMILY_INVITING


class TestRelationOfInvalid:
    @pytest.mark.parametrize("v", [None, {}, {"vehicleType": "bogus"}, "notadict", 42])
    def test_invalid_input_is_none(self, v):
        assert vr.relation_of(v) == vr.REL_NONE


class TestLabels:
    def test_labels_and_names_agree(self):
        """每个 REL_* 都要有 label 与 name，且不重复。"""
        for rel in (vr.REL_NONE, vr.REL_OWNER, vr.REL_TRANSFERRING,
                    vr.REL_TRANSFER_ACCEPTED, vr.REL_FAMILY_INVITING,
                    vr.REL_FAMILY_SHARED, vr.REL_EXPERIENCE):
            assert rel in vr.RELATION_LABELS
            assert rel in vr.RELATION_NAMES
        assert len(set(vr.RELATION_NAMES.values())) == len(vr.RELATION_NAMES)

    def test_label_for_our_account(self):
        v = {"vehicleType": "authorized", "vehicleRoleId": "15"}
        assert vr.relation_label(v) == "家人共享"
        assert vr.relation_name(v) == "family_shared"


class TestHiddenPolicy:
    """展示策略：App 对家人隐藏的项 → 默认禁用（但实体仍存在）。"""

    @pytest.mark.parametrize("key", [
        "location", "charge_here", "remote_photo",
        "parking_photo", "maintain_engine", "maintenance_oil",
    ])
    def test_family_hidden_keys(self, key):
        assert vr.is_hidden_for_relation(key, vr.REL_FAMILY_SHARED) is True

    @pytest.mark.parametrize("key", [
        "battery_level", "charge_status", "tire_fl",
        "door_lock", "window_fl", "ac_on", "seat_fl_heat",
    ])
    def test_family_visible_keys(self, key):
        """★ 关键回归：车控与状态【绝不能】被家人角色隐藏。

        依据：功能对照表 30 项 ✅ 全部是在家人账号下实测通过的。
        """
        assert vr.is_hidden_for_relation(key, vr.REL_FAMILY_SHARED) is False

    def test_ota_hidden_for_test_driver_only(self):
        assert vr.is_hidden_for_relation("ota_state", vr.REL_EXPERIENCE) is True
        assert vr.is_hidden_for_relation("ota_state", vr.REL_OWNER) is False

    def test_owner_sees_everything(self):
        for key in ("location", "maintain_engine", "ota_state", "battery_level"):
            assert vr.is_hidden_for_relation(key, vr.REL_OWNER) is False

    def test_notice_text_differs_by_role(self):
        assert "家人" in vr.hidden_notice(vr.REL_FAMILY_SHARED)
        assert "试驾" in vr.hidden_notice(vr.REL_EXPERIENCE)
        assert vr.hidden_notice(vr.REL_OWNER) == ""

    def test_no_control_key_is_ever_hidden(self):
        """★ 防回归：任何车控 key 都不应进隐藏表。

        实测（2026-09-28）：家人账号能控制车锁/车窗/尾门/空调/座椅/
        方向盘/寻车/拍照/哨兵 —— 全部可用。
        """
        control_prefixes = (
            "door", "window", "trunk", "frunk", "slide",
            "seat_", "wheel_heat", "ac_", "charge_switch",
            "find_car", "flash", "honk", "sentry",
        )
        for rel in (vr.REL_FAMILY_SHARED, vr.REL_EXPERIENCE):
            for key in control_prefixes:
                assert vr.is_hidden_for_relation(key, rel) is False, (
                    f"{key} 是车控能力，不应被角色隐藏（实测家人账号可用）"
                )


class TestCurrentVehicle:
    def test_reads_first_vehicle(self):
        class _Api:
            def get_vehicles(self):
                return [{"vehicleType": "authorized", "vehicleRoleId": "15"}]
        v = vr.current_vehicle(_Api())
        assert vr.is_family(v) is True

    def test_handles_empty_and_error(self):
        class _Empty:
            def get_vehicles(self):
                return []
        assert vr.current_vehicle(_Empty()) is None

        class _Boom:
            def get_vehicles(self):
                raise RuntimeError("network down")
        assert vr.current_vehicle(_Boom()) is None
