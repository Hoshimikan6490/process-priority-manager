"""UI builder module for creating application interface"""
import tkinter as tk
from tkinter import ttk


class UIBuilder:
	"""Builds and manages UI components"""
	
	def __init__(self, app, i18n):
		"""Initialize UI builder
		
		Args:
			app: Main application window
			i18n: I18n instance for translations
		"""
		self.app = app
		self.i18n = i18n
		self.settings_visible = False
		self.settings_window = None
		self.settings_frame = None

	def _ensure_settings_window(self):
		"""Create settings window if it does not exist yet."""
		if self.settings_window is not None:
			try:
				if self.settings_window.winfo_exists():
					return
			except Exception:
				pass

		self.settings_window = tk.Toplevel(self.app)
		self.settings_window.title(self.i18n.t('app_title'))
		self.settings_window.resizable(False, False)
		self.settings_window.transient(self.app)
		self.settings_window.protocol('WM_DELETE_WINDOW', self._hide_settings_window)
		self.settings_window.withdraw()

	def _hide_settings_window(self):
		"""Hide settings window."""
		if self.settings_window is None:
			return
		try:
			self.settings_window.withdraw()
		except Exception:
			pass
		self.settings_visible = False

	def _position_settings_window(self):
		"""Place settings window centered over the main window."""
		if self.settings_window is None:
			return

		try:
			self.app.update_idletasks()
			self.settings_window.update_idletasks()

			app_x = self.app.winfo_x()
			app_y = self.app.winfo_y()
			app_w = self.app.winfo_width()
			app_h = self.app.winfo_height()

			win_w = self.settings_window.winfo_reqwidth()
			win_h = self.settings_window.winfo_reqheight()

			x = app_x + max(0, (app_w - win_w) // 2)
			y = app_y + max(0, (app_h - win_h) // 2)
			self.settings_window.geometry(f'+{x}+{y}')
		except Exception:
			pass
	
	def create_toolbar(self, toggle_settings_callback):
		"""Create toolbar with title and settings button
		
		Args:
			toggle_settings_callback: Callback for settings button
		"""
		toolbar = ttk.Frame(self.app)
		toolbar.pack(fill='x')
		
		gear = ttk.Button(toolbar, text='⚙', width=3, command=toggle_settings_callback)
		gear.pack(side='right', padx=6, pady=6)
		
		self.toolbar_title = ttk.Label(
			toolbar,
			text=self.i18n.t('app_title'),
			font=('Segoe UI', 12, 'bold')
		)
		self.toolbar_title.pack(side='left', padx=8)
	
	def update_toolbar_title(self):
		"""Update toolbar title after language change"""
		if hasattr(self, 'toolbar_title'):
			try:
				self.toolbar_title.configure(text=self.i18n.t('app_title'))
			except Exception:
				pass
	
	def create_settings_panel(self, callbacks):
		"""Create settings panel
		
		Args:
			callbacks: Dictionary with callback functions for settings changes
		"""
		self._ensure_settings_window()

		if self.settings_frame is not None:
			try:
				self.settings_frame.destroy()
			except Exception:
				pass

		self.settings_frame = ttk.Frame(self.settings_window, relief='ridge', padding=8)
		self.settings_frame.pack(fill='both', expand=True, padx=8, pady=8)
		
		# Language selector
		lang_label = ttk.Label(self.settings_frame, text=self.i18n.t('language'))
		lang_label.grid(row=0, column=0, sticky='w')
		
		self.lang_map = {}
		lang_display_names = []
		for lang_code, locale_name in self.i18n.get_available_languages():
			self.lang_map[locale_name] = lang_code
			lang_display_names.append(locale_name)
		
		self.lang_display_var = tk.StringVar()
		current_locale = self.i18n.translations[self.i18n.current_lang].get('locale', self.i18n.current_lang)
		
		lang_combo = ttk.Combobox(
			self.settings_frame,
			textvariable=self.lang_display_var,
			values=lang_display_names,
			state='readonly',
			width=12
		)
		lang_combo.set(current_locale)
		lang_combo.grid(row=0, column=1, sticky='w')
		lang_combo.bind('<<ComboboxSelected>>', lambda e: callbacks.get('on_language_change', lambda: None)())
		
		# Theme selector
		theme_label = ttk.Label(self.settings_frame, text=self.i18n.t('theme_label'))
		theme_label.grid(row=1, column=0, sticky='w')
		
		theme_options = [('light', 'light_theme'), ('dark', 'dark_theme')]
		self.theme_map = {self.i18n.t(k2): k1 for k1, k2 in theme_options}
		theme_display_values = [self.i18n.t(k2) for k1, k2 in theme_options]
		
		self.theme_display_var = tk.StringVar()
		self.theme_display_var.set(self.i18n.t('light_theme'))
		
		theme_combo = ttk.Combobox(
			self.settings_frame,
			textvariable=self.theme_display_var,
			values=theme_display_values,
			state='readonly',
			width=12
		)
		theme_combo.grid(row=1, column=1, sticky='w')
		theme_combo.bind('<<ComboboxSelected>>', lambda e: callbacks.get('on_theme_change', lambda: None)())
		
		# Process refresh frequency
		ttk.Label(self.settings_frame, text=self.i18n.t('process_refresh_label')).grid(row=2, column=0, sticky='w')
		proc_options = [('1s', 'freq_1s'), ('5s', 'freq_5s'), ('10s', 'freq_10s'),
		                 ('20s', 'freq_20s'), ('30s', 'freq_30s'), ('on change', 'freq_on_change')]
		self.proc_map = {self.i18n.t(k2): k1 for k1, k2 in proc_options}
		proc_display_values = [self.i18n.t(k2) for k1, k2 in proc_options]
		
		self.proc_freq_display_var = tk.StringVar()
		self.proc_freq_display_var.set(proc_display_values[0])
		
		freq_combo = ttk.Combobox(
			self.settings_frame,
			textvariable=self.proc_freq_display_var,
			values=proc_display_values,
			state='readonly',
			width=12
		)
		freq_combo.grid(row=2, column=1, sticky='w')
		freq_combo.bind('<<ComboboxSelected>>', lambda e: callbacks.get('on_proc_freq_change', lambda: None)())
		
		# Priority update frequency
		ttk.Label(self.settings_frame, text=self.i18n.t('priority_update_label')).grid(row=3, column=0, sticky='w')
		prio_options = [('1s', 'freq_1s'), ('5s', 'freq_5s'), ('10s', 'freq_10s'),
		                 ('20s', 'freq_20s'), ('30s', 'freq_30s'), ('45s', 'freq_45s'),
		                 ('60s', 'freq_60s'), ('first only', 'freq_first_only')]
		self.prio_map = {self.i18n.t(k2): k1 for k1, k2 in prio_options}
		prio_display_values = [self.i18n.t(k2) for k1, k2 in prio_options]
		
		self.prio_freq_display_var = tk.StringVar()
		self.prio_freq_display_var.set(prio_display_values[0])
		
		prio_combo = ttk.Combobox(
			self.settings_frame,
			textvariable=self.prio_freq_display_var,
			values=prio_display_values,
			state='readonly',
			width=12
		)
		prio_combo.grid(row=3, column=1, sticky='w')
		prio_combo.bind('<<ComboboxSelected>>', lambda e: callbacks.get('on_prio_freq_change', lambda: None)())
		
		# Checkbuttons
		self.startup_var = tk.BooleanVar(value=False)
		self.tray_var = tk.BooleanVar(value=False)
		self.auto_monitor_var = tk.BooleanVar(value=False)
		
		ttk.Checkbutton(
			self.settings_frame,
			text=self.i18n.t('startup_checkbox'),
			variable=self.startup_var,
			command=callbacks.get('on_startup_toggle', lambda: None)
		).grid(row=4, column=0, columnspan=2, sticky='w')
		
		ttk.Checkbutton(
			self.settings_frame,
			text=self.i18n.t('tray_checkbox'),
			variable=self.tray_var,
			command=callbacks.get('on_tray_toggle', lambda: None)
		).grid(row=5, column=0, columnspan=2, sticky='w')
		
		ttk.Checkbutton(
			self.settings_frame,
			text=self.i18n.t('auto_monitor_checkbox'),
			variable=self.auto_monitor_var,
			command=callbacks.get('on_auto_monitor_toggle', lambda: None)
		).grid(row=6, column=0, columnspan=2, sticky='w')
		
		for child in self.settings_frame.winfo_children():
			child.grid_configure(padx=4, pady=4)
	
	def toggle_settings(self):
		"""Toggle settings panel visibility"""
		self._ensure_settings_window()

		if self.settings_visible:
			self._hide_settings_window()
		else:
			self._position_settings_window()
			self.settings_window.deiconify()
			self.settings_window.lift()
			self.settings_window.focus_force()
			self.settings_visible = True
	
	def create_notebook(self):
		"""Create notebook (tabbed interface)
		
		Returns:
			Notebook widget
		"""
		notebook = ttk.Notebook(self.app)
		notebook.pack(fill='both', expand=True, padx=8, pady=4)
		return notebook
	
	def create_process_tab(self, parent, callbacks):
		"""Create process tab
		
		Args:
			parent: Parent widget
			callbacks: Dictionary with callback functions
		
		Returns:
			Process listbox widget
		"""
		top = ttk.Frame(parent)
		top.pack(fill='x', pady=6)
		
		ttk.Label(top, text=self.i18n.t('search_label')).pack(side='left')
		
		self.search_var = tk.StringVar()
		search_entry = ttk.Entry(top, textvariable=self.search_var)
		search_entry.pack(side='left', fill='x', expand=True, padx=6)
		search_entry.bind('<KeyRelease>', lambda e: callbacks.get('on_search', lambda: None)())
		
		refresh_btn = ttk.Button(
			top,
			text=self.i18n.t('refresh_button'),
			command=callbacks.get('on_refresh', lambda: None)
		)
		refresh_btn.pack(side='right')
		
		proc_listbox = tk.Listbox(parent)
		proc_listbox.pack(fill='both', expand=True)
		proc_listbox.bind('<<ListboxSelect>>', lambda e: callbacks.get('on_process_select', lambda: None)())
		
		return proc_listbox
	
	def create_priority_tab(self, parent, callbacks):
		"""Create priority tab
		
		Args:
			parent: Parent widget
			callbacks: Dictionary with callback functions
		
		Returns:
			Dictionary with priority widgets
		"""
		frame = ttk.Frame(parent, padding=8)
		frame.pack(fill='both', expand=True)

		# Add setting section
		add_frame = ttk.LabelFrame(frame, text=self.i18n.t('priority_add_setting_section'), padding=8)
		add_frame.pack(fill='x', pady=(0, 10))

		ttk.Label(add_frame, text=self.i18n.t('priority_process_name_label')).grid(row=0, column=0, sticky='w')
		keyword_var = tk.StringVar()
		keyword_entry = ttk.Entry(add_frame, textvariable=keyword_var)
		keyword_entry.grid(row=0, column=1, sticky='ew')
		keyword_entry.bind('<KeyRelease>', lambda e: callbacks.get('on_priority_keyword_change', lambda: None)())

		ttk.Label(add_frame, text=self.i18n.t('priority_process_list_label')).grid(row=1, column=0, sticky='nw')
		process_listbox = tk.Listbox(add_frame, height=6)
		process_listbox.grid(row=1, column=1, sticky='ew')
		process_listbox.bind('<<ListboxSelect>>', lambda e: callbacks.get('on_priority_process_select', lambda: None)())

		ttk.Label(add_frame, text=self.i18n.t('priority_label')).grid(row=2, column=0, sticky='w')

		priority_var = tk.StringVar(value='Normal')
		priorities = [
			self.i18n.t('priority_idle'),
			self.i18n.t('priority_below_normal'),
			self.i18n.t('priority_normal'),
			self.i18n.t('priority_above_normal'),
			self.i18n.t('priority_high'),
			self.i18n.t('priority_realtime')
		]

		priority_combo = ttk.Combobox(add_frame, values=priorities, textvariable=priority_var, state='readonly')
		priority_combo.grid(row=2, column=1, sticky='w')
		priority_combo.set(self.i18n.t('priority_normal'))

		apply_btn = ttk.Button(
			add_frame,
			text=self.i18n.t('apply_priority_button'),
			command=callbacks.get('on_apply_priority_rule', lambda: None)
		)
		apply_btn.grid(row=3, column=0, columnspan=2, pady=(8, 2), sticky='w')

		add_frame.columnconfigure(1, weight=1)

		# Active settings section
		active_frame = ttk.LabelFrame(frame, text=self.i18n.t('priority_active_settings_section'), padding=8)
		active_frame.pack(fill='both', expand=True)

		headers = ttk.Frame(active_frame)
		headers.pack(fill='x')
		ttk.Label(headers, text=self.i18n.t('priority_column_select'), width=8).grid(row=0, column=0, sticky='w')
		ttk.Label(headers, text=self.i18n.t('priority_column_keyword'), width=30).grid(row=0, column=1, sticky='w')
		ttk.Label(headers, text=self.i18n.t('priority_column_priority'), width=16).grid(row=0, column=2, sticky='w')

		rules_rows_frame = ttk.Frame(active_frame)
		rules_rows_frame.pack(fill='both', expand=True, pady=(6, 8))

		delete_btn = ttk.Button(
			active_frame,
			text=self.i18n.t('delete_checked_settings_button'),
			command=callbacks.get('on_delete_priority_rules', lambda: None)
		)
		delete_btn.pack(anchor='w')

		for child in add_frame.winfo_children():
			child.grid_configure(padx=6, pady=4)

		return {
			'keyword_var': keyword_var,
			'keyword_entry': keyword_entry,
			'process_listbox': process_listbox,
			'priority_var': priority_var,
			'priority_combo': priority_combo,
			'rules_rows_frame': rules_rows_frame,
			'rule_check_vars': [],
			'delete_button': delete_btn,
		}
