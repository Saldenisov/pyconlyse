"""Explicit error/reference lanes; no default-success or task-validity claim."""
import copy
import unittest
from elyse_agent.saved_initializer import (
    ErrorValue, InitializerFixture, OpaqueReference, STAGES, UNWIRED,
    project_initializer_frame, project_ai_test_frame, replay_saved_initializer,
)


def error(status=False, code=-200284):
    return dict(status=status, code=code, source='explicit external return')


def payload():
    return dict(source_id='APP-00', uid='227', fixtures=[
        dict(tasks=['supplied:{0}:{1}'.format(i,j) for j in range(sum(n for b,n in stage[4]))],
             error_out=error(i == 1)) for i,stage in enumerate(STAGES)],
             clear_returns={'1532':error(True,17)})


class SavedInitializerTests(unittest.TestCase):
    def test_clear_return_status_does_not_skip_later_initializer(self):
        result = replay_saved_initializer(payload())
        self.assertEqual([s['node_uid'] for s in result['steps']], ['593','262','1532','500','620'])
        self.assertEqual(result['steps'][3]['error_in'], payload()['clear_returns']['1532'])
        self.assertEqual(result['steps'][3]['local_assignments'][0]['bank'], 22)
        self.assertFalse(result['external_calls_executed'])
        self.assertFalse(result['reference_validity_qualified'])

    def test_nonzero_warning_code_selects_pass_through(self):
        data = payload()
        for fixture in data['fixtures']:
            fixture['error_out'] = error(False)
        data['clear_returns'] = {}
        result = replay_saved_initializer(data)
        self.assertEqual(len(result['steps']),4)
        self.assertEqual(result['outputs']['next_read_error']['code'],-200284)

    def test_original_error_and_reference_objects_retained(self):
        fixtures = tuple(InitializerFixture(tuple(OpaqueReference(str(i)) for i in range(sum(n for b,n in s[4]))),
                            ErrorValue(False,100+j,str(j))) for j,s in enumerate(STAGES))
        result = project_initializer_frame(fixtures,{})
        self.assertIs(result.steps[0].error_in, UNWIRED)
        self.assertIs(result.next_read_error, fixtures[-1].error_out)
        self.assertIs(result.steps[1].local_assignments[0][1], fixtures[1].tasks[0])

    def test_fallback_retains_original_read_error_and_replacement_refs(self):
        original = ErrorValue(True,0,'read')
        fixture = InitializerFixture((OpaqueReference('one'),OpaqueReference('two')),ErrorValue(True,99,'retry'))
        clears = {uid:ErrorValue(True,-17,uid) for uid in ('2134','4034','7931','2268')}
        result = project_ai_test_frame(original,fixture,clears)
        self.assertIs(result.original_read_error,original)
        self.assertIs(result.sequence_local_306,clears['2268'])
        self.assertIs(result.steps[3].local_assignments[0][1],fixture.tasks[0])
        self.assertIs(result.steps[3].error_in,clears['7931'])

    def test_warning_cannot_consume_unselected_fallback_returns(self):
        data = dict(source_id='APP-00',uid='133',read_error=error(False),fallback_result=None,clear_returns=None)
        result = replay_saved_initializer(data)
        self.assertEqual(result['steps'],[])
        self.assertEqual(result['outputs']['original_read_error'],result['outputs']['sequence_local_306'])
        data['clear_returns']={'2134':error()}
        self.assertRaises(ValueError,replay_saved_initializer,data)

    def test_selected_clear_returns_are_required_exactly(self):
        for clears in ({},{'1532':error(),'383':error()}):
            data=payload()
            data['clear_returns']=clears
            self.assertRaises(ValueError,replay_saved_initializer,data)

    def test_reference_cardinality_and_empty_tokens_refuse(self):
        for tasks in ([],[''],['x']*7):
            data=payload()
            data['fixtures'][0]['tasks']=tasks
            self.assertRaises(ValueError,replay_saved_initializer,data)

    def test_storage_errors_are_adapter_policy_and_refuse(self):
        for bad in (dict(status=1,code=0,source=''),error(False,True),error(False,2**31),dict(status=False,code=0,source=7)):
            data=payload()
            data['fixtures'][0]['error_out']=bad
            self.assertRaises((ValueError,TypeError),replay_saved_initializer,data)

    def test_exact_identity_and_fields_and_input_immutability(self):
        data=payload()
        before=copy.deepcopy(data)
        replay_saved_initializer(data)
        self.assertEqual(data,before)
        for key,value in (('uid','missing'),('source_id','APP-17'),('extra',0)):
            invalid=copy.deepcopy(data)
            invalid[key]=value
            self.assertRaises(ValueError,replay_saved_initializer,invalid)


if __name__=='__main__':
    unittest.main()
