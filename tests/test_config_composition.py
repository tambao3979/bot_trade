"""Tests for config composition and environment overlay."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestConfigComposition:
    def test_base_config_is_valid_json(self):
        """Base config must be valid JSON."""
        config_path = Path("user_data/config/config.base.json")
        assert config_path.exists(), "config.base.json not found"

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        assert isinstance(config, dict)
        assert "exchange" in config
        assert "name" in config["exchange"]

    def test_backtest_config_is_valid_json(self):
        """Backtest config must be valid JSON."""
        config_path = Path("user_data/config/config.backtest.json")
        assert config_path.exists(), "config.backtest.json not found"

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        assert isinstance(config, dict)

    def test_dryrun_config_requires_base(self):
        """Dryrun-only config should fail or require base composition."""
        dryrun_path = Path("user_data/config/config.dryrun.json")

        if not dryrun_path.exists():
            pytest.skip("config.dryrun.json not present")

        with open(dryrun_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # If dryrun config exists alone without exchange, it's incomplete
        if "exchange" not in config:
            pytest.skip("dryrun config is overlay-only (requires base)")

    def test_freqtrade_list_strategies_works(self):
        """Verify freqtrade can load strategies with base config."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "freqtrade",
                "list-strategies",
                "-c",
                "user_data/config/config.base.json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should exit 0 and list strategies
        assert result.returncode == 0, f"list-strategies failed: {result.stderr}"
        assert "TrendPullback" in result.stdout or "TrendPullback" in result.stderr

    def test_freqtrade_show_config_base_backtest(self):
        """Verify config composition works for backtest."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "freqtrade",
                "show-config",
                "-c",
                "user_data/config/config.base.json",
                "-c",
                "user_data/config/config.backtest.json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, f"show-config failed: {result.stderr}"

        # Parse output to verify composition
        output = result.stdout + result.stderr
        assert "dry_run" in output.lower() or "runmode" in output.lower()


class TestEnvironmentOverlay:
    def test_env_example_exists(self):
        """Ensure .env.example exists and is documented."""
        env_example = Path(".env.example")
        assert env_example.exists(), ".env.example not found"

        content = env_example.read_text(encoding="utf-8")

        # Should have FREQTRADE__ prefix examples
        assert "FREQTRADE__" in content
        # Should have double underscore for nesting
        assert "__" in content
        # Should not contain real secrets
        assert "change-me" in content.lower() or "example" in content.lower()

    def test_env_file_is_gitignored(self):
        """Verify .env files are in .gitignore."""
        gitignore = Path(".gitignore")
        assert gitignore.exists()

        content = gitignore.read_text(encoding="utf-8")
        assert ".env" in content
        # Should allow .env.example
        assert "!.env.example" in content


class TestDatabaseAndLogPaths:
    def test_database_files_are_gitignored(self):
        """Database files should be ignored."""
        gitignore = Path(".gitignore")
        content = gitignore.read_text(encoding="utf-8")

        assert "*.sqlite" in content
        assert "*.db" in content

    def test_log_files_are_gitignored(self):
        """Log files should be ignored."""
        gitignore = Path(".gitignore")
        content = gitignore.read_text(encoding="utf-8")

        assert "*.log" in content or "user_data/logs/" in content

    def test_risk_state_file_is_gitignored(self):
        """Risk state file should be ignored (contains runtime PnL)."""
        gitignore = Path(".gitignore")
        content = gitignore.read_text(encoding="utf-8")

        assert ".risk_state.json" in content


class TestDependencies:
    def test_requirements_txt_exists(self):
        """Requirements file should exist."""
        req_file = Path("requirements.txt")
        assert req_file.exists(), "requirements.txt not found"

        content = req_file.read_text(encoding="utf-8")
        assert "freqtrade" in content.lower()

    def test_python_version_documented(self):
        """Python version should be documented somewhere."""
        # Check README or similar
        readme = Path("README.md")
        if readme.exists():
            content = readme.read_text(encoding="utf-8")
            assert "python" in content.lower() or "3.1" in content
