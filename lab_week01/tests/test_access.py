from __future__ import annotations

import pytest

from lab_week01.realtime.access import create_access_plan


def test_local_access_is_loopback_only() -> None:
    plan = create_access_plan("local", port=7860)

    assert plan.server_name == "127.0.0.1"
    assert not plan.share
    assert plan.auth is None


def test_lan_access_binds_all_interfaces_and_lists_urls() -> None:
    plan = create_access_plan(
        "lan", port=9000, lan_addresses=("192.168.1.20", "10.0.0.4")
    )

    assert plan.server_name == "0.0.0.0"
    assert not plan.share
    assert "LAN URL: http://192.168.1.20:9000" in plan.notices
    assert any("may block Webcam" in notice for notice in plan.notices)


def test_mobile_access_uses_https_share_and_authentication() -> None:
    plan = create_access_plan(
        "mobile", port=7860, username="student", password="safe-pass-123"
    )

    assert plan.share
    assert plan.pwa
    assert plan.server_name == "127.0.0.1"
    assert plan.auth == ("student", "safe-pass-123")


def test_mobile_access_generates_a_strong_temporary_password() -> None:
    plan = create_access_plan("mobile", port=7860)

    assert plan.auth is not None
    assert len(plan.auth[1]) >= 12


@pytest.mark.parametrize("bad_port", [0, 65536])
def test_invalid_port_is_rejected(bad_port: int) -> None:
    with pytest.raises(ValueError):
        create_access_plan("local", port=bad_port)


def test_short_mobile_password_is_rejected() -> None:
    with pytest.raises(ValueError):
        create_access_plan("mobile", port=7860, password="short")
