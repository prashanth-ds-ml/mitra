"""Tests for layered configuration model in app/config.py."""

import tempfile
import pathlib
import os

from app import config


class TestDeepMerge:
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = config._deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"outer": {"inner": 1, "other": 2}}
        override = {"outer": {"inner": 3}}
        result = config._deep_merge(base, override)
        assert result == {"outer": {"inner": 3, "other": 2}}

    def test_nested_new_key(self):
        base = {"outer": {"inner": 1}}
        override = {"outer": {"new": 2}, "top": 3}
        result = config._deep_merge(base, override)
        assert result == {"outer": {"inner": 1, "new": 2}, "top": 3}


class TestLayeredConfig:
    def test_user_defaults_layer(self, tmp_path, monkeypatch):
        # Create user config
        user_dir = tmp_path / ".config" / "codemitra"
        user_dir.mkdir(parents=True)
        user_file = user_dir / "codemitra.toml"
        user_file.write_text('local_model = "user-model"\ntemperature = 0.5\n')

        monkeypatch.setattr(config, "_USER_CONFIG_FILE", user_file)

        cfg = config.load(str(tmp_path))
        assert cfg["local_model"] == "user-model"
        assert cfg["temperature"] == 0.5

    def test_project_overrides_user(self, tmp_path, monkeypatch):
        # Create user config
        user_dir = tmp_path / ".config" / "codemitra"
        user_dir.mkdir(parents=True)
        user_file = user_dir / "codemitra.toml"
        user_file.write_text('local_model = "user-model"\n')

        monkeypatch.setattr(config, "_USER_CONFIG_FILE", user_file)

        # Create project config
        project_file = tmp_path / "codemitra.toml"
        project_file.write_text('local_model = "project-model"\n')

        cfg = config.load(str(tmp_path))
        assert cfg["local_model"] == "project-model"

    def test_local_overrides_project(self, tmp_path, monkeypatch):
        # Create user config
        user_dir = tmp_path / ".config" / "codemitra"
        user_dir.mkdir(parents=True)
        user_file = user_dir / "codemitra.toml"
        user_file.write_text('local_model = "user-model"\n')

        monkeypatch.setattr(config, "_USER_CONFIG_FILE", user_file)

        # Create project config
        project_file = tmp_path / "codemitra.toml"
        project_file.write_text('local_model = "project-model"\n')

        # Create local override
        local_dir = tmp_path / ".codemitra"
        local_dir.mkdir(parents=True)
        local_file = local_dir / "local.toml"
        local_file.write_text('local_model = "local-model"\n')

        cfg = config.load(str(tmp_path))
        assert cfg["local_model"] == "local-model"

    def test_cli_overrides_all(self, tmp_path, monkeypatch):
        # Create user config
        user_dir = tmp_path / ".config" / "codemitra"
        user_dir.mkdir(parents=True)
        user_file = user_dir / "codemitra.toml"
        user_file.write_text('local_model = "user-model"\n')

        monkeypatch.setattr(config, "_USER_CONFIG_FILE", user_file)

        # Create project config
        project_file = tmp_path / "codemitra.toml"
        project_file.write_text('local_model = "project-model"\n')

        # Create local override
        local_dir = tmp_path / ".codemitra"
        local_dir.mkdir(parents=True)
        local_file = local_dir / "local.toml"
        local_file.write_text('local_model = "local-model"\n')

        # CLI override
        cfg = config.load(str(tmp_path), cli_overrides={"local_model": "cli-model"})
        assert cfg["local_model"] == "cli-model"

    def test_env_var_overrides_all(self, tmp_path, monkeypatch):
        # Create user config
        user_dir = tmp_path / ".config" / "codemitra"
        user_dir.mkdir(parents=True)
        user_file = user_dir / "codemitra.toml"
        user_file.write_text('ollama_api_key = "from-config"\n')

        monkeypatch.setattr(config, "_USER_CONFIG_FILE", user_file)

        monkeypatch.setenv("OLLAMA_API_KEY", "from-env")

        cfg = config.load(str(tmp_path))
        assert cfg["ollama_api_key"] == "from-env"

    def test_dotenv_overrides_config(self, tmp_path, monkeypatch):
        user_dir = tmp_path / ".config" / "codemitra"
        user_dir.mkdir(parents=True)
        user_file = user_dir / "codemitra.toml"
        user_file.write_text('ollama_api_key = "from-config"\n')

        monkeypatch.setattr(config, "_USER_CONFIG_FILE", user_file)

        env_file = tmp_path / ".env"
        env_file.write_text('OLLAMA_API_KEY="from-dotenv"\n')

        cfg = config.load(str(tmp_path))
        assert cfg["ollama_api_key"] == "from-dotenv"

    def test_nested_config_merge(self, tmp_path, monkeypatch):
        """Test that nested dicts are merged, not replaced."""
        user_dir = tmp_path / ".config" / "codemitra"
        user_dir.mkdir(parents=True)
        user_file = user_dir / "codemitra.toml"
        user_file.write_text('custom_section = { key1 = "user", key2 = "user2" }\n')

        monkeypatch.setattr(config, "_USER_CONFIG_FILE", user_file)

        project_file = tmp_path / "codemitra.toml"
        project_file.write_text('custom_section = { key2 = "project", key3 = "project3" }\n')

        cfg = config.load(str(tmp_path))
        assert cfg["custom_section"]["key1"] == "user"
        assert cfg["custom_section"]["key2"] == "project"
        assert cfg["custom_section"]["key3"] == "project3"


class TestSaveUserConfig:
    def test_save_user_config(self, tmp_path, monkeypatch):
        user_file = tmp_path / "codemitra.toml"
        monkeypatch.setattr(config, "_USER_CONFIG_FILE", user_file)
        monkeypatch.setattr(config, "_USER_CONFIG_DIR", user_file.parent)

        cfg = {"local_model": "test-model", "temperature": 0.3}
        ok, msg = config.save_user_config(cfg)
        assert ok
        assert user_file.exists()

        # Verify content
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(user_file, "rb") as f:
            loaded = tomllib.load(f)
        assert loaded["local_model"] == "test-model"
        assert loaded["temperature"] == 0.3


class TestSaveLocalConfig:
    def test_save_local_config(self, tmp_path):
        cfg = {"local_model": "local-test", "session_mode": "auto"}
        ok, msg = config.save_local_config(cfg, str(tmp_path))
        assert ok

        local_file = tmp_path / ".codemitra" / "local.toml"
        assert local_file.exists()

        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(local_file, "rb") as f:
            loaded = tomllib.load(f)
        assert loaded["local_model"] == "local-test"
        assert loaded["session_mode"] == "auto"