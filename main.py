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


class App(tk.Tk):
	def __init__(self):
		super().__init__()
		
		# Initialize core components
		self.i18n = I18n()
		self.title(self.i18n.t('app_title'))
		self.geometry('800x500')
		
		# Initialize managers
		self.ui_builder = UIBuilder(self, self.i18n)
		self.monitor = ProcessMonitor()
		self.tray_manager = None
		
		# Style
		self.style = ttk.Style(self)
		
		# State variables
		self.theme_key = tk.StringVar(value='light')
		self.proc_freq_key = tk.StringVar(value='1s')
		self.prio_freq_key = tk.StringVar(value='1s')
		self.refresh_interval = 1000
		
		# UI components (populated during UI creation)
		self.proc_listbox = None
		self.priority_widgets = None
		self.search_var = None
		
		# Build UI
		self._build_ui()
		
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
			'on_auto_monitor_toggle': self._on_auto_monitor_toggle,
			'on_search': self.refresh_process_list,
			'on_refresh': self.refresh_process_list,
			'on_process_select': self._on_process_select,
			'on_apply_priority': self.apply_priority_to_selected,
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
		
		# Initial refresh
		self.refresh_process_list()
		self._apply_theme()
	
	def _toggle_settings(self):
		"""Toggle settings panel"""
		self.ui_builder.toggle_settings()
	
	def _on_language_change(self):
		"""Handle language change"""
		locale_display = self.ui_builder.lang_display_var.get()
		new_lang = self.ui_builder.lang_map.get(locale_display, self.i18n.current_lang)
		
		if new_lang != self.i18n.current_lang:
			self.i18n.set_language(new_lang)
			self._refresh_ui_text()
	
	def _refresh_ui_text(self):
		"""Refresh all UI text after language change"""
		self.title(self.i18n.t('app_title'))
		self.ui_builder.update_toolbar_title()
		
		# Recreate UI with new language
		try:
			self.ui_builder.settings_frame.destroy()
		except Exception:
			pass
		
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
			'on_auto_monitor_toggle': self._on_auto_monitor_toggle,
			'on_search': self.refresh_process_list,
			'on_refresh': self.refresh_process_list,
			'on_process_select': self._on_process_select,
			'on_apply_priority': self.apply_priority_to_selected,
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
		
		self.refresh_process_list()
	
	def _apply_theme(self):
		"""Apply theme colors"""
		if self.theme_key.get() == 'dark':
			bg = '#2e2e2e'
			fg = 'white'
		else:
			bg = 'SystemButtonFace'
			fg = 'black'
		
		self.configure(bg=bg)
		self.style.configure('TFrame', background=bg)
		self.style.configure('TLabel', background=bg, foreground=fg)
		self.style.configure('TButton', background=bg)
	
	def _on_theme_select(self):
		"""Handle theme change"""
		disp = self.ui_builder.theme_display_var.get()
		key = self.ui_builder.theme_map.get(disp)
		if key:
			self.theme_key.set(key)
		self._apply_theme()
	
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
	
	def _on_prio_freq_select(self):
		"""Handle priority update frequency change"""
		disp = self.ui_builder.prio_freq_display_var.get()
		key = self.ui_builder.prio_map.get(disp)
		if key:
			self.prio_freq_key.set(key)
	
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
		if self.proc_listbox is None or not self.priority_widgets:
			return
		
		sel = self.proc_listbox.curselection()
		if not sel:
			return
		
		text = self.proc_listbox.get(sel[0])
		pid = int(text.split(' - ', 1)[0])
		
		process = ProcessManager.get_process_by_pid(pid)
		if process:
			self.priority_widgets['selected_label'].config(text=f"{process.pid} - {process.name()}")
		else:
			self.priority_widgets['selected_label'].config(text=self.i18n.t('process_gone'))
	
	# ===== Priority management =====
	
	def apply_priority_to_selected(self):
		"""Apply selected priority to process"""
		if self.proc_listbox is None or not self.priority_widgets:
			messagebox.showinfo(self.i18n.t('msg_info'), self.i18n.t('msg_no_process'))
			return
		
		sel = self.proc_listbox.curselection()
		if not sel:
			messagebox.showinfo(self.i18n.t('msg_info'), self.i18n.t('msg_no_process'))
			return
		
		text = self.proc_listbox.get(sel[0])
		pid = int(text.split(' - ', 1)[0])
		prio_display = self.priority_widgets['priority_var'].get()
		
		# Map display priority to internal name
		priority_map = {
			self.i18n.t('priority_idle'): 'Idle',
			self.i18n.t('priority_below_normal'): 'Below Normal',
			self.i18n.t('priority_normal'): 'Normal',
			self.i18n.t('priority_above_normal'): 'Above Normal',
			self.i18n.t('priority_high'): 'High',
			self.i18n.t('priority_realtime'): 'RealTime',
		}
		prio_name = priority_map.get(prio_display, prio_display)
		
		try:
			PriorityManager.set_priority(pid, prio_name)
			messagebox.showinfo(
				self.i18n.t('msg_success'),
				self.i18n.t('msg_success_priority', pid=pid, priority=prio_display)
			)
		except Exception as e:
			if 'Access' in str(e) or 'permission' in str(e).lower():
				messagebox.showerror(self.i18n.t('msg_error'), self.i18n.t('msg_access_denied'))
			else:
				messagebox.showerror(self.i18n.t('msg_error'), self.i18n.t('msg_process_gone'))
	
	# ===== Startup management =====
	
	def _on_startup_toggle(self):
		"""Handle startup toggle"""
		enable = self.ui_builder.startup_var.get()
		try:
			StartupManager.register_startup(enable)
			messagebox.showinfo(self.i18n.t('msg_info'), self.i18n.t('msg_startup'))
		except Exception as e:
			messagebox.showerror(self.i18n.t('msg_error'), self.i18n.t('msg_startup_error', error=str(e)))
	
	# ===== Auto-monitoring =====
	
	def _on_auto_monitor_toggle(self):
		"""Handle auto-monitor toggle"""
		if self.ui_builder.auto_monitor_var.get():
			self.monitor.start(
				self._get_selected_pid,
				self._get_desired_priority,
				self._get_update_interval
			)
		else:
			self.monitor.stop()
	
	def _get_selected_pid(self):
		"""Get currently selected process PID"""
		if self.proc_listbox is None:
			return None
		
		sel = self.proc_listbox.curselection()
		if not sel:
			return None
		
		text = self.proc_listbox.get(sel[0])
		try:
			return int(text.split(' - ', 1)[0])
		except Exception:
			return None
	
	def _get_desired_priority(self):
		"""Get desired priority setting"""
		if self.priority_widgets is None:
			return 'Normal'
		
		priority_map = {
			self.i18n.t('priority_idle'): 'Idle',
			self.i18n.t('priority_below_normal'): 'Below Normal',
			self.i18n.t('priority_normal'): 'Normal',
			self.i18n.t('priority_above_normal'): 'Above Normal',
			self.i18n.t('priority_high'): 'High',
			self.i18n.t('priority_realtime'): 'RealTime',
		}
		return priority_map.get(self.priority_widgets['priority_var'].get(), 'Normal')
	
	def _get_update_interval(self):
		"""Get priority update interval in seconds"""
		val = self.prio_freq_key.get()
		if val == 'first only':
			return 0
		try:
			return int(val.replace('s', ''))
		except Exception:
			return 1
	
	# ===== Window management =====
	
	def _periodic_refresh(self):
		"""Periodic refresh of process list"""
		if getattr(self, 'refresh_interval', 1000) > 0:
			self.refresh_process_list()
		self.after(max(500, getattr(self, 'refresh_interval', 1000)), self._periodic_refresh)
	
	def _on_close(self):
		"""Handle window close"""
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
