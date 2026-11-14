"""Configuration management for persistent app settings."""

import copy
import json
import os
from pathlib import Path
from typing import ClassVar


class ConfigManager:
    """Loads and saves configuration near the executable."""

    VALID_THEMES = frozenset({"light", "dark"})
    VALID_PROCESS_REFRESH = frozenset({"1s", "5s", "10s", "20s", "30s", "on change"})
    VALID_PRIORITY_REFRESH = frozenset(
        {"1s", "5s", "10s", "20s", "30s", "45s", "60s", "first only"}
    )
    VALID_LANGUAGES = frozenset({"ja", "en"})
    VALID_PRIORITIES = frozenset(
        {"Idle", "Below Normal", "Normal", "Above Normal", "High", "RealTime"}
    )

    # Plain nested dict: it is deep-copied before use (mappingproxy cannot be).
    DEFAULT_CONFIG: ClassVar[dict] = {
        "ui": {
            "language": "ja",
            "theme": "light",
            "process_refresh": "1s",
            "priority_update": "1s",
            "start_with_windows": False,
            "minimize_to_tray": False,
            "auto_monitor": False,
            "check_updates": True,
        },
        "priority_rules": [],
    }

    def __init__(self):
        self.config_path = self._resolve_config_path()

    @staticmethod
    def _resolve_config_path():
        """Resolve config path under %APPDATA%."""
        appdata = os.environ.get("APPDATA") or str(Path.home())
        return Path(appdata) / "Process Priority Manager" / "config.json"

    @staticmethod
    def _installer_check_updates():
        """Read the update-check choice made in the MSI installer (None if absent)."""
        try:
            import winreg
        except ImportError:
            return None
        key_path = r"Software\Hoshimikan6490\Process Priority Manager"
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                key = winreg.OpenKey(hive, key_path)
            except OSError:
                continue
            with key:
                try:
                    value, _ = winreg.QueryValueEx(key, "CheckUpdates")
                except OSError:
                    # Installed by the MSI with the "update check" feature deselected.
                    return False
            return str(value).strip() == "1"
        return None

    @classmethod
    def _default_config(cls):
        config = copy.deepcopy(cls.DEFAULT_CONFIG)
        installer_choice = cls._installer_check_updates()
        if installer_choice is not None:
            config["ui"]["check_updates"] = installer_choice
        return config

    @staticmethod
    def _strict_bool(value):
        return value if isinstance(value, bool) else False

    def _sanitize_ui(self, ui_loaded):
        """Sanitize UI config and force defaults for invalid values."""
        default_ui = self._default_config()["ui"]
        if not isinstance(ui_loaded, dict):
            return default_ui

        def pick(key, valid):
            value = str(ui_loaded.get(key, default_ui[key])).strip().lower()
            return value if value in valid else default_ui[key]

        language = pick("language", self.VALID_LANGUAGES)
        theme = pick("theme", self.VALID_THEMES)
        process_refresh = pick("process_refresh", self.VALID_PROCESS_REFRESH)
        priority_update = pick("priority_update", self.VALID_PRIORITY_REFRESH)

        return {
            "language": language,
            "theme": theme,
            "process_refresh": process_refresh,
            "priority_update": priority_update,
            "start_with_windows": self._strict_bool(
                ui_loaded.get("start_with_windows")
            ),
            "minimize_to_tray": self._strict_bool(ui_loaded.get("minimize_to_tray")),
            "auto_monitor": self._strict_bool(ui_loaded.get("auto_monitor")),
            "check_updates": ui_loaded["check_updates"]
            if isinstance(ui_loaded.get("check_updates"), bool)
            else default_ui["check_updates"],
        }

    @staticmethod
    def _sanitize_rules(rules_loaded):
        """Keep only valid rule objects."""
        if not isinstance(rules_loaded, list):
            return []

        sanitized = []
        for item in rules_loaded:
            if not isinstance(item, dict):
                continue
            keyword = str(item.get("keyword", "")).strip()
            priority = str(item.get("priority", "Normal")).strip()
            enabled = item.get("enabled", True)
            if not keyword:
                continue
            if priority not in ConfigManager.VALID_PRIORITIES:
                priority = "Normal"
            if not isinstance(enabled, bool):
                enabled = True
            sanitized.append(
                {
                    "keyword": keyword,
                    "priority": priority,
                    "enabled": enabled,
                }
            )
        return sanitized

    def _sanitize_config(self, loaded):
        """Normalize full config structure."""
        if not isinstance(loaded, dict):
            return self._default_config()

        return {
            "ui": self._sanitize_ui(loaded.get("ui")),
            "priority_rules": self._sanitize_rules(loaded.get("priority_rules")),
        }

    def load(self):
        """Load configuration from disk.

        Returns:
                Configuration dictionary with defaults applied.
        """
        config = self._default_config()
        if not os.path.exists(self.config_path):
            self.save(config)
            return config

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, ValueError):
            self.save(config)
            return config

        sanitized = self._sanitize_config(loaded)
        if sanitized != loaded:
            self.save(sanitized)

        return sanitized

    def save(self, config):
        """Save configuration to disk."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except (OSError, TypeError, ValueError):
            return False
        return True
