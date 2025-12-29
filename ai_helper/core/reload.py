import addon_utils
import bpy

_RELOAD_PENDING = False
_ADDON_NAME = "ai_helper"


def _do_reload():
    global _RELOAD_PENDING
    _RELOAD_PENDING = False
    try:
        addon_utils.disable(_ADDON_NAME, default_set=True)
        addon_utils.enable(_ADDON_NAME, default_set=True)
    except Exception as exc:
        print(f"[ai_helper] Reload failed: {exc}")
    return None


def schedule_reload(delay: float = 0.1) -> bool:
    global _RELOAD_PENDING
    if _RELOAD_PENDING:
        return False
    _RELOAD_PENDING = True
    bpy.app.timers.register(_do_reload, first_interval=max(0.0, delay))
    return True
