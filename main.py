"""Process Priority Manager - Main application"""
import tkinter as tk
from tkinter import ttk, messagebox

from src.i18n import I18n
from src.process_manager import ProcessManager
from src.priority_manager import PriorityManager
from src.system_startup import StartupManager
from src.tray_manager import TrayManager
from src.monitor import ProcessMonitor
from src.ui_builder import UIBuilder
from src.config_manager import ConfigManager


class App(tk.Tk):
	def __init__(self):
		super().__init__()

		# Load persisted configuration first
		self.config_manager = ConfigManager()
		self.config = self.config_manager.load()

		# Initialize core components
		self.i18n = I18n()
		config_lang = self.config.get('ui', {}).get('language')
		if isinstance(config_lang, str):
			self.i18n.set_language(config_lang)

		self.title(self.i18n.t('app_title'))
		self.geometry('800x500')

		# Initialize managers
		self.ui_builder = UIBuilder(self, self.i18n)
		self.monitor = ProcessMonitor()
		self.tray_manager = None

		# Style
		self.style = ttk.Style(self)

		# State variables
		ui_config = self.config.get('ui', {})
		self.theme_key = tk.StringVar(value=str(ui_config.get('theme', 'light')))
		self.proc_freq_key = tk.StringVar(value=str(ui_config.get('process_refresh', '1s')))
		self.prio_freq_key = tk.StringVar(value=str(ui_config.get('priority_update', '1s')))
		self.refresh_interval = 1000
		self.priority_rules = self._normalize_priority_rules(self.config.get('priority_rules', []))
		
		# UI components (populated during UI creation)
		self.proc_listbox = None
		self.priority_widgets = None
		self.search_var = None

		# Build UI
		self._build_ui()
		self._update_refresh_interval()

		# Start monitoring if enabled in config
		if self.ui_builder.auto_monitor_var.get():
			self.monitor.start(self._get_active_priority_rules, self._get_update_interval)
		
		# Setup window close handler
		self.protocol('WM_DELETE_WINDOW', self._on_close)
		self.after(self.refresh_interval, self._periodic_refresh)
	
	def _build_ui(self):
		"""Build the entire UI"""
		callbacks = {
			'on_language_change': self._on_language_change,
			'on_theme_change': self._on_theme_select,
			'on_proc_freq_change': self._on_proc_freq_select,
			'on_prio_freq_change': self._on_prio_freq_select,
			'on_startup_toggle': self._on_startup_toggle,
			'on_tray_toggle': self._on_tray_toggle,
			'on_auto_monitor_toggle': self._on_auto_monitor_toggle,
			'on_search': self.refresh_process_list,
			'on_refresh': self.refresh_process_list,
			'on_process_select': self._on_process_select,
			'on_priority_keyword_change': self._on_priority_keyword_change,
			'on_priority_refresh': self.refresh_priority_process_list,
			'on_priority_process_select': self._on_priority_process_select,
			'on_apply_priority_rule': self.apply_priority_rule,
			'on_delete_priority_rules': self.delete_checked_priority_rules,
		}
		
		# Toolbar
		self.ui_builder.create_toolbar(self._toggle_settings)
		
		# Settings panel
		self.ui_builder.create_settings_panel(callbacks)
		
		# Notebook (tabs)
		notebook = self.ui_builder.create_notebook()
		
		# Process tab
		tab_processes = ttk.Frame(notebook)
		notebook.add(tab_processes, text=self.i18n.t('tab_processes'))
		self.proc_listbox = self.ui_builder.create_process_tab(tab_processes, callbacks)
		self.search_var = self.ui_builder.search_var
		
		# Priority tab
		tab_priority = ttk.Frame(notebook)
		notebook.add(tab_priority, text=self.i18n.t('tab_priority'))
		self.priority_widgets = self.ui_builder.create_priority_tab(tab_priority, callbacks)

		self._sync_ui_controls_from_state()
		self.refresh_priority_process_list()
		self.refresh_priority_rules_table()

		# Initial refresh
		self.refresh_process_list()
		self._apply_theme()
	
	def _get_theme_palette(self):
		"""Return theme colors for the current theme."""
		if self.theme_key.get() == 'dark':
			return {
				'bg': '#2e2e2e',
				'fg': '#f5f5f5',
				'dark_text': '#1d1d1d',
				'panel_bg': '#3a3a3a',
				'entry_bg': '#404040',
				'selection': '#4a90d9',
			}
		return {
			'bg': 'SystemButtonFace',
			'fg': 'black',
			'dark_text': 'black',
			'panel_bg': '#f0f0f0',
			'entry_bg': 'white',
			'selection': '#4a90d9',
		}
	
	def _toggle_settings(self):
		"""Toggle settings panel"""
		self.ui_builder.toggle_settings()
	
	def _on_language_change(self):
		"""Handle language change"""
		locale_display = self.ui_builder.lang_display_var.get()
		new_lang = self.ui_builder.lang_map.get(locale_display, self.i18n.current_lang)
		
		if new_lang != self.i18n.current_lang:
			self.i18n.set_language(new_lang)
			self._save_config()
			self._refresh_ui_text()
	
	def _refresh_ui_text(self):
		"""Refresh all UI text after language change"""
		self.title(self.i18n.t('app_title'))
		self.ui_builder.update_toolbar_title()
		if self.ui_builder.settings_window is not None:
			try:
				self.ui_builder.settings_window.title(self.i18n.t('app_title'))
			except Exception:
				pass
		
		# Recreate UI with new language
		try:
			for widget in self.winfo_children():
				if isinstance(widget, ttk.Notebook):
					widget.destroy()
		except Exception:
			pass
		
		callbacks = {
			'on_language_change': self._on_language_change,
			'on_theme_change': self._on_theme_select,
			'on_proc_freq_change': self._on_proc_freq_select,
			'on_prio_freq_change': self._on_prio_freq_select,
			'on_startup_toggle': self._on_startup_toggle,
			'on_tray_toggle': self._on_tray_toggle,
			'on_auto_monitor_toggle': self._on_auto_monitor_toggle,
			'on_search': self.refresh_process_list,
			'on_refresh': self.refresh_process_list,
			'on_process_select': self._on_process_select,
			'on_priority_keyword_change': self._on_priority_keyword_change,
			'on_priority_refresh': self.refresh_priority_process_list,
			'on_priority_process_select': self._on_priority_process_select,
			'on_apply_priority_rule': self.apply_priority_rule,
			'on_delete_priority_rules': self.delete_checked_priority_rules,
		}
		
		self.ui_builder.create_settings_panel(callbacks)

		notebook = self.ui_builder.create_notebook()
		
		tab_processes = ttk.Frame(notebook)
		notebook.add(tab_processes, text=self.i18n.t('tab_processes'))
		self.proc_listbox = self.ui_builder.create_process_tab(tab_processes, callbacks)
		self.search_var = self.ui_builder.search_var
		
		tab_priority = ttk.Frame(notebook)
		notebook.add(tab_priority, text=self.i18n.t('tab_priority'))
		self.priority_widgets = self.ui_builder.create_priority_tab(tab_priority, callbacks)

		self._sync_ui_controls_from_state()
		self.refresh_priority_process_list()
		self.refresh_priority_rules_table()

		self.refresh_process_list()
		self._apply_theme()
	
	def _apply_theme(self):
		"""Apply theme colors to all relevant widgets."""
		palette = self._get_theme_palette()
		bg = palette['bg']
		fg = palette['fg']
		dark_text = palette['dark_text']
		panel_bg = palette['panel_bg']
		entry_bg = palette['entry_bg']
		selection = palette['selection']
		
		self.configure(bg=bg)
		self.style.configure('TFrame', background=bg)
		self.style.configure('TLabel', background=bg, foreground=fg)
		self.style.configure('TButton', background=bg, foreground=dark_text)
		self.style.configure('TEntry', fieldbackground=entry_bg, foreground=fg)
		self.style.configure('TCombobox', fieldbackground=entry_bg, foreground=dark_text)
		self.style.configure('TCheckbutton', background=bg, foreground=fg)
		self.style.configure('TLabelframe', background=bg)
		self.style.configure('TLabelframe.Label', background=bg, foreground=fg)
		self.style.configure('TNotebook', background=bg)
		self.style.configure('TNotebook.Tab', background=panel_bg, foreground=dark_text)
		self.style.map('TNotebook.Tab',
			background=[('selected', panel_bg), ('active', panel_bg)],
			foreground=[('selected', dark_text), ('active', dark_text)]
		)
		
		if self.proc_listbox is not None:
			self.proc_listbox.configure(
				bg='black',
				fg='white',
				selectbackground=selection,
				selectforeground='white',
				highlightbackground='white',
				highlightcolor='white',
				bd=1,
				relief='solid',
				highlightthickness=1,
			)

		if self.priority_widgets and self.priority_widgets.get('process_listbox') is not None:
			self.priority_widgets['process_listbox'].configure(
				bg='black',
				fg='white',
				selectbackground=selection,
				selectforeground='white',
				highlightbackground='white',
				highlightcolor='white',
				bd=1,
				relief='solid',
				highlightthickness=1,
			)
		
		for child in self.winfo_children():
			if not isinstance(child, ttk.Widget):
				try:
					child.configure(background=bg, foreground=fg)
				except Exception:
					pass
	
	def _on_theme_select(self):
		"""Handle theme change"""
		disp = self.ui_builder.theme_display_var.get()
		key = self.ui_builder.theme_map.get(disp)
		if key:
			self.theme_key.set(key)
		self._apply_theme()
		self._save_config()
	
	def _update_refresh_interval(self):
		"""Update process list refresh interval"""
		val = self.proc_freq_key.get()
		mapping = {'1s': 1000, '5s': 5000, '10s': 10000, '20s': 20000, '30s': 30000, 'on change': 0}
		self.refresh_interval = mapping.get(val, 1000)
	
	def _on_proc_freq_select(self):
		"""Handle process refresh frequency change"""
		disp = self.ui_builder.proc_freq_display_var.get()
		key = self.ui_builder.proc_map.get(disp)
		if key:
			self.proc_freq_key.set(key)
		self._update_refresh_interval()
		self._save_config()
	
	def _on_prio_freq_select(self):
		"""Handle priority update frequency change"""
		disp = self.ui_builder.prio_freq_display_var.get()
		key = self.ui_builder.prio_map.get(disp)
		if key:
			self.prio_freq_key.set(key)
		self._save_config()
	
	# ===== Process list management =====
	
	def refresh_process_list(self):
		"""Refresh process list with current search keyword"""
		if self.proc_listbox is None:
			return
		
		keyword = self.search_var.get() if self.search_var else ''
		self.proc_listbox.delete(0, tk.END)
		
		procs = ProcessManager.get_processes_by_keyword(keyword)
		for display, pid, name in procs:
			self.proc_listbox.insert(tk.END, display)
	
	def _on_process_select(self):
		"""Handle process selection"""
		return
	
	# ===== Priority management =====

	def _priority_display_to_internal(self, display_name):
		priority_map = {
			self.i18n.t('priority_idle'): 'Idle',
			self.i18n.t('priority_below_normal'): 'Below Normal',
			self.i18n.t('priority_normal'): 'Normal',
			self.i18n.t('priority_above_normal'): 'Above Normal',
			self.i18n.t('priority_high'): 'High',
			self.i18n.t('priority_realtime'): 'RealTime',
		}
		return priority_map.get(display_name, 'Normal')

	def _priority_internal_to_display(self, priority_name):
		reverse_map = {
			'Idle': self.i18n.t('priority_idle'),
			'Below Normal': self.i18n.t('priority_below_normal'),
			'Normal': self.i18n.t('priority_normal'),
			'Above Normal': self.i18n.t('priority_above_normal'),
			'High': self.i18n.t('priority_high'),
			'RealTime': self.i18n.t('priority_realtime'),
		}
		return reverse_map.get(priority_name, self.i18n.t('priority_normal'))

	def _on_priority_keyword_change(self):
		"""Update priority-process list when keyword changes."""
		self.refresh_priority_process_list()

	def refresh_priority_process_list(self):
		"""Refresh process candidates in priority tab."""
		if not self.priority_widgets:
			return

		listbox = self.priority_widgets.get('process_listbox')
		keyword_var = self.priority_widgets.get('keyword_var')
		if listbox is None or keyword_var is None:
			return

		keyword = keyword_var.get().strip()
		listbox.delete(0, tk.END)
		if not keyword:
			return

		for display, _pid, _name in ProcessManager.get_processes_by_keyword(keyword):
			listbox.insert(tk.END, display)

	def _on_priority_process_select(self):
		"""Use selected process name as keyword candidate."""
		if not self.priority_widgets:
			return

		listbox = self.priority_widgets.get('process_listbox')
		keyword_var = self.priority_widgets.get('keyword_var')
		if listbox is None or keyword_var is None:
			return

		sel = listbox.curselection()
		if not sel:
			return

		text = listbox.get(sel[0])
		parts = text.split(' - ', 1)
		if len(parts) == 2:
			keyword_var.set(parts[1])

	def refresh_priority_rules_table(self):
		"""Render active priority rules in table-like rows."""
		if not self.priority_widgets:
			return

		rows_frame = self.priority_widgets.get('rules_rows_frame')
		if rows_frame is None:
			return

		for child in rows_frame.winfo_children():
			child.destroy()

		check_vars = []
		for idx, rule in enumerate(self.priority_rules):
			if not rule.get('enabled', True):
				continue

			selected_var = tk.BooleanVar(value=False)
			ttk.Checkbutton(rows_frame, variable=selected_var).grid(row=idx, column=0, sticky='w', padx=(0, 8), pady=2)
			ttk.Label(rows_frame, text=rule['keyword'], width=30).grid(row=idx, column=1, sticky='w', padx=(0, 8), pady=2)
			ttk.Label(rows_frame, text=self._priority_internal_to_display(rule['priority']), width=16).grid(row=idx, column=2, sticky='w', pady=2)
			check_vars.append((selected_var, rule['keyword'], rule['priority']))

		self.priority_widgets['rule_check_vars'] = check_vars

	def _find_rule_index(self, keyword):
		"""Find priority rule index by keyword (case-insensitive)."""
		for idx, rule in enumerate(self.priority_rules):
			if rule.get('keyword', '').lower() == keyword.lower():
				return idx
		return -1

	def apply_priority_rule(self):
		"""Save keyword/priority rule and apply immediately to matching processes."""
		if not self.priority_widgets:
			return

		keyword = self.priority_widgets['keyword_var'].get().strip()
		if not keyword:
			messagebox.showinfo(self.i18n.t('msg_info'), self.i18n.t('msg_enter_keyword'))
			return

		prio_display = self.priority_widgets['priority_var'].get()
		prio_name = self._priority_display_to_internal(prio_display)

		rule = {
			'keyword': keyword,
			'priority': prio_name,
			'enabled': True,
		}
		existing_idx = self._find_rule_index(keyword)
		if existing_idx >= 0:
			self.priority_rules[existing_idx] = rule
		else:
			self.priority_rules.append(rule)

		applied_count = 0
		for _display, pid, _name in ProcessManager.get_processes_by_keyword(keyword):
			try:
				PriorityManager.set_priority(pid, prio_name)
				applied_count += 1
			except Exception:
				continue

		self._save_config()
		self.refresh_priority_rules_table()
		messagebox.showinfo(
			self.i18n.t('msg_success'),
			self.i18n.t(
				'msg_rule_saved',
				keyword=keyword,
				priority=prio_display,
				count=applied_count,
			)
		)

	def delete_checked_priority_rules(self):
		"""Delete checked priority rules from active settings."""
		if not self.priority_widgets:
			return

		check_vars = self.priority_widgets.get('rule_check_vars', [])
		selected_keywords = []
		for selected_var, keyword, _priority in check_vars:
			if selected_var.get():
				selected_keywords.append(keyword.lower())

		if not selected_keywords:
			messagebox.showinfo(self.i18n.t('msg_info'), self.i18n.t('msg_no_checked_setting'))
			return

		self.priority_rules = [
			rule for rule in self.priority_rules
			if rule.get('keyword', '').lower() not in selected_keywords
		]

		self._save_config()
		self.refresh_priority_rules_table()
		messagebox.showinfo(self.i18n.t('msg_info'), self.i18n.t('msg_deleted_checked_setting'))
	
	# ===== Startup management =====
	
	def _on_startup_toggle(self):
		"""Handle startup toggle"""
		enable = self.ui_builder.startup_var.get()
		try:
			StartupManager.register_startup(enable)
			self._save_config()
			messagebox.showinfo(self.i18n.t('msg_info'), self.i18n.t('msg_startup'))
		except Exception as e:
			messagebox.showerror(self.i18n.t('msg_error'), self.i18n.t('msg_startup_error', error=str(e)))

	def _on_tray_toggle(self):
		"""Handle tray setting toggle."""
		self._save_config()
	
	# ===== Auto-monitoring =====
	
	def _on_auto_monitor_toggle(self):
		"""Handle auto-monitor toggle"""
		if self.ui_builder.auto_monitor_var.get():
			self.monitor.start(self._get_active_priority_rules, self._get_update_interval)
		else:
			self.monitor.stop()
		self._save_config()

	def _get_active_priority_rules(self):
		"""Return currently active rules for monitor loop."""
		return [rule.copy() for rule in self.priority_rules if rule.get('enabled', True)]
	
	def _get_update_interval(self):
		"""Get priority update interval in seconds"""
		val = self.prio_freq_key.get()
		if val == 'first only':
			return 0
		try:
			return int(val.replace('s', ''))
		except Exception:
			return 1

	# ===== Config management =====

	def _normalize_priority_rules(self, rules):
		"""Normalize loaded rule list to internal schema."""
		normalized = []
		allowed = {'Idle', 'Below Normal', 'Normal', 'Above Normal', 'High', 'RealTime'}
		if not isinstance(rules, list):
			return normalized

		for item in rules:
			if not isinstance(item, dict):
				continue
			keyword = str(item.get('keyword', '')).strip()
			priority = str(item.get('priority', 'Normal')).strip()
			enabled = bool(item.get('enabled', True))
			if not keyword:
				continue
			if priority not in allowed:
				priority = 'Normal'
			normalized.append({'keyword': keyword, 'priority': priority, 'enabled': enabled})
		return normalized

	def _sync_ui_controls_from_state(self):
		"""Apply current state variables to UI controls."""
		if not self.ui_builder.settings_frame:
			return

		current_locale = self.i18n.translations[self.i18n.current_lang].get('locale', self.i18n.current_lang)
		self.ui_builder.lang_display_var.set(current_locale)

		theme_display = next((d for d, k in self.ui_builder.theme_map.items() if k == self.theme_key.get()), None)
		if theme_display:
			self.ui_builder.theme_display_var.set(theme_display)

		proc_display = next((d for d, k in self.ui_builder.proc_map.items() if k == self.proc_freq_key.get()), None)
		if proc_display:
			self.ui_builder.proc_freq_display_var.set(proc_display)

		prio_display = next((d for d, k in self.ui_builder.prio_map.items() if k == self.prio_freq_key.get()), None)
		if prio_display:
			self.ui_builder.prio_freq_display_var.set(prio_display)

		ui_config = self.config.get('ui', {})
		self.ui_builder.startup_var.set(bool(ui_config.get('start_with_windows', False)))
		self.ui_builder.tray_var.set(bool(ui_config.get('minimize_to_tray', False)))
		self.ui_builder.auto_monitor_var.set(bool(ui_config.get('auto_monitor', False)))

	def _build_config_payload(self):
		"""Build config object from current app state."""
		return {
			'ui': {
				'language': self.i18n.current_lang,
				'theme': self.theme_key.get(),
				'process_refresh': self.proc_freq_key.get(),
				'priority_update': self.prio_freq_key.get(),
				'start_with_windows': bool(self.ui_builder.startup_var.get()) if self.ui_builder.settings_frame else False,
				'minimize_to_tray': bool(self.ui_builder.tray_var.get()) if self.ui_builder.settings_frame else False,
				'auto_monitor': bool(self.ui_builder.auto_monitor_var.get()) if self.ui_builder.settings_frame else False,
			},
			'priority_rules': self.priority_rules,
		}

	def _save_config(self):
		"""Persist current state to config.json."""
		self.config = self._build_config_payload()
		self.config_manager.save(self.config)
	
	# ===== Window management =====
	
	def _periodic_refresh(self):
		"""Periodic refresh of process list"""
		if getattr(self, 'refresh_interval', 1000) > 0:
			self.refresh_process_list()
		self.after(max(500, getattr(self, 'refresh_interval', 1000)), self._periodic_refresh)
	
	def _on_close(self):
		"""Handle window close"""
		self._save_config()
		if self.ui_builder.tray_var.get():
			self.withdraw()
			if self.tray_manager is None:
				self.tray_manager = TrayManager(
					self.i18n.t('app_title'),
					{
						'show': self._show_from_tray,
						'exit': self._quit_from_tray,
						'show_label': self.i18n.t('tray_show'),
						'exit_label': self.i18n.t('tray_exit'),
					}
				)
				if self.tray_manager.is_available():
					self.tray_manager.create_icon()
					self.tray_manager.start()
		else:
			self.quit()
	
	def _show_from_tray(self):
		"""Show window from tray"""
		if self.tray_manager:
			self.tray_manager.stop()
		self.deiconify()
	
	def _quit_from_tray(self):
		"""Quit from tray"""
		if self.tray_manager:
			self.tray_manager.stop()
		self.quit()


if __name__ == '__main__':
	app = App()
	app.mainloop()
