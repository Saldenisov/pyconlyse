"""Bounded pure projection of the saved NI6220 Read mean loop.

The supplied sample_count also feeds LabVIEW's channel-mean For N.
This helper models nonnegative integer N and nonempty returned rows only;
validation errors are Python safeguards, not attributed to LabVIEW.
No device, transport, task, clock or timeout is executed.
"""


from legacy.xp_acq_agent.elyse_agent.saved_ni6220 import (
    project_ni6220_channel_means,
    project_saved_ni6220_read,
    replay_saved_ni6220_read,
)

__all__ = ["project_ni6220_channel_means", "project_saved_ni6220_read", "replay_saved_ni6220_read"]
