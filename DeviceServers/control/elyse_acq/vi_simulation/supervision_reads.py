"""Qualified Supervision caller slices shared with the Python3.4 replay server."""
from legacy.xp_acq_agent.elyse_agent.saved_sup_reads import (
    ReaderReturn,independent_read,read_chain,replay_saved_sup_reads,
)

__all__=('ReaderReturn','read_chain','independent_read','replay_saved_sup_reads')
