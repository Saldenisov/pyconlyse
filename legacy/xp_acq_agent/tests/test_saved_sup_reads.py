"""No supplied fault gates local assignments;independent Error is unused."""
import copy
import unittest
from elyse_agent import saved_sup_reads as core


def payload(independent=False):
    uids=(core.INDEPENDENT,) if independent else core.CHAIN
    return dict(source_id='APP-17',uid='51964' if independent else '13595',
        frames_returned=['49696'] if independent else ['14799','15121'],
        defaults={uid:dict(default=uid) for uid in uids},references={uid:'supplied:'+uid for uid in uids},
        returns={uid:dict(data=dict(returned=uid),error=dict(status=False,code=-17,source=uid)) for uid in uids})


class SupReadCallerTests(unittest.TestCase):
    def test_unconditional_data_and_error_identity(self):
        defaults={u:object() for u in core.CHAIN};references={u:object() for u in core.CHAIN}
        returns={u:core.ReaderReturn(object(),core.ErrorValue(i%2==0,-17,u)) for i,u in enumerate(core.CHAIN)}
        before=dict(returns)
        result=core.read_chain(defaults,references,returns)
        self.assertIs(result.calls[0].error_in,core.UNWIRED)
        for i,call in enumerate(result.calls):
            self.assertIs(call.reference_in,references[call.node_uid])
            self.assertIs(call.returned,returns[call.node_uid])
            self.assertIs(result.local_assignments[i][2],returns[call.node_uid].data)
            if i:self.assertIs(call.error_in,returns[core.CHAIN[i-1]].error)
        self.assertEqual(returns,before)
        self.assertIs(result.final_error,returns[core.CHAIN[-1]].error)

    def test_independent_read_has_no_incoming_chain_or_final_error(self):
        uid=core.INDEPENDENT
        returned=core.ReaderReturn(object(),core.ErrorValue(True,0,'fault supplied'))
        result=core.independent_read({uid:object()},{uid:object()},{uid:returned})
        self.assertIs(result.calls[0].error_in,core.UNWIRED)
        self.assertIs(result.local_assignments[0][2],returned.data)
        self.assertIsNone(result.final_error)

    def test_supplied_reference_and_data_are_not_decoded(self):
        class NoAccess(object):
            def __getitem__(self,key):raise AssertionError('opaque snapshot read')
            def __bool__(self):raise AssertionError('opaque snapshot tested')
        defaults={u:NoAccess() for u in core.CHAIN};refs={u:NoAccess() for u in core.CHAIN}
        returns={u:core.ReaderReturn(NoAccess(),core.ErrorValue(True,0,u)) for u in core.CHAIN}
        self.assertEqual(len(core.read_chain(defaults,refs,returns).local_assignments),13)

    def test_json_inert_both_selected_slices(self):
        for independent in (False,True):
            data=payload(independent);before=copy.deepcopy(data)
            result=core.replay_saved_sup_reads(data)
            self.assertEqual(data,before)
            self.assertFalse(result['external_calls_executed'])
            self.assertFalse(result['whole_timeout_equivalence'])

    def test_refuse_partial_frames_and_wrong_sites(self):
        for key,value in (('source_id','APP-00'),('uid','5909'),('frames_returned',['14799'])):
            data=payload();data[key]=value
            with self.assertRaises(ValueError):core.replay_saved_sup_reads(data)
        data=payload();data['returns'].pop(core.CHAIN[0])
        with self.assertRaises(ValueError):core.replay_saved_sup_reads(data)

    def test_refuse_storage_error_coercions(self):
        for key,value in (('status',1),('code',True),('source',None),('code',2**31)):
            data=payload();data['returns'][core.CHAIN[0]]['error'][key]=value
            with self.assertRaises((ValueError,TypeError)):core.replay_saved_sup_reads(data)


if __name__=='__main__':unittest.main()
