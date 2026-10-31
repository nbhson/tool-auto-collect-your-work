"""Tests cho config.py — parse env vars và giá trị mặc định."""

import importlib
import os

import pytest

import config as config_module


@pytest.fixture
def clean_env(monkeypatch):
    """Xoá mọi env var liên quan để test giá trị mặc định deterministic."""
    keys = [
        "DEBUG",
        "LOG_LEVEL",
        "HOST",
        "PORT",
        "DATABASE_URL",
        "JIRA_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "JIRA_PROJECT",
        "JIRA_POLL_INTERVAL_MINUTES",
        "BITBUCKET_USERNAME",
        "BITBUCKET_APP_PASSWORD",
        "BITBUCKET_WORKSPACE",
        "BITBUCKET_POLL_INTERVAL_MINUTES",
        "GITHUB_TOKEN",
        "GITHUB_BASE_URL",
        "GITHUB_POLL_INTERVAL_MINUTES",
        "POLLER_MAX_RETRIES",
        "POLLER_INITIAL_DELAY",
        "GIT_HOOK_LOG",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def _reload_config():
    """Reload module config để class attributes được đánh giá lại từ env."""
    return importlib.reload(config_module)


class TestConfigDefaults:
    """Khi env var không được set — dùng giá trị mặc định."""

    def test_app_defaults(self, clean_env):
        cfg_mod = _reload_config()
        cfg = cfg_mod.config
        assert cfg.APP_NAME == "Work Log Tracker"
        assert cfg.DEBUG is True
        assert cfg.LOG_LEVEL == "INFO"

    def test_server_defaults(self, clean_env):
        cfg_mod = _reload_config()
        cfg = cfg_mod.config
        assert cfg.HOST == "127.0.0.1"
        assert cfg.PORT == 8765
        assert isinstance(cfg.PORT, int)

    def test_database_default_is_sqlite(self, clean_env):
        cfg_mod = _reload_config()
        assert cfg_mod.config.DATABASE_URL == "sqlite:///./worklog.db"

    def test_integration_credentials_default_empty(self, clean_env):
        cfg_mod = _reload_config()
        cfg = cfg_mod.config
        assert cfg.JIRA_URL == ""
        assert cfg.JIRA_API_TOKEN == ""
        assert cfg.BITBUCKET_USERNAME == ""
        assert cfg.BITBUCKET_APP_PASSWORD == ""
        assert cfg.GITHUB_TOKEN == ""

    def test_poller_defaults(self, clean_env):
        cfg_mod = _reload_config()
        cfg = cfg_mod.config
        assert cfg.JIRA_POLL_INTERVAL == 10
        assert cfg.BITBUCKET_POLL_INTERVAL == 10
        assert cfg.GITHUB_POLL_INTERVAL == 10
        assert cfg.POLLER_MAX_RETRIES == 3
        assert cfg.POLLER_INITIAL_DELAY == 1.0
        assert isinstance(cfg.POLLER_INITIAL_DELAY, float)


class TestConfigFromEnv:
    """Env var được set — Config phải đọc đúng kiểu."""

    def test_debug_false(self, clean_env):
        clean_env.setenv("DEBUG", "false")
        cfg_mod = _reload_config()
        assert cfg_mod.config.DEBUG is False

    def test_debug_case_insensitive(self, clean_env):
        clean_env.setenv("DEBUG", "False")
        cfg_mod = _reload_config()
        assert cfg_mod.config.DEBUG is False

    def test_port_int_conversion(self, clean_env):
        clean_env.setenv("PORT", "9999")
        cfg_mod = _reload_config()
        assert cfg_mod.config.PORT == 9999

    def test_poll_interval_int_conversion(self, clean_env):
        clean_env.setenv("JIRA_POLL_INTERVAL_MINUTES", "42")
        cfg_mod = _reload_config()
        assert cfg_mod.config.JIRA_POLL_INTERVAL == 42

    def test_custom_host_and_db(self, clean_env):
        clean_env.setenv("HOST", "0.0.0.0")
        clean_env.setenv("DATABASE_URL", "sqlite:////tmp/custom.db")
        cfg_mod = _reload_config()
        assert cfg_mod.config.HOST == "0.0.0.0"
        assert cfg_mod.config.DATABASE_URL == "sqlite:////tmp/custom.db"

    def test_git_hook_log_env_override(self, clean_env, tmp_path):
        expected = str(tmp_path / "hooks.jsonl")
        clean_env.setenv("GIT_HOOK_LOG", expected)
        actual = _reload_config().config.GIT_HOOK_LOG
        assert actual == expected

    def test_git_hook_log_default_points_home(self, clean_env):
        actual = _reload_config().config.GIT_HOOK_LOG
        expected = str(os.path.expanduser("~/.worklog_git_hooks.jsonl"))
        assert actual == expected


@pytest.fixture(autouse=True)
def restore_config():
    """Reload config sau mỗi test để trả về trạng thái ban đầu cho test khác."""
    yield
    importlib.reload(config_module)
