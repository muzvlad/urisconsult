"""Тесты токена доступа к API: приоритет источников (спека 061)."""
import sys
import types

from src import config as config_module
from src.config import _builtin_api_token, _get_api_token, _read_env_value


class TestTokenPriority:
    """env var > .env рядом с EXE > токен, вшитый в EXE > пусто."""

    def test_env_var_wins(self, monkeypatch):
        monkeypatch.setenv("API_TOKEN", "env-token")
        monkeypatch.setattr(config_module, "_read_env_value", lambda key: "file-token")
        monkeypatch.setattr(config_module, "_builtin_api_token", lambda: "builtin-token")
        assert _get_api_token() == "env-token"

    def test_env_file_wins_over_builtin(self, monkeypatch):
        monkeypatch.delenv("API_TOKEN", raising=False)
        monkeypatch.setattr(config_module, "_read_env_value", lambda key: "file-token")
        monkeypatch.setattr(config_module, "_builtin_api_token", lambda: "builtin-token")
        assert _get_api_token() == "file-token"

    def test_builtin_used_as_last_resort(self, monkeypatch):
        monkeypatch.delenv("API_TOKEN", raising=False)
        monkeypatch.setattr(config_module, "_read_env_value", lambda key: "")
        monkeypatch.setattr(config_module, "_builtin_api_token", lambda: "builtin-token")
        assert _get_api_token() == "builtin-token"

    def test_no_token_anywhere(self, monkeypatch):
        monkeypatch.delenv("API_TOKEN", raising=False)
        monkeypatch.setattr(config_module, "_read_env_value", lambda key: "")
        monkeypatch.setattr(config_module, "_builtin_api_token", lambda: "")
        assert _get_api_token() == ""


class TestBuiltinToken:
    def test_reads_generated_module(self, monkeypatch):
        module = types.ModuleType("src._api_secret")
        module.API_TOKEN = "secret-token"
        monkeypatch.setitem(sys.modules, "src._api_secret", module)
        assert _builtin_api_token() == "secret-token"

    def test_missing_module_returns_empty(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "src._api_secret", None)
        assert _builtin_api_token() == ""


class TestEnvFileReading:
    def test_quotes_are_stripped(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text('API_TOKEN="quoted-token"\n', encoding="utf-8")
        monkeypatch.setattr(config_module, "_get_base_path", lambda: tmp_path)
        assert _read_env_value("API_TOKEN") == "quoted-token"

    def test_bom_is_ignored(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_bytes('\ufeffAPI_TOKEN=bom-token\n'.encode("utf-8"))
        monkeypatch.setattr(config_module, "_get_base_path", lambda: tmp_path)
        assert _read_env_value("API_TOKEN") == "bom-token"

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config_module, "_get_base_path", lambda: tmp_path)
        assert _read_env_value("API_TOKEN") == ""
