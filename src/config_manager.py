"""Configuration management for persistent app settings."""
import copy
import json
import os
from pathlib import Path

class ConfigManager:
	"""Loads and saves configuration near the executable."""

	VALID_THEMES = {'light', 'dark'}
	VALID_PROCESS_REFRESH = {'1s', '5s', '10s', '20s', '30s', 'on change'}
	VALID_PRIORITY_REFRESH = {'1s', '5s', '10s', '20s', '30s', '45s', '60s', 'first only'}
	VALID_LANGUAGES = {'ja', 'en'}

	DEFAULT_CONFIG = {
		'ui': {
			'language': 'ja',
			'theme': 'light',
			'process_refresh': '1s',
			'priority_update': '1s',
			'start_with_windows': False,
			'minimize_to_tray': False,
			'auto_monitor': False,
		},
		'priority_rules': [],
	}

	def __init__(self):
		self.config_path = self._resolve_config_path()

	@staticmethod
	def _resolve_config_path():
		"""Resolve config path next to executable/script."""
		config_dir = Path(os.environ["APPDATA"])/"Process Priority Manager"
		print(config_dir/"config.json")
		return config_dir / "config.json"

	@classmethod
	def _default_config(cls):
		return copy.deepcopy(cls.DEFAULT_CONFIG)

	@staticmethod
	def _strict_bool(value):
		return value if isinstance(value, bool) else False

	def _sanitize_ui(self, ui_loaded):
		"""Sanitize UI config and force defaults for invalid values."""
		default_ui = self._default_config()['ui']
		if not isinstance(ui_loaded, dict):
			return default_ui

		language = str(ui_loaded.get('language', default_ui['language'])).strip().lower()
		theme = str(ui_loaded.get('theme', default_ui['theme'])).strip().lower()
		process_refresh = str(ui_loaded.get('process_refresh', default_ui['process_refresh'])).strip().lower()
		priority_update = str(ui_loaded.get('priority_update', default_ui['priority_update'])).strip().lower()

		if language not in self.VALID_LANGUAGES:
			language = default_ui['language']
		if theme not in self.VALID_THEMES:
			theme = default_ui['theme']
		if process_refresh not in self.VALID_PROCESS_REFRESH:
			process_refresh = default_ui['process_refresh']
		if priority_update not in self.VALID_PRIORITY_REFRESH:
			priority_update = default_ui['priority_update']

		return {
			'language': language,
			'theme': theme,
			'process_refresh': process_refresh,
			'priority_update': priority_update,
			'start_with_windows': self._strict_bool(ui_loaded.get('start_with_windows')),
			'minimize_to_tray': self._strict_bool(ui_loaded.get('minimize_to_tray')),
			'auto_monitor': self._strict_bool(ui_loaded.get('auto_monitor')),
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
			keyword = str(item.get('keyword', '')).strip()
			priority = str(item.get('priority', 'Normal')).strip()
			enabled = item.get('enabled', True)
			if not keyword:
				continue
			if not isinstance(enabled, bool):
				enabled = True
			sanitized.append({
				'keyword': keyword,
				'priority': priority,
				'enabled': enabled,
			})
		return sanitized

	def _sanitize_config(self, loaded):
		"""Normalize full config structure."""
		if not isinstance(loaded, dict):
			return self._default_config()

		return {
			'ui': self._sanitize_ui(loaded.get('ui')),
			'priority_rules': self._sanitize_rules(loaded.get('priority_rules')),
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
			with open(self.config_path, 'r', encoding='utf-8') as f:
				loaded = json.load(f)
		except Exception:
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
			
			with open(self.config_path, 'w', encoding='utf-8') as f:
				json.dump(config, f, ensure_ascii=False, indent=2)
		except Exception:
			return False
		return True
