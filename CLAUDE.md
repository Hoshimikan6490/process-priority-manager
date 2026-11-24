# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Windows-only Tkinter GUI (Python 3.12 exactly: `>=3.12,<3.13`) that keeps processes whose name/PID contains a keyword at a chosen priority. UI text and the README are in Japanese. There is no test suite or linter configured.

## Commands

- Install deps: `pip install -r requirements.txt` (psutil, pystray, Pillow)
- Run: `python main.py`
- Build MSI: `python installer/build_msi.py` (needs uv and WiX Toolset v4+ with `WixToolset.UI.wixext`). Output goes to `appdist/windowsmsi/dist/`.

## Architecture

`main.py` defines `App(tk.Tk)`, which wires together the modules in `src/`:

- `config_manager.py`: persists settings to `%APPDATA%\Process Priority Manager\config.json` and validates them against the `VALID_*` sets. The `config.json` in the repo root is not the runtime config. On first run it also reads the registry key `Software\Hoshimikan6490\Process Priority Manager` (value `CheckUpdates`), which the MSI installer writes.
- `monitor.py`: `ProcessMonitor` runs a daemon thread that re-applies the enabled priority rules via psutil. It calls back into `App` for the current rules and interval, so rule edits take effect without restarting the thread. Each loop owns its own stop event, and `restart()` replaces the loop. An interval of 0 ("first only") makes the loop run once and exit.
- `priority_manager.py`, `process_manager.py`: priority name ↔ psutil value mapping, and process listing.
- `ui_builder.py`: builds the Tk widgets. `App._build_callbacks()` passes it a callback table, so the UI holds no logic. `widgets.py` has custom widgets such as `ToggleSwitch`.
- `tray_manager.py`: the pystray tray icon runs on its own thread and talks to Tk only through the `queue.Queue` that `App._poll_tray_events` drains. Never touch Tk widgets from a non-main thread.
- `update_checker.py`: checks GitHub Releases for a newer `.msi` and downloads it. It reads the current version from the installed package metadata (`pyproject.toml`). Results come back to the UI thread via `_update_results` / `_install_results` queues.
- `i18n.py` + `locales/{ja,en}.json`: every locale file is auto-loaded. To add a language, add a JSON file and the code in `ConfigManager.VALID_LANGUAGES`.
- `system_startup.py`: registers or removes the start-with-Windows entry.

The settings keys (theme, refresh intervals, languages, priorities) are string identifiers such as `"1s"`, `"first only"` and `"RealTime"`. They are duplicated in `ConfigManager.VALID_*`, `App.PROC_REFRESH_MS` and the UI, so keep them in sync when adding options.

## Packaging and versioning

- The version lives only in `pyproject.toml` (`version`). Bump it there for releases.
- `installer/build_msi.py` runs `pyappdist` (configured under `[tool.pyappdist]` in `pyproject.toml`) to produce a base `.wxs` in `.appdist-build/`. It then patches that file (install scope, install folder, hidden `UpdateCheck` feature that writes the registry value) and compiles it with `installer/UI.wxs` using the WiX CLI. Change installer behaviour in the script or in `UI.wxs`, not in the generated files.
- Silent install options: `CHECKUPDATES=0`, `APPLICATIONFOLDER=...`, `ALLUSERS=1`.
