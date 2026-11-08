"""Partial-order and supplied-error cleanup routing; physical success unknown."""
import copy
import unittest
from elyse_agent.saved_cleanup import CleanupEvent,project_cleanup,replay_saved_cleanup
from elyse_agent.saved_initializer import ErrorValue,OpaqueReference


def full_schedule():
    return [dict(kind='psp_close',index=i) for i in range(27)]+[
        dict(kind='handler',node_uid='88'),dict(kind='tpg_close',bank=51),
        dict(kind='handler',node_uid='68680'),dict(kind='tpg_close',bank=52),
        dict(kind='handler',node_uid='67965'),dict(kind='stop_reset'),dict(kind='frame_returned')]


def payload(schedule=None):
    schedule=full_schedule() if schedule is None else schedule
    returns=[]
    for token in schedule:
        kind=token['kind']
        uid='536' if kind=='psp_close' else str(token['node_uid']) if kind=='handler' else {51:'61121',52:'66474'}[token['bank']] if kind=='tpg_close' else None
        if uid is not None:
            returns.append(dict(node_uid=uid,iteration=token.get('index'),
                 error=dict(status=True,code=-17,source='supplied:'+uid)))
    return dict(source_id='APP-00',uid='246',outer_joined=True,stop_before=True,
        psp_error_seed=dict(status=True,code=-99,source='uninitialized explicit seed'),
        tpg_sessions=['opaque51','opaque52'],schedule=schedule,returned_errors=returns)


class SavedCleanupTests(unittest.TestCase):
    def test_full_frame_returns_even_with_all_supplied_errors_true(self):
        result=replay_saved_cleanup(payload())
        self.assertTrue(result['outputs']['frame_returned'])
        self.assertFalse(result['outputs']['stop_after'])
        self.assertEqual(len(result['calls']),32)
        self.assertFalse(result['resource_close_success_qualified'])
        self.assertFalse(result['external_calls_executed'])

    def test_reset_precedes_partial_blocked_cleanup_without_completion(self):
        data=payload([dict(kind='stop_reset'),dict(kind='psp_close',index=0)])
        result=replay_saved_cleanup(data)
        self.assertFalse(result['outputs']['stop_after'])
        self.assertFalse(result['outputs']['frame_ready'])
        self.assertFalse(result['outputs']['frame_returned'])

    def test_handler_output_unused_and_tpg_errors_have_independent_lanes(self):
        data=payload()
        for row in data['returned_errors']:
            row['error']['source']=row['node_uid']+':'+str(row['iteration'])
        result=replay_saved_cleanup(data)
        self.assertEqual(result['outputs']['psp_error_after']['source'],'536:26')
        calls={c['node_uid']:c for c in result['calls'] if c['iteration'] is None}
        self.assertEqual(calls['88']['error_in']['source'],'536:26')
        self.assertEqual(calls['68680']['error_in']['source'],'61121:None')
        self.assertEqual(calls['67965']['error_in']['source'],'66474:None')
        self.assertEqual(calls['61121']['error_in'],dict(connection='unwired'))

    def test_return_objects_and_session_refs_are_retained(self):
        seed=ErrorValue(True,0,'seed')
        returned=ErrorValue(False,17,'returned')
        session=OpaqueReference('one')
        result=project_cleanup((CleanupEvent('psp_close',0),CleanupEvent('tpg_close',51)),seed,
               (session,OpaqueReference('two')),True,{('536',0):returned,('61121',None):returned})
        self.assertIs(result.state.psp_error_seed,seed)
        self.assertIs(result.state.psp_error_after,returned)
        self.assertIs(result.calls[0].plan.error_in,seed)
        self.assertIs(result.calls[1].plan.task_in,session)

    def test_missing_return_duplicate_and_unused_return_refuse(self):
        data=payload()
        for variant in ('missing','duplicate','unused'):
            invalid=copy.deepcopy(data)
            if variant=='missing':
                invalid['returned_errors'].pop()
            elif variant=='duplicate':
                invalid['returned_errors'].append(invalid['returned_errors'][0])
            else:
                invalid['returned_errors'].append(dict(node_uid='unknown',iteration=None,error=dict(status=False,code=0,source='')))
            self.assertRaises(ValueError,replay_saved_cleanup,invalid)

    def test_handler_precedence_duplicate_reset_and_noninteger_index_refuse(self):
        for schedule in ([dict(kind='handler',node_uid='88')],
                         [dict(kind='handler',node_uid='68680')],
                         [dict(kind='stop_reset'),dict(kind='stop_reset')],
                         [dict(kind='psp_close',index=True)],
                         [dict(kind='frame_returned')]):
            self.assertRaises(ValueError,replay_saved_cleanup,payload(schedule))

    def test_outer_join_and_typed_snapshot_required(self):
        for field,value in (('outer_joined',False),('outer_joined',1),('stop_before',1),('psp_error_seed',None)):
            data=payload()
            data[field]=value
            self.assertRaises((ValueError,TypeError),replay_saved_cleanup,data)

    def test_unknown_identity_unknown_event_and_postreturn_token_refuse(self):
        for field,value in (('uid','227'),('source_id','APP-17'),('extra',0)):
            data=payload()
            data[field]=value
            self.assertRaises(ValueError,replay_saved_cleanup,data)
        data=payload()
        data['schedule']=[dict(kind='unknown')]
        self.assertRaises(ValueError,replay_saved_cleanup,data)
        data=payload()
        data['schedule'].append(dict(kind='stop_reset'))
        self.assertRaises(ValueError,replay_saved_cleanup,data)

    def test_json_error_storage_policy_refuses_and_input_is_unchanged(self):
        data=payload()
        before=copy.deepcopy(data)
        replay_saved_cleanup(data)
        self.assertEqual(data,before)
        for error in (dict(status=1,code=0,source=''),dict(status=False,code=2**31,source='')):
            invalid=copy.deepcopy(data)
            invalid['returned_errors'][0]['error']=error
            self.assertRaises((ValueError,TypeError),replay_saved_cleanup,invalid)


if __name__=='__main__':
    unittest.main()
