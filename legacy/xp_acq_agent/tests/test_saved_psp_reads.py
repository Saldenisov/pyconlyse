"""Supplied-return caller body preserves identities and final-status selection."""
import unittest
from elyse_agent import saved_psp_reads as core
from elyse_agent.saved_xnode import ErrorValue


def fixtures():
    defaults,returns={},{}
    for uid,tag,bank,size,element in core.SITES:
        defaults[uid]=(False if element is bool else 1.0,)*size
        returns[uid]=core.PspReturn((True if element is bool else 2.0,)*size,ErrorValue(False,0,uid))
    return defaults,returns


def payload():
    defaults,returns=fixtures()
    return dict(source_id='APP-00',uid='10115',frame_returned=True,
        defaults={uid:list(data) for uid,data in defaults.items()},
        returns={uid:dict(data=list(value.data),error=dict(value.error._asdict())) for uid,value in returns.items()},
        stop_before=True,tcp_ed_before=True)


class SavedPspReadTests(unittest.TestCase):
    def test_each_call_and_assignment_retains_own_supplied_objects(self):
        defaults,returns=fixtures()
        result=core.read_frame(defaults,returns,True,True)
        for call,assignment in zip(result.calls,result.data_assignments):
            self.assertIs(call.default_data,defaults[call.node_uid])
            self.assertIs(call.returned,returns[call.node_uid])
            self.assertIs(assignment[1],returns[call.node_uid].data)
        self.assertIs(result.calls[0].error_in,core.UNWIRED)

    def test_error_chain_preserves_each_error_identity(self):
        defaults,returns=fixtures()
        result=core.read_frame(defaults,returns,False,False)
        for before,after in zip(result.calls,result.calls[1:]):
            self.assertIs(after.error_in,before.returned.error)

    def test_fault_data_is_not_replaced_by_prior(self):
        defaults,returns=fixtures()
        fault=ErrorValue(True,-17,'earlier fault')
        returns['10310']=core.PspReturn((7.0,)*10,fault)
        result=core.read_frame(defaults,returns,True,True)
        self.assertEqual(dict(result.data_assignments)[9],(7.0,)*10)
        self.assertEqual(result.fault_assignments,())

    def test_last_status_clears_flags_even_with_zero_code(self):
        defaults,returns=fixtures()
        returns['22840']=core.PspReturn((False,)*12,ErrorValue(True,0,'final'))
        result=core.read_frame(defaults,returns,True,True)
        self.assertEqual(result.fault_assignments,((30,False),(45,False)))
        self.assertFalse(result.stop_after)
        self.assertFalse(result.tcp_ed_after)

    def test_nonzero_code_with_false_status_does_not_select_fault(self):
        defaults,returns=fixtures()
        returns['22840']=core.PspReturn((True,)*12,ErrorValue(False,-999,'warning'))
        self.assertTrue(core.read_frame(defaults,returns,True,True).stop_after)

    def test_json_partial_frame_and_wrong_shape_refuse(self):
        data=payload()
        data['frame_returned']=False
        self.assertRaises(ValueError,core.replay_saved_psp_reads,data)
        data=payload()
        data['returns']['19950']['data']=[True]*28
        self.assertRaises(TypeError,core.replay_saved_psp_reads,data)

    def test_json_float_policy_and_error_code_bound_refuse(self):
        data=payload()
        data['defaults']['10310'][0]=float('inf')
        self.assertRaises(ValueError,core.replay_saved_psp_reads,data)
        data=payload()
        data['returns']['22840']['error']['code']=2**31
        self.assertRaises(ValueError,core.replay_saved_psp_reads,data)

    def test_exact_uid_and_inert_result(self):
        data=payload()
        result=core.replay_saved_psp_reads(data)
        self.assertFalse(result['external_calls_executed'])
        self.assertFalse(result['native_default_return_semantics_qualified'])
        data['uid']='8105'
        self.assertRaises(ValueError,core.replay_saved_psp_reads,data)


if __name__=='__main__':
    unittest.main()
