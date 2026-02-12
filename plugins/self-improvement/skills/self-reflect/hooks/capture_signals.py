"""
capture_signals.py — Importable module wrapper for capture-signals.py.
Python cannot import modules with hyphens, so this re-exports the public API
from the hook file (capture-signals.py) to make it testable.
"""
import importlib
import os
import sys

# Import the hyphenated module using importlib
_hook_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture-signals.py")
_spec = importlib.util.spec_from_file_location("capture_signals_hook", _hook_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export public API
extract_signals_from_transcript = _mod.extract_signals_from_transcript
read_transcript = _mod.read_transcript
