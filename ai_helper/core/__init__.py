from . import logger

try:
    from .settings import get_prefs
except ModuleNotFoundError:
    def get_prefs():
        return None

__all__ = ["logger", "get_prefs"]
