"""Tests verifying OWNd.connection proxy module behavior, attribute forwarding, and reload."""
from __future__ import annotations

import importlib
from types import ModuleType
from unittest.mock import MagicMock, patch
import pytest

import OWNd.connection as conn
from OWNd.connection import _FORWARD_TARGETS, _ConnectionModule


def test_connection_proxy_dynamic_submodules() -> None:
    """Verify _get_submodules dynamically resolves loaded connection submodules."""
    assert isinstance(conn, _ConnectionModule)
    submodules = conn._get_submodules()
    assert len(submodules) >= 5
    mod_names = [m.__name__.split(".")[-1] for m in submodules]
    for expected in ("auth", "command_session", "event_session", "gateway", "session"):
        assert expected in mod_names


def test_connection_proxy_getattr_from_submodule() -> None:
    """Verify __getattr__ dynamically retrieves attributes from submodules."""
    import OWNd.connection.session as sess_mod

    sess_mod._test_dynamic_probe_value = "probe_found"
    try:
        assert getattr(conn, "_test_dynamic_probe_value") == "probe_found"
    finally:
        del sess_mod._test_dynamic_probe_value


def test_connection_proxy_getattr_nonexistent() -> None:
    """Verify __getattr__ raises AttributeError for non-existent attributes."""
    with pytest.raises(AttributeError, match="has no attribute 'nonexistent_test_attr_xyz'"):
        _ = conn.nonexistent_test_attr_xyz


def test_connection_proxy_dir() -> None:
    """Verify __dir__ lists attributes from proxy and underlying submodules."""
    dir_list = dir(conn)
    assert "OWNSession" in dir_list
    assert "calculate_open_password" in dir_list
    assert "find_gateways" in dir_list


def test_connection_proxy_setattr_forwarding() -> None:
    """Verify setting patched attributes propagates to all submodules possessing them."""
    import OWNd.connection.gateway as gw_mod

    orig = gw_mod.find_gateways
    dummy_finder = MagicMock(return_value=["mocked"])
    try:
        conn.find_gateways = dummy_finder
        assert gw_mod.find_gateways is dummy_finder
        assert conn.find_gateways is dummy_finder
    finally:
        conn.find_gateways = orig
        assert gw_mod.find_gateways is orig


def test_connection_proxy_setattr_and_delattr_dunder() -> None:
    """Verify dunder attributes are set and deleted on proxy without submodule forwarding."""
    conn.__test_dunder_proxy__ = "dunder_val"
    assert conn.__test_dunder_proxy__ == "dunder_val"
    del conn.__test_dunder_proxy__
    assert not hasattr(conn, "__test_dunder_proxy__")


def test_connection_proxy_delattr_submodule() -> None:
    """Verify deleting an attribute removes it from proxy and submodules."""
    import OWNd.connection.gateway as gw_mod

    gw_mod._transient_submodule_attr = "sub_val"
    conn._transient_submodule_attr = "sub_val"
    assert hasattr(gw_mod, "_transient_submodule_attr")

    del conn._transient_submodule_attr
    assert not hasattr(conn, "_transient_submodule_attr")
    assert not hasattr(gw_mod, "_transient_submodule_attr")


def test_connection_proxy_forward_targets_missing_fails_loudly() -> None:
    """Verify that if a required forward target is missing from the submodule, it fails loudly."""
    _FORWARD_TARGETS["test_missing_forward_target"] = ("session",)
    try:
        with pytest.raises(
            AttributeError,
            match="Patched attribute 'test_missing_forward_target' missing from expected target submodule 'session'",
        ):
            conn.test_missing_forward_target = "should_fail"
    finally:
        _FORWARD_TARGETS.pop("test_missing_forward_target", None)


def test_connection_proxy_all_attribute_missing_fails_loudly() -> None:
    """Verify that setting an attribute declared in __all__ that is missing from all submodules fails loudly."""
    all_list = list(conn.__all__)
    all_list.append("bogus_all_symbol_missing")
    with patch.object(conn, "__all__", all_list):
        with pytest.raises(
            AttributeError,
            match="Patched attribute 'bogus_all_symbol_missing' in __all__ is missing from all connection submodules",
        ):
            conn.bogus_all_symbol_missing = "fail"


def test_connection_proxy_reload() -> None:
    """Verify that importlib.reload reloads cleanly, preserves _ConnectionModule, and restores state."""
    reloaded = importlib.reload(conn)
    assert isinstance(reloaded, reloaded._ConnectionModule)
    assert reloaded.OWNSession is not None
    assert reloaded.find_gateways is not None

