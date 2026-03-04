# Backward compatibility wrapper for DS_Motor import
from .motor import DS_MOTORIZED_MONO_AXIS as DS_Motor

# Export for compatibility
__all__ = ["DS_Motor"]
