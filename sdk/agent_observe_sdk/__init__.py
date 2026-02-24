__version__ = "0.1.0"

try:
    from .observer import Observer
except Exception:
    Observer = None

if Observer is None:
    class Observer:
        """NoOp fallback — SDK import failed, telemetry disabled, agent unaffected."""
        def __init__(self, *args, **kwargs):
            pass
        def track(self, fn=None, **kwargs):
            if fn is not None:
                return fn
            return lambda f: f
        def wrap(self, fn=None, **kwargs):
            return fn

__all__ = ["Observer"]
