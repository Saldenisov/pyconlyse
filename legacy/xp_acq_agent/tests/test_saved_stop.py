"""Saved opposing stop writes and snapshot ordering;no apparatus execution."""
import itertools
import unittest
from collections import Counter
from elyse_agent import saved_stop as core


def payload(facet='runtime_trace'):
    if facet=='reset':return dict(source_id='APP-00',facet=facet,stage='post_init',
        before=dict(stop=True,tcp_ed=True,emergency_stop=True,general_stop=True))
    return dict(source_id='APP-00',facet=facet,stop_before=True,tcp_before=False,
        schedule=[dict(kind='read_stop',loop_uid=u) for u in reversed(core.RUNTIME_LOOPS)])


class StopTests(unittest.TestCase):
    def test_opposing_writes_all720_orders(self):
        entries=tuple(core.ErrorArmEntry(u) for u in sorted(core.ERROR_SITES))
        writers=tuple(core.LocalAssignment(n) for u in sorted(core.ERROR_SITES) for n,_,_ in core.ERROR_SITES[u][1])
        counts=Counter()
        for order in itertools.permutations(writers):
            result=core.replay_runtime(entries+order,stop_before=False,tcp_before=False)
            counts[(result.stop_after,result.tcp_after)]+=1
        self.assertEqual(counts,{(True,True):320,(True,False):160,(False,True):160,(False,False):80})

    def test_partial_snapshot_order_is_explicit(self):
        result=core.replay_saved_stop(payload())
        self.assertEqual(tuple(r[0] for r in result['pending_snapshots']),tuple(reversed(core.RUNTIME_LOOPS)))
        self.assertFalse(result['external_calls_executed'])

    def test_resets_preserve_unwritten_memory(self):
        result=core.replay_saved_stop(payload('reset'))
        self.assertEqual(result['after'],dict(stop=True,tcp_ed=False,emergency_stop=False,general_stop=True))
        self.assertFalse(result['atomic_local_pairs_qualified'])

    def test_outer_join_requires_all_exits_and_unknown_tokens_refuse(self):
        data=payload();data['schedule']=[dict(kind='outer_tcp_read')]
        with self.assertRaises(ValueError):core.replay_saved_stop(data)
        data['schedule']=[dict(kind='hardware_stop')]
        with self.assertRaises(ValueError):core.replay_saved_stop(data)


if __name__=='__main__':unittest.main()
