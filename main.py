"""Process Priority Manager - Main application"""

import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from types import MappingProxyType

import psutil

try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None

from src import update_checker
from src.config_manager import ConfigManager
from src.i18n import I18n
from src.monitor import ProcessMonitor
from src.priority_manager import PriorityManager
from src.process_manager import ProcessManager
from src.resources import load_logo
from src.system_startup import StartupManager
from src.tray_manager import TrayManager
from src.ui_builder import UIBuilder
from src.widgets import ToggleSwitch


class App(tk.Tk):
    PROC_REFRESH_MS = MappingProxyType(
        {
            "1s": 1000,
            "5s": 5000,
            "10s": 10000,
            "20s": 20000,
            "30s": 30000,
            "on change": 0,
        }
    )

    def __init__(self):
        super().__init__()

        # Load persisted configuration first
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()

        # Initialize core components
        self.i18n = I18n()
        config_lang = self.config.get("ui", {}).get("language")
        if isinstance(config_lang, str):
            self.i18n.set_language(config_lang)

        self.title(self.i18n.t("app_title"))
        self.geometry("800x500")
        self._set_window_icon()

        # Initialize managers
        self.ui_builder = UIBuilder(self, self.i18n, self.config_manager.config_path)
        self.monitor = ProcessMonitor()
        self.tray_manager = None  # created by _sync_tray()

        # Style
        self.style = ttk.Style(self)

        # State variables
        ui_config = self.config.get("ui", {})
        self.theme_key = tk.StringVar(value=str(ui_config.get("theme", "light")))
        self.proc_freq_key = tk.StringVar(
            value=str(ui_config.get("process_refresh", "1s"))
        )
        self.prio_freq_key = tk.StringVar(
            value=str(ui_config.get("priority_update", "1s"))
        )
        self.refresh_interval = 1000
        self.priority_rules = self.config.get("priority_rules", [])

        # UI components (populated during UI creation)
        self.proc_listbox = None
        self.priority_widgets = None
        self.search_var = None

        # Build UI
        self._build_ui()
        self._update_refresh_interval()

        # Priorities are always monitored; individual rules are toggled on/off.
        self._start_monitor()

        # System tray (the icon lives in the tray from startup when enabled)
        self._tray_events = queue.Queue()
        self._sync_tray()
        self.after(200, self._poll_tray_events)

        # Setup window close handler
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(self.refresh_interval, self._periodic_refresh)

        # Periodic update check (GitHub Releases)
        self._update_results = queue.Queue()
        self._install_results = queue.Queue()
        self._notified_version = None
        self._downloading = False
        self.after(3000, self._schedule_update_check)
        self.after(1000, self._poll_update_result)

    def _set_window_icon(self):
        """Replace the default Tk feather icon with the app logo."""
        image = load_logo(64)
        if image is None or ImageTk is None:
            return
        self._icon_image = ImageTk.PhotoImage(image)  # keep a reference
        self.iconphoto(True, self._icon_image)

    def _build_callbacks(self):
        """Return the callback table used by the UI builder."""
        return {
            "on_language_change": self._on_language_change,
            "on_theme_change": self._on_theme_select,
            "on_proc_freq_change": self._on_proc_freq_select,
            "on_prio_freq_change": self._on_prio_freq_select,
            "on_startup_toggle": self._on_startup_toggle,
            "on_tray_toggle": self._on_tray_toggle,
            "on_check_updates_toggle": self._on_check_updates_toggle,
            "on_check_updates_now": self._on_check_updates_now,
            "on_search": self.refresh_process_list,
            "on_refresh": self.refresh_process_list,
            "on_priority_keyword_change": self.refresh_priority_process_list,
            "on_priority_refresh": self.refresh_priority_process_list,
            "on_priority_process_select": self._on_priority_process_select,
            "on_apply_priority_rule": self.apply_priority_rule,
            "on_enable_priority_rules": lambda: self.set_checked_rules_enabled(True),
            "on_disable_priority_rules": lambda: self.set_checked_rules_enabled(False),
            "on_delete_priority_rules": self.delete_checked_priority_rules,
        }

    def _build_ui(self):
        """Build the entire UI"""
        self.ui_builder.create_toolbar(self.ui_builder.toggle_settings)
        self._build_content()

    def _build_content(self):
        """Build settings panel and tabs (rebuilt on language change)."""
        callbacks = self._build_callbacks()
        self.ui_builder.create_settings_panel(callbacks)

        notebook = self.ui_builder.create_notebook()

        tab_processes = ttk.Frame(notebook)
        notebook.add(tab_processes, text=self.i18n.t("tab_processes"))
        self.proc_listbox = self.ui_builder.create_process_tab(tab_processes, callbacks)
        self.search_var = self.ui_builder.search_var

        tab_priority = ttk.Frame(notebook)
        notebook.add(tab_priority, text=self.i18n.t("tab_priority"))
        self.priority_widgets = self.ui_builder.create_priority_tab(
            tab_priority, callbacks
        )

        self._sync_ui_controls_from_state()
        self.refresh_priority_process_list()
        self.refresh_priority_rules_table()
        self.refresh_process_list()
        self._apply_theme()

    def _get_theme_palette(self):
        """Return theme colors for the current theme."""
        if self.theme_key.get() == "dark":
            return {
                "bg": "#2e2e2e",
                "fg": "#f5f5f5",
                "dark_text": "#1d1d1d",
                "panel_bg": "#3a3a3a",
                "entry_bg": "#404040",
                "list_bg": "black",
                "list_fg": "white",
                "list_border": "white",
                "selection": "#4a90d9",
            }
        return {
            "bg": "SystemButtonFace",
            "fg": "black",
            "dark_text": "black",
            "panel_bg": "#f0f0f0",
            "entry_bg": "white",
            "list_bg": "white",
            "list_fg": "black",
            "list_border": "#a0a0a0",
            "selection": "#4a90d9",
        }

    def _on_language_change(self):
        """Handle language change"""
        locale_display = self.ui_builder.lang_display_var.get()
        new_lang = self.ui_builder.lang_map.get(locale_display, self.i18n.current_lang)

        if new_lang != self.i18n.current_lang:
            self.i18n.set_language(new_lang)
            self._save_config()
            self._refresh_ui_text()
            self._sync_tray(restart=True)

    def _refresh_ui_text(self):
        """Refresh all UI text after language change"""
        self.title(self.i18n.t("app_title"))
        if self.ui_builder.settings_window is not None:
            try:
                self.ui_builder.settings_window.title(self.i18n.t("app_title"))
            except tk.TclError:
                # Settings window was already destroyed; nothing to retitle.
                pass

        for widget in self.winfo_children():
            if isinstance(widget, ttk.Notebook):
                widget.destroy()
        self._build_content()

    def _apply_theme(self):
        """Apply theme colors to all relevant widgets."""
        palette = self._get_theme_palette()
        bg = palette["bg"]
        fg = palette["fg"]
        dark_text = palette["dark_text"]
        panel_bg = palette["panel_bg"]
        entry_bg = palette["entry_bg"]
        selection = palette["selection"]

        self.configure(bg=bg)
        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabel", background=bg, foreground=fg)
        self.style.configure("TButton", background=bg, foreground=dark_text)
        self.style.configure("TEntry", fieldbackground=entry_bg, foreground=fg)
        self.style.configure(
            "TCombobox", fieldbackground=entry_bg, foreground=dark_text
        )
        self.style.configure("TCheckbutton", background=bg, foreground=fg)
        self.style.configure("TLabelframe", background=bg)
        self.style.configure("TLabelframe.Label", background=bg, foreground=fg)
        self.style.configure("TNotebook", background=bg)
        self.style.configure(
            "TNotebook.Tab",
            background=panel_bg,
            foreground=dark_text,
            padding=(20, 8),
            font=("Segoe UI", 11),
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", panel_bg), ("active", panel_bg)],
            foreground=[("selected", dark_text), ("active", dark_text)],
        )

        listboxes = [
            self.proc_listbox,
            (self.priority_widgets or {}).get("process_listbox"),
        ]
        for listbox in listboxes:
            if listbox is not None:
                listbox.configure(
                    bg=palette["list_bg"],
                    fg=palette["list_fg"],
                    selectbackground=selection,
                    selectforeground="white",
                    highlightbackground=palette["list_border"],
                    highlightcolor=palette["list_border"],
                    bd=1,
                    relief="solid",
                    highlightthickness=1,
                )

        for child in self.winfo_children():
            if not isinstance(child, ttk.Widget):
                try:
                    child.configure(background=bg, foreground=fg)
                except tk.TclError:
                    # This widget has no background/foreground option.
                    pass

    def _on_theme_select(self):
        """Handle theme change"""
        disp = self.ui_builder.theme_display_var.get()
        key = self.ui_builder.theme_map.get(disp)
        if key:
            self.theme_key.set(key)
        self._apply_theme()
        self.refresh_priority_rules_table()  # switch backgrounds follow the theme
        self._save_config()

    def _update_refresh_interval(self):
        """Update process list refresh interval"""
        self.refresh_interval = self.PROC_REFRESH_MS.get(self.proc_freq_key.get(), 1000)

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
        self._restart_monitor()  # "first only" ends the loop; a new interval re-arms it

    # ===== Process list management =====

    def refresh_process_list(self):
        """Refresh process list with current search keyword"""
        if self.proc_listbox is None:
            return

        keyword = self.search_var.get() if self.search_var else ""
        self.proc_listbox.delete(0, tk.END)

        for display, _pid, _name in ProcessManager.get_processes_by_keyword(keyword):
            self.proc_listbox.insert(tk.END, display)

    # ===== Priority management =====

    PRIORITY_I18N_KEYS = MappingProxyType(
        {
            "Idle": "priority_idle",
            "Below Normal": "priority_below_normal",
            "Normal": "priority_normal",
            "Above Normal": "priority_above_normal",
            "High": "priority_high",
            "RealTime": "priority_realtime",
        }
    )

    def _priority_display_to_internal(self, display_name):
        for name, key in self.PRIORITY_I18N_KEYS.items():
            if self.i18n.t(key) == display_name:
                return name
        return "Normal"

    def _priority_internal_to_display(self, priority_name):
        return self.i18n.t(
            self.PRIORITY_I18N_KEYS.get(priority_name, "priority_normal")
        )

    def refresh_priority_process_list(self):
        """Refresh process candidates in priority tab."""
        if not self.priority_widgets:
            return

        listbox = self.priority_widgets.get("process_listbox")
        keyword_var = self.priority_widgets.get("keyword_var")
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

        listbox = self.priority_widgets.get("process_listbox")
        keyword_var = self.priority_widgets.get("keyword_var")
        if listbox is None or keyword_var is None:
            return

        sel = listbox.curselection()
        if not sel:
            return

        text = listbox.get(sel[0])
        parts = text.split(" - ", 1)
        if len(parts) == 2:
            keyword_var.set(parts[1])

    def refresh_priority_rules_table(self):
        """Render registered priority rules (checkbox / on-off switch / keyword / priority)."""
        if not self.priority_widgets:
            return

        rows_frame = self.priority_widgets.get("rules_rows_frame")
        if rows_frame is None:
            return

        # Keep the user's checkmarks across rebuilds (e.g. after a theme change).
        previously_checked = {
            kw.lower()
            for var, kw, _p in self.priority_widgets.get("rule_check_vars", [])
            if var.get()
        }
        for child in rows_frame.winfo_children():
            child.destroy()

        switch_bg = self._get_theme_palette()["bg"]
        check_vars = []
        for idx, rule in enumerate(self.priority_rules):
            selected_var = tk.BooleanVar(
                value=rule["keyword"].lower() in previously_checked
            )
            ttk.Checkbutton(rows_frame, variable=selected_var, width=4).grid(
                row=idx, column=0, sticky="w", padx=(0, 8), pady=2
            )
            ToggleSwitch(
                rows_frame,
                value=rule.get("enabled", True),
                command=lambda value, r=rule: self._set_rule_enabled(r, value),
                bg=switch_bg,
            ).grid(row=idx, column=1, sticky="w", padx=(0, 8), pady=2)
            ttk.Label(rows_frame, text=rule["keyword"], width=28).grid(
                row=idx, column=2, sticky="w", padx=(0, 8), pady=2
            )
            ttk.Label(
                rows_frame,
                text=self._priority_internal_to_display(rule["priority"]),
                width=14,
            ).grid(row=idx, column=3, sticky="w", pady=2)
            check_vars.append((selected_var, rule["keyword"], rule["priority"]))

        self.priority_widgets["rule_check_vars"] = check_vars

    def _set_rule_enabled(self, rule, enabled):
        """Switch a single rule on/off and apply the change to the monitor."""
        rule["enabled"] = bool(enabled)
        self._save_config()
        self._restart_monitor()

    def _checked_keywords(self):
        """Lower-cased keywords of the rows whose checkbox is ticked."""
        if not self.priority_widgets:
            return []
        return [
            kw.lower()
            for var, kw, _p in self.priority_widgets.get("rule_check_vars", [])
            if var.get()
        ]

    def set_checked_rules_enabled(self, enabled):
        """Enable/disable all checked rules at once."""
        selected = self._checked_keywords()
        if not selected:
            messagebox.showinfo(
                self.i18n.t("msg_info"), self.i18n.t("msg_no_checked_setting")
            )
            return

        for rule in self.priority_rules:
            if rule.get("keyword", "").lower() in selected:
                rule["enabled"] = bool(enabled)

        self._save_config()
        self._restart_monitor()
        self.refresh_priority_rules_table()
        message_key = (
            "msg_enabled_checked_setting" if enabled else "msg_disabled_checked_setting"
        )
        messagebox.showinfo(self.i18n.t("msg_info"), self.i18n.t(message_key))

    def _find_rule_index(self, keyword):
        """Find priority rule index by keyword (case-insensitive)."""
        for idx, rule in enumerate(self.priority_rules):
            if rule.get("keyword", "").lower() == keyword.lower():
                return idx
        return -1

    def apply_priority_rule(self):
        """Save keyword/priority rule and apply immediately to matching processes."""
        if not self.priority_widgets:
            return

        keyword = self.priority_widgets["keyword_var"].get().strip()
        if not keyword:
            messagebox.showinfo(
                self.i18n.t("msg_info"), self.i18n.t("msg_enter_keyword")
            )
            return

        prio_display = self.priority_widgets["priority_var"].get()
        prio_name = self._priority_display_to_internal(prio_display)

        rule = {
            "keyword": keyword,
            "priority": prio_name,
            "enabled": True,
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
            except psutil.Error:
                # Process exited or access denied; skip it.
                continue

        self._save_config()
        self.refresh_priority_rules_table()
        messagebox.showinfo(
            self.i18n.t("msg_success"),
            self.i18n.t(
                "msg_rule_saved",
                keyword=keyword,
                priority=prio_display,
                count=applied_count,
            ),
        )

    def delete_checked_priority_rules(self):
        """Delete checked priority rules from active settings."""
        if not self.priority_widgets:
            return

        selected_keywords = self._checked_keywords()

        if not selected_keywords:
            messagebox.showinfo(
                self.i18n.t("msg_info"), self.i18n.t("msg_no_checked_setting")
            )
            return

        self.priority_rules = [
            rule
            for rule in self.priority_rules
            if rule.get("keyword", "").lower() not in selected_keywords
        ]

        self._save_config()
        self._restart_monitor()
        self.refresh_priority_rules_table()
        messagebox.showinfo(
            self.i18n.t("msg_info"), self.i18n.t("msg_deleted_checked_setting")
        )

    # ===== Startup management =====

    def _on_startup_toggle(self):
        """Handle startup toggle"""
        enable = self.ui_builder.startup_var.get()
        try:
            StartupManager.register_startup(enable)
            self._save_config()
            messagebox.showinfo(self.i18n.t("msg_info"), self.i18n.t("msg_startup"))
        except (RuntimeError, OSError) as e:
            messagebox.showerror(
                self.i18n.t("msg_error"), self.i18n.t("msg_startup_error", error=str(e))
            )

    # ===== Priority monitoring =====

    def _start_monitor(self):
        self.monitor.start(self._get_active_priority_rules, self._get_update_interval)

    def _restart_monitor(self):
        """Re-run the monitor so rule/interval changes take effect immediately."""
        self.monitor.restart(self._get_active_priority_rules, self._get_update_interval)

    def _get_active_priority_rules(self):
        """Return currently active rules for monitor loop."""
        return [
            rule.copy() for rule in self.priority_rules if rule.get("enabled", True)
        ]

    def _get_update_interval(self):
        """Get priority update interval in seconds"""
        val = self.prio_freq_key.get()
        if val == "first only":
            return 0
        try:
            return int(val.rstrip("s"))
        except ValueError:
            return 1

    # ===== Config management =====

    def _sync_ui_controls_from_state(self):
        """Apply current state variables to UI controls."""
        if not self.ui_builder.settings_frame:
            return

        current_locale = self.i18n.translations[self.i18n.current_lang].get(
            "locale", self.i18n.current_lang
        )
        self.ui_builder.lang_display_var.set(current_locale)

        theme_display = next(
            (
                d
                for d, k in self.ui_builder.theme_map.items()
                if k == self.theme_key.get()
            ),
            None,
        )
        if theme_display:
            self.ui_builder.theme_display_var.set(theme_display)

        proc_display = next(
            (
                d
                for d, k in self.ui_builder.proc_map.items()
                if k == self.proc_freq_key.get()
            ),
            None,
        )
        if proc_display:
            self.ui_builder.proc_freq_display_var.set(proc_display)

        prio_display = next(
            (
                d
                for d, k in self.ui_builder.prio_map.items()
                if k == self.prio_freq_key.get()
            ),
            None,
        )
        if prio_display:
            self.ui_builder.prio_freq_display_var.set(prio_display)

        ui_config = self.config.get("ui", {})
        self.ui_builder.startup_var.set(
            bool(ui_config.get("start_with_windows", False))
        )
        self.ui_builder.tray_var.set(bool(ui_config.get("minimize_to_tray", True)))
        self.ui_builder.check_updates_var.set(bool(ui_config.get("check_updates", True)))

    def _build_config_payload(self):
        """Build config object from current app state."""
        return {
            "ui": {
                "language": self.i18n.current_lang,
                "theme": self.theme_key.get(),
                "process_refresh": self.proc_freq_key.get(),
                "priority_update": self.prio_freq_key.get(),
                "start_with_windows": bool(self.ui_builder.startup_var.get())
                if self.ui_builder.settings_frame
                else False,
                "minimize_to_tray": self._tray_enabled(),
                "check_updates": self._updates_enabled(),
            },
            "priority_rules": self.priority_rules,
        }

    # ===== Update check =====

    def _updates_enabled(self):
        if self.ui_builder.settings_frame:
            return bool(self.ui_builder.check_updates_var.get())
        return bool(self.config.get("ui", {}).get("check_updates", True))

    def _schedule_update_check(self):
        """Run an update check in the background, then repeat every 24 hours."""
        if self._updates_enabled():
            threading.Thread(target=self._update_worker, daemon=True).start()
        self.after(update_checker.CHECK_INTERVAL_MS, self._schedule_update_check)

    def _update_worker(self, manual=False):
        try:
            self._update_results.put((update_checker.check_for_update(), manual, None))
        except update_checker.UpdateCheckError as e:
            self._update_results.put((None, manual, str(e)))

    def _poll_update_result(self):
        """Pick up background check/download results on the Tk thread."""
        try:
            info, manual, error = self._update_results.get_nowait()
        except queue.Empty:
            pass
        else:
            if error is not None:
                if manual:
                    messagebox.showerror(
                        self.i18n.t("msg_error"),
                        self.i18n.t("update_check_failed", error=error),
                    )
            elif info is None:
                if manual:
                    version = update_checker.get_current_version() or self.i18n.t(
                        "version_dev"
                    )
                    messagebox.showinfo(
                        self.i18n.t("msg_info"),
                        self.i18n.t("update_up_to_date", version=version),
                    )
            elif manual or (
                self._updates_enabled() and info.tag != self._notified_version
            ):
                self._notified_version = info.tag
                self._offer_update(info)

        try:
            status, payload = self._install_results.get_nowait()
        except queue.Empty:
            pass
        else:
            self._downloading = False
            self.title(self.i18n.t("app_title"))
            if status == "ok":
                messagebox.showinfo(
                    self.i18n.t("msg_info"), self.i18n.t("update_installing")
                )
                try:
                    update_checker.launch_installer(payload)
                except OSError as e:
                    messagebox.showerror(
                        self.i18n.t("msg_error"),
                        self.i18n.t("update_download_failed", error=str(e)),
                    )
                else:
                    self._quit_app()
                    return
            else:
                messagebox.showerror(
                    self.i18n.t("msg_error"),
                    self.i18n.t("update_download_failed", error=payload),
                )
        self.after(1000, self._poll_update_result)

    def _offer_update(self, info):
        """Ask whether to download+install (or just open the release page)."""
        if info.msi_url:
            if self._downloading:
                return
            if messagebox.askyesno(
                self.i18n.t("update_available_title"),
                self.i18n.t("update_available_message", version=info.tag),
            ):
                self._downloading = True
                self.title(
                    f"{self.i18n.t('app_title')} - {self.i18n.t('update_downloading')}"
                )
                threading.Thread(
                    target=self._download_worker, args=(info,), daemon=True
                ).start()
        elif messagebox.askyesno(
            self.i18n.t("update_available_title"),
            self.i18n.t("update_available_message_no_installer", version=info.tag),
        ):
            webbrowser.open(info.page_url)

    def _download_worker(self, info):
        try:
            path = update_checker.download_installer(info)
        except (OSError, ValueError) as e:
            self._install_results.put(("error", str(e)))
        else:
            self._install_results.put(("ok", path))

    def _on_check_updates_toggle(self):
        self._save_config()
        if self._updates_enabled():
            threading.Thread(target=self._update_worker, daemon=True).start()

    def _on_check_updates_now(self):
        threading.Thread(
            target=self._update_worker, kwargs={"manual": True}, daemon=True
        ).start()

    def _save_config(self):
        """Persist current state to config.json."""
        self.config = self._build_config_payload()
        self.config_manager.save(self.config)

    # ===== System tray =====

    def _tray_enabled(self):
        if self.ui_builder.settings_frame:
            return bool(self.ui_builder.tray_var.get())
        return bool(self.config.get("ui", {}).get("minimize_to_tray", True))

    def _sync_tray(self, restart=False):
        """Make the tray icon match the "minimize to tray" setting."""
        if restart and self.tray_manager is not None:
            self.tray_manager.stop()
            self.tray_manager = None

        if self._tray_enabled():
            if self.tray_manager is None:
                # Callbacks run on the tray thread: hand them over to Tk via a queue.
                self.tray_manager = TrayManager(
                    self.i18n.t("app_title"),
                    {
                        "show": lambda: self._tray_events.put("show"),
                        "exit": lambda: self._tray_events.put("exit"),
                        "show_label": self.i18n.t("tray_show"),
                        "exit_label": self.i18n.t("tray_exit"),
                    },
                )
            if self.tray_manager.is_available():
                self.tray_manager.start()
        elif self.tray_manager is not None:
            self.tray_manager.stop()
            self.tray_manager = None

    def _on_tray_toggle(self):
        self._save_config()
        self._sync_tray()

    def _poll_tray_events(self):
        try:
            while True:
                event = self._tray_events.get_nowait()
                if event == "show":
                    self._show_from_tray()
                elif event == "exit":
                    self._quit_app()
                    return
        except queue.Empty:
            pass
        self.after(200, self._poll_tray_events)

    # ===== Window management =====

    def _periodic_refresh(self):
        """Periodic refresh of process list"""
        if self.refresh_interval > 0:
            self.refresh_process_list()
        self.after(max(500, self.refresh_interval), self._periodic_refresh)

    def _on_close(self):
        """Handle window close: hide to the tray when enabled, otherwise quit."""
        self._save_config()
        if (
            self._tray_enabled()
            and self.tray_manager is not None
            and self.tray_manager.is_available()
        ):
            self.withdraw()
        else:
            self._quit_app()

    def _show_from_tray(self):
        """Restore the window (the tray icon stays)."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def _quit_app(self):
        """Fully exit the application."""
        if self.tray_manager:
            self.tray_manager.stop()
        self.monitor.stop()
        self.quit()


if __name__ == "__main__":
    app = App()
    app.mainloop()
