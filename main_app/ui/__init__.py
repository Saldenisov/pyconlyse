"""User interface components for PyConlyse."""

try:
    from .main_window import PyConlyseMainWindow

    __all__ = ["PyConlyseMainWindow"]
except ImportError:
    # PyQt5 might not be available
    __all__ = []
