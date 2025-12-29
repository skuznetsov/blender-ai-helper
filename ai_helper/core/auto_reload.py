import os
import time

import bpy

from . import reload as reload_utils

_ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LAST_MTIMES = {}
_TIMER_RUNNING = False
_DEBOUNCE_SEC = 0.5
_LAST_RELOAD = 0.0


def _get_prefs():
    addon = bpy.context.preferences.addons.get("ai_helper")
    if addon is None:
        return None
    return addon.preferences


def _collect_mtimes(root: str) -> dict:
    mtimes = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in ("__pycache__", ".git", ".venv", "venv", ".pytest_cache")
        ]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            try:
                mtimes[path] = os.path.getmtime(path)
            except OSError:
                continue
    return mtimes


def _has_changes(prev: dict, current: dict) -> bool:
    for path, mtime in current.items():
        if prev.get(path) != mtime:
            return True
    for path in prev:
        if path not in current:
            return True
    return False


def _stop_timer():
    global _TIMER_RUNNING
    if not _TIMER_RUNNING:
        return
    try:
        bpy.app.timers.unregister(_auto_reload_timer)
    except Exception:
        pass
    _TIMER_RUNNING = False


def _auto_reload_timer():
    global _LAST_MTIMES, _TIMER_RUNNING, _LAST_RELOAD
    prefs = _get_prefs()
    if prefs is None or not getattr(prefs, "auto_reload_enabled", False):
        _TIMER_RUNNING = False
        return None

    interval = max(0.2, float(getattr(prefs, "auto_reload_interval", 1.0)))
    current = _collect_mtimes(_ADDON_ROOT)
    if _LAST_MTIMES and _has_changes(_LAST_MTIMES, current):
        now = time.monotonic()
        if now - _LAST_RELOAD >= _DEBOUNCE_SEC:
            _LAST_RELOAD = now
            _LAST_MTIMES = current
            _TIMER_RUNNING = False
            reload_utils.schedule_reload()
            return None
    _LAST_MTIMES = current
    return interval


def ensure_timer():
    global _LAST_MTIMES, _TIMER_RUNNING
    prefs = _get_prefs()
    if prefs is None or not getattr(prefs, "auto_reload_enabled", False):
        _stop_timer()
        return
    if _TIMER_RUNNING:
        return
    _LAST_MTIMES = _collect_mtimes(_ADDON_ROOT)
    _TIMER_RUNNING = True
    bpy.app.timers.register(_auto_reload_timer, first_interval=0.5)


def register():
    ensure_timer()


def unregister():
    _stop_timer()
