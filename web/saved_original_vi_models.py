"""Shared original-VI models, directly callable without new network routes.

APP-16: complete finite isolated logic. APP-30: conditional projection;
constant decoding and absent field indices remain explicit caller inputs.
Neither function qualifies original native execution.
"""
from legacy.xp_acq_agent.elyse_agent.saved_acq_app16 import (
    compute_vi as compute_acq_app16, compute_saved_app16 as compute_saved_acq_app16,
)
from legacy.xp_acq_agent.elyse_agent.saved_sup_app30 import (
    convert_property_node_font_to_graphics_font as convert_sup_app30,
)

__all__ = ['compute_acq_app16', 'compute_saved_acq_app16', 'convert_sup_app30']

# APP15 uses the exact native20 static literal witness; original LV12 execution
# remains unqualified. No new network routes or caller-supplied literal policy.
from legacy.xp_acq_agent.elyse_agent.saved_acq_app15_static_interpreted import (
    project_app15_static_interpreted as project_acq_app15_static_interpreted,
)

__all__.append('project_acq_app15_static_interpreted')

# SUP APP22 uses the complete independently audited saved source within its
# finite isolated domain; original native connector/runtime remains unqualified.
from legacy.xp_acq_agent.elyse_agent.saved_sup_app22 import (
    project_app22_source as project_sup_app22_source,
)

__all__.append('project_sup_app22_source')
