"""Fresh portable tests for bounded Page Synchronisation body."""
import copy
import unittest
from fractions import Fraction
from elyse_agent import saved_sup_event_18780 as m
from legacy.xp_acq_agent.tests.sup_event_18780_fixtures import full_payload,decoded

class Event18780(unittest.TestCase):
    def test_all33_old_minus_new_and_field32(self):
        p=full_payload();r=m.replay_saved_sup_event_18780(p)
        expected=[float(Fraction.from_float(a)-Fraction.from_float(b))for a,b in zip(p['event_returns']['19499']['19675'],p['event_returns']['19499']['19678'])]
        self.assertEqual(r['differences'],expected);self.assertEqual(r['iteration_count'],33)
        self.assertEqual([x['index']for x in r['iterations']if x['changed']],[0,7,32]);self.assertEqual(r['field_updates'][-1]['value'],33.0)
        self.assertEqual(r['field_updates'][-1]['raw_flattened_field_index'],32)
    def test_fanout_carrier_identity_and_independent_epochs(self):
        args=decoded(m);r=m.project_event_18780(*args);reads=args[1]['19774']
        for i in(0,7,32):
            writes=[a for a in r.local_assignments if a.loop_iteration==i and a.node_uid in('35923','37769')]
            self.assertIs(writes[0].data,writes[1].data)
            self.assertIsNot(writes[0].data,reads[i]);self.assertEqual(writes[0].data[32],float(i+1))
            for j in range(32):self.assertIs(writes[0].data[j],reads[i][j])
        self.assertEqual(r.local_reads[-1].data,4)
    def test_false_unwired_error_and_supplied_loop_error_are_distinct(self):
        args=decoded(m);r=m.project_event_18780(*args)
        self.assertIs(r.iterations[1].supplied_or_returned_error,args[3].unwired_false_case_errors[1])
        self.assertIs(r.supplied_loop_error_output,args[3].loop_error_output)
        self.assertIsNot(r.loop_error_candidate,r.supplied_loop_error_output)
        prop=next(x for x in r.leaf_observations if x.node_uid=='40236');self.assertIs(prop.inputs['40252'],args[3].loop_error_output)
    def test_byte_concat_supplied_format_and_selector_independent(self):
        p=full_payload();r=m.replay_saved_sup_event_18780(p)
        self.assertEqual(r['initial_string_hex'],m.hex_bytes(m.INITIAL_PREFIX+b'A\x00\xff'))
        self.assertEqual(r['message_hex'],m.hex_bytes(m.ERROR_PREFIX+b'\xff\x00A'))
        p['intrinsic_outputs']['20154']=False;p['completed_sinks']=None;r=m.replay_saved_sup_event_18780(p)
        self.assertEqual(r['message_hex'],'5300FF');self.assertTrue(r['returned_error']['status']);self.assertFalse(r['native_error_selector_projection_qualified'])
    def test_dps_busy_nonaccess(self):
        args=list(decoded(m));args[1]=dict(args[1]);args[1]['19687']=(True,)+(False,)*28
        args[0]=m.EventDataReturn(object(),object(),object(),object(),object(),object())
        args[1]['19774']=object();args[1]['8733']=object()
        args[2]=m.NativeBoundaries(object(),object(),object(),{'40566':object()},dict(zip(m.BORDER_UIDS,[object()for _ in m.BORDER_UIDS])))
        args[3]=m.IntrinsicBoundaries(object(),object(),object());args[4]=dict(zip(m.LITERAL_UIDS,[object()for _ in m.LITERAL_UIDS]))
        r=m.project_event_18780(*args);self.assertTrue(r.dps_any);self.assertEqual(r.iteration_count,0);self.assertEqual(r.leaf_observations,())
    def test_unchanged_iteration_nonaccess(self):
        args=list(decoded(m));n=args[2];reads=dict(args[1]);loops=list(n.loop_returns);carriers=list(reads['19774']);unwired=list(n.unwired_inputs['40566'])
        for i in range(33):
            if i in(0,7,32):continue
            loops[i]=object();carriers[i]=object();unwired[i]=object()
        reads['19774']=tuple(carriers);args[1]=reads;args[2]=n._replace(loop_returns=tuple(loops),unwired_inputs={'40566':tuple(unwired)})
        self.assertEqual(m.project_event_18780(*args).iteration_count,33)
    def test_no_changes_still_direct_loop_and_final_sequence(self):
        p=full_payload();p['event_returns']['19499']['19678']=list(p['event_returns']['19499']['19675']);p['completed_sinks']=None
        p['loop_returns']=['opaque']*33;p['local_reads']['19774']=['opaque']*33;p['unwired_inputs']['40566']=['opaque']*33
        r=m.replay_saved_sup_event_18780(p);self.assertEqual(len(r['iterations']),33);self.assertEqual(r['field_updates'],[])
        self.assertEqual([x['node_uid']for x in r['local_assignments']],['20535'])
    def test_index_bounds_and_signed_intersection(self):
        for x in(-1,33,2**31,True,1.0):
            p=full_payload();p['local_reads']['8733']=x
            with self.assertRaises((TypeError,ValueError)):m.replay_saved_sup_event_18780(p)
        p=full_payload();p['loop_returns'][32]['40540']['40574']=[]
        with self.assertRaises(ValueError):m.replay_saved_sup_event_18780(p)
    def test_exact_source_and_native_typed_boundaries(self):
        for key in('source_id','source_version','event_uid','frame_uid'):
            p=full_payload();p[key]='wrong'
            with self.assertRaises(ValueError):m.replay_saved_sup_event_18780(p)
        for key in('status','code','source_hex'):
            p=full_payload();p['intrinsic_outputs']['29296'][key]=1.0
            with self.assertRaises((TypeError,ValueError)):m.replay_saved_sup_event_18780(p)
    def test_numeric_shape_and_strict_json(self):
        for bad in(float('nan'),float('inf'),True,1,2.0**41):
            p=full_payload();p['event_returns']['19499']['19675'][0]=bad
            with self.assertRaises((TypeError,ValueError)):m.replay_saved_sup_event_18780(p)
        p=full_payload();p['event_returns']['19499']['19675'].pop()
        with self.assertRaises(TypeError):m.replay_saved_sup_event_18780(p)
        p=full_payload();p['final_returns']['40371']['55971']='ff'
        with self.assertRaises(ValueError):m.replay_saved_sup_event_18780(p)
    def test_completion_reports_no_schedule_success_claim(self):
        p=full_payload();p['completed_sinks']=[['20535',None],['35923',32]];r=m.replay_saved_sup_event_18780(p)
        self.assertEqual(r['completed_sinks'],p['completed_sinks']);self.assertFalse(r['writer_success_gates_local_assignment'])
        p['completed_sinks']=[['20132',1]]
        with self.assertRaises(ValueError):m.replay_saved_sup_event_18780(p)
    def test_literal_comparison_is_supplied_not_hidden_zero(self):
        p=full_payload();p['literal_inputs']['49984']=0.5;p['completed_sinks']=None
        r=m.replay_saved_sup_event_18780(p);self.assertEqual(sum(x['changed']for x in r['iterations']),30)
        self.assertFalse(r['native_literal_storage_decode_qualified']);self.assertFalse(r['null_model_terminal20047_restored'])

if __name__=='__main__':unittest.main()
