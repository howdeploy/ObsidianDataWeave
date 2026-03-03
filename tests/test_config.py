"""Tests for scripts/config.py — shared configuration module."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.config import (
    DEFAULT_STAGING_DIR,
    PROJECT_ROOT,
    REGISTRY_PATH,
    load_config,
)


def test_project_root_exists():
    assert PROJECT_ROOT.exists()
    assert (PROJECT_ROOT / "config.toml").exists()


def test_registry_path_under_project():
    assert REGISTRY_PATH.parent == PROJECT_ROOT
    assert REGISTRY_PATH.name == "processed.json"


def test_default_staging_dir():
    assert DEFAULT_STAGING_DIR == "/tmp/dw/staging"


def test_load_config_returns_dict():
    cfg = load_config()
    assert isinstance(cfg, dict)


def test_load_config_has_vault_section():
    cfg = load_config()
    assert "vault" in cfg
    assert "vault_path" in cfg["vault"]


def test_load_config_has_rclone_section():
    cfg = load_config()
    assert "rclone" in cfg
    assert "staging_dir" in cfg["rclone"]


def test_load_config_soft_fallback(tmp_path):
    """When config.toml is missing and strict=False, returns defaults."""
    with patch("scripts.config.PROJECT_ROOT", tmp_path):
        cfg = load_config(strict=False)
        assert cfg["rclone"]["staging_dir"] == DEFAULT_STAGING_DIR


def test_load_config_strict_exits(tmp_path):
    """When config.toml is missing and strict=True, exits."""
    with patch("scripts.config.PROJECT_ROOT", tmp_path):
        with pytest.raises(SystemExit):
            load_config(strict=True)
