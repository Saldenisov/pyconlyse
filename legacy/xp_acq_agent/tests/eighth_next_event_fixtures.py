"""Fresh G69 portable data: exact worker payload literals, no native calls."""
import copy

if __package__:
    from .eighth_next_event_fixtures_acq_full_data import (
        _ACQ_FULL,
        _SUP_FULL,
    )
else:
    from eighth_next_event_fixtures_acq_full_data import (
        _ACQ_FULL,
        _SUP_FULL,
    )


if __package__:
    from .eighth_next_event_fixtures_sup_minimum_data import (
        _SUP_MINIMUM,
        _SUP_SPARSE,
    )
else:
    from eighth_next_event_fixtures_sup_minimum_data import (
        _SUP_MINIMUM,
        _SUP_SPARSE,
    )


def acq_payload(new_value=True):
    p=copy.deepcopy(_ACQ_FULL);p['new_value']=new_value;return p

def sup_payload():return copy.deepcopy(_SUP_FULL)
def minimum_sup_payload():return copy.deepcopy(_SUP_MINIMUM)
def sparse_sup_payload():return copy.deepcopy(_SUP_SPARSE)
def oversized_sup_payload():
    """Supplied opaque refs only; original saved literal hypotheses unchanged."""
    p=minimum_sup_payload()
    p['native_returns']['33897']['33900']='R'*6000
    p['native_returns']['33859']['33889']=['Q'*700 for unused in range(64)]
    return p
