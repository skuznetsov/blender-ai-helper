import bpy

ADDON_ID = "ai_helper"


def get_prefs():
    addon = bpy.context.preferences.addons.get(ADDON_ID)
    return addon.preferences if addon else None
