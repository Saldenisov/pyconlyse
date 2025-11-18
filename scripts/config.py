#!/usr/bin/env python3
"""
Configuration shim for backward compatibility.

This module re-exports the main configuration from main_app.core.config
to support legacy imports like 'from config import *'.
"""

# Re-export everything from main_app.core.config
try:
    from main_app.core.config import *
except ImportError as e:
    # Fallback if main_app.core.config doesn't exist or has issues
    print(f"Warning: Could not import main_app.core.config: {e}")
    
    # Provide minimal config defaults
    DEBUG = False
    TESTING = False
    VERSION = "unknown"