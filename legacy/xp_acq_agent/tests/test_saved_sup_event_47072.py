"""Fresh direct G78 source shapes/domains; supplied data are hypotheses."""
import copy
import unittest
from elyse_agent import saved_sup_event_47072 as core
from sup_event_47072_fixtures import full_payload,minimal_payload,sparse_payload,pure_arguments

class Tripwire(object):
    def __getattribute__(self,name):raise AssertionError('Inactive boundary read: '+name)
    def __iter__(self):raise AssertionError('Inactive boundary iterated')
    def __bool__(self):raise AssertionError('Inactive boundary coerced')

class SavedSUP47072Tests(unittest.TestCase):
    def test_three_literal_examples_and_identity(self):
        for factory in (full_payload,minimal_payload,sparse_payload):
            p=factory();before=copy.deepcopy(p);r=core.replay_saved_sup_event_47072(p)
            self.assertEqual(p,before);self.assertEqual(r['frame_uid'],'47072')
            self.assertFalse(r['whole_event_equivalence'])

    def test_direct_dps_copy_and_source_preorder_paths(self):
        args=pure_arguments(core,full_payload());r=core.project_event_47072(**args)
        expected=list(args['local_reads']['47137']);expected[20]=args['new_value'][4];expected[23]=args['new_value'][3];expected[21]=args['new_value'][12]
        self.assertEqual(r['local_assignments'][0]['value'],tuple(expected))
        self.assertIs(r['leaf_observations'][0]['inputs']['32664'],r['local_assignments'][0]['value'])
        self.assertEqual([(f['raw_flattened_field_index'],f['typed_position_path'])for f in r['field_updates']],[(11,(4,)),(10,(3,)),(19,(12,))])
        self.assertEqual([(f['destination_terminal_uid'],f['destination_raw_flattened_field_index'])for f in r['field_updates']],[('47204',20),('47207',23),('68861',21)])

    def test_error_reference_and_byte_concat_identities(self):
        args=pure_arguments(core,full_payload());r=core.project_event_47072(**args)
        returned=args['native_boundaries']['32048']['outputs']['32661'];ref=args['reference_bindings']['31390']['native_reference']
        self.assertIs(r['leaf_observations'][0]['inputs']['32652'],ref)
        self.assertIs(r['case_observations'][0]['source_input_error'],returned)
        self.assertIs(r['byte_concat']['Error_source_bytes'],returned.source_bytes)
        self.assertEqual(r['local_assignments'][1]['value'],core.PREFIX_BYTES+b'\x00\xff')
        self.assertEqual(r['local_assignments'][1]['explicit_paramIdx'],184)

    def test_hypothetical_selector_does_not_gate_on_native_status(self):
        for status in (False,True):
            for arm in (False,True):
                p=full_payload();p['native_boundaries']['32048']['outputs']['32661']['status']=status;p['intrinsic_inputs']['19594']=arm;p['completed_sinks']=[]
                r=core.replay_saved_sup_event_47072(p)
                self.assertEqual(len(r['local_assignments']),2 if arm else 1)
                self.assertEqual(r['case_observations'][0]['selected_frame'],'36477'if arm else'36498')
                self.assertFalse(r['native_ErrorCluster_Case_selection_qualified'])

    def test_busy_branch_nonaccess_and_u32_literal_hypothesis(self):
        args=pure_arguments(core,minimal_payload());wire=Tripwire()
        for key in ('new_value','reference_bindings','unwired_inputs','event_time_40518','intrinsic_inputs','event_outputs'):args[key]=wire
        args['literal_inputs']['35281']=wire;args['native_boundaries']['32048']=wire
        for value in (0,1,2**32-1):
            args['literal_inputs']['42462']=value;r=core.project_event_47072(**args)
            self.assertEqual(r['source_Wait_input_value'],value);self.assertEqual(r['local_assignments'],[])
            self.assertIs(r['supplied_unused_event_outputs'],wire)

    def test_empty_error_arm_prefix_nonaccess(self):
        args=pure_arguments(core,sparse_payload());args['literal_inputs']['35281']=Tripwire();args['literal_inputs']['42462']=Tripwire()
        r=core.project_event_47072(**args);self.assertEqual(len(r['local_assignments']),1)
        self.assertNotIn('byte_concat',r)

    def test_max_source_bytes_concat_and_refusal(self):
        p=full_payload();p['native_boundaries']['32048']['outputs']['32661']['source_hex']='FF'*4096
        r=core.replay_saved_sup_event_47072(p);self.assertEqual(len(r['byte_concat']['value']['bytes_hex']),8402)
        p['native_boundaries']['32048']['outputs']['32661']['source_hex']='FF'*4097
        with self.assertRaises(ValueError):core.replay_saved_sup_event_47072(p)

    def test_completion_reports_are_not_feasible_traces(self):
        p=full_payload();p['completed_sinks']=['40558','32048','47186'];r=core.replay_saved_sup_event_47072(p)
        self.assertEqual(r['completed_sinks'],p['completed_sinks']);self.assertFalse(r['completion_observations_are_feasible_trace'])
        for value in (['40558','40558'],['47137'],['28277']):
            p['completed_sinks']=value
            with self.assertRaises(ValueError):core.replay_saved_sup_event_47072(p)

    def test_strict_page_dps_typed_shapes(self):
        mutants=[]
        for value in ([False]*28,[False]*30,[0]*29):
            p=full_payload();p['local_reads']['47137']=value;mutants.append(p)
        for path,value in ((0,[0.0]*6),(0,[0]*7),(4,1),(1,65536),(10,{'bytes_hex':'ff'})):
            p=full_payload();p['new_value'][path]=value;mutants.append(p)
        for p in mutants:
            with self.assertRaises(ValueError):core.replay_saved_sup_event_47072(p)

    def test_literal_reference_error_and_time_boundaries(self):
        p=full_payload();p['literal_inputs']['35281']={'bytes_hex':'00'}
        with self.assertRaises(ValueError):core.replay_saved_sup_event_47072(p)
        for key,value in (('status',0),('code',2**31),('source_hex','ff')):
            p=full_payload();p['native_boundaries']['32048']['outputs']['32661'][key]=value
            with self.assertRaises(ValueError):core.replay_saved_sup_event_47072(p)
        for value in (True,-1,2**32,0.0):
            p=minimal_payload();p['literal_inputs']['42462']=value
            with self.assertRaises(ValueError):core.replay_saved_sup_event_47072(p)
            p=full_payload();p['event_time_40518']=value
            with self.assertRaises(ValueError):core.replay_saved_sup_event_47072(p)

    def test_exact_source_and_native_false_policy(self):
        for key in ('source_id','source_version','event_uid','frame_uid'):
            p=full_payload();p[key]='foreign'
            with self.assertRaises(ValueError):core.replay_saved_sup_event_47072(p)
        for flag in core.UNQUALIFIED_FLAGS:
            p=full_payload();p['unqualified_boundaries'][flag]=True
            with self.assertRaises(ValueError):core.replay_saved_sup_event_47072(p)

    def test_json_transport_guards_and_unused_leaf_output(self):
        p=full_payload();p['native_boundaries']['28270']['outputs']={'opaque_unused':'not native U32'}
        r=core.replay_saved_sup_event_47072(p);self.assertEqual(r['leaf_observations'][-1]['supplied_outputs'],p['native_boundaries']['28270']['outputs'])
        for value in (float('nan'),float('inf')):
            p=full_payload();p['new_value'][0][0]=value
            with self.assertRaises(ValueError):core.replay_saved_sup_event_47072(p)
        p=full_payload();p['execute_native']=True
        with self.assertRaises(ValueError):core.replay_saved_sup_event_47072(p)

if __name__=='__main__':unittest.main()
