"""Internationalization (i18n) manager for loading translations"""
import json
import locale as locale_module
import os


class I18n:
	"""Simple i18n (internationalization) manager for loading translations"""
	
	def __init__(self, default_lang='en'):
		self.translations = {}
		self.current_lang = default_lang
		self._load_available_languages()
		self._detect_system_language()
	
	def _load_available_languages(self):
		"""Load all available translations from locales folder"""
		locales_dir = os.path.join(os.path.dirname(__file__), '..', 'locales')
		if not os.path.exists(locales_dir):
			return
		
		for filename in os.listdir(locales_dir):
			if filename.endswith('.json'):
				lang_code = filename[:-5]
				filepath = os.path.join(locales_dir, filename)
				try:
					with open(filepath, 'r', encoding='utf-8') as f:
						self.translations[lang_code] = json.load(f)
				except (OSError, ValueError) as e:
					print(f"Failed to load {filename}: {e}")
	
	def _detect_system_language(self):
		"""Detect system language and set current language"""
		try:
			system_lang = locale_module.getlocale()[0]
			if system_lang:
				lang_code = system_lang.split('_')[0].lower()[:2]
				if lang_code in self.translations:
					self.current_lang = lang_code
		except (ValueError, AttributeError):
			# Locale could not be determined; keep the default language.
			pass
	
	def set_language(self, lang_code):
		"""Set the current language"""
		if lang_code in self.translations:
			self.current_lang = lang_code
	
	def get_available_languages(self):
		"""Get list of available languages as (code, locale_name) tuples"""
		languages = []
		for lang_code in sorted(self.translations.keys()):
			trans_dict = self.translations[lang_code]
			locale_name = trans_dict.get('locale', lang_code)
			languages.append((lang_code, locale_name))
		return languages
	
	def t(self, key, **kwargs):
		"""Get translated string with optional formatting"""
		trans_dict = self.translations.get(self.current_lang, {})
		fallback_dict = self.translations.get('en', {})
		
		text = trans_dict.get(key, fallback_dict.get(key, key))
		
		if kwargs:
			try:
				text = text.format(**kwargs)
			except KeyError:
				pass
		
		return text
