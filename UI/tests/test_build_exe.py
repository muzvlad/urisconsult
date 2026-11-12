"""Тесты вшивки API-токена в собранный EXE (спека 061)."""
import ast
import os

import build_exe


class TestReadBuildApiToken:
    def test_from_environment(self, monkeypatch):
        monkeypatch.delenv("API_TOKEN", raising=False)
        monkeypatch.setenv("UI_BUILD_API_TOKEN", "env-token")
        token, source = build_exe.read_build_api_token(env_path="")
        assert token == "env-token"
        assert "UI_BUILD_API_TOKEN" in source

    def test_api_token_env_is_second_source(self, monkeypatch):
        monkeypatch.delenv("UI_BUILD_API_TOKEN", raising=False)
        monkeypatch.setenv("API_TOKEN", "plain-env-token")
        token, source = build_exe.read_build_api_token(env_path="")
        assert token == "plain-env-token"
        assert "API_TOKEN" in source

    def test_from_bot_env_file(self, monkeypatch, tmp_path):
        monkeypatch.delenv("UI_BUILD_API_TOKEN", raising=False)
        monkeypatch.delenv("API_TOKEN", raising=False)
        env_path = tmp_path / ".env"
        env_path.write_text("BOT_TOKEN=123:abc\nAPI_TOKEN=file-token\n", encoding="utf-8")
        token, source = build_exe.read_build_api_token(env_path=str(env_path))
        assert token == "file-token"
        assert source.endswith(".env")

    def test_quotes_are_stripped(self, monkeypatch, tmp_path):
        monkeypatch.delenv("UI_BUILD_API_TOKEN", raising=False)
        monkeypatch.delenv("API_TOKEN", raising=False)
        env_path = tmp_path / ".env"
        env_path.write_text('API_TOKEN="file-token"\n', encoding="utf-8")
        token, _ = build_exe.read_build_api_token(env_path=str(env_path))
        assert token == "file-token"

    def test_token_missing(self, monkeypatch, tmp_path):
        monkeypatch.delenv("UI_BUILD_API_TOKEN", raising=False)
        monkeypatch.delenv("API_TOKEN", raising=False)
        token, source = build_exe.read_build_api_token(
            env_path=str(tmp_path / "missing.env"))
        assert token == ""
        assert source == ""


class TestApiSecretFile:
    def test_write_and_remove(self, tmp_path):
        target = str(tmp_path / "_api_secret.py")
        build_exe.write_api_secret("secret-token", target=target)
        with open(target, encoding="utf-8") as f:
            content = f.read()
        assert "secret-token" in content
        build_exe.remove_api_secret(target=target)
        assert not os.path.exists(target)

    def test_remove_missing_file_is_safe(self, tmp_path):
        build_exe.remove_api_secret(target=str(tmp_path / "_api_secret.py"))

    def test_generated_module_is_valid_python(self, tmp_path):
        target = str(tmp_path / "_api_secret.py")
        build_exe.write_api_secret('to"ken\\x', target=target)
        with open(target, encoding="utf-8") as f:
            module = ast.parse(f.read())
        value = ast.literal_eval(module.body[0].value)
        assert value == 'to"ken\\x'
