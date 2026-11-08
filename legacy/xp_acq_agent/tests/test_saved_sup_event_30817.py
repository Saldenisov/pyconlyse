"""Fresh G79 Boolean copies, independent observations and byte-domain checks."""
import copy
import unittest
from elyse_agent import saved_sup_event_30817 as core
from sup_event_30817_fixtures import full_payload,minimal_payload,sparse_payload,pure_arguments

class Tripwire(object):
    def __getattribute__(self,name):raise AssertionError('Inactive boundary read: '+name)
    def __iter__(self):raise AssertionError('Inactive boundary iterated')
    def __bool__(self):raise AssertionError('Inactive boundary coerced')

class SavedSUP30817Tests(unittest.TestCase):
    def test_three_literal_json_examples_remain_unchanged(self):
        for factory in (full_payload,minimal_payload,sparse_payload):
            p=factory();before=copy.deepcopy(p);r=core.replay_saved_sup_event_30817(p)
            self.assertEqual(p,before);self.assertEqual(r['frame_uid'],'30817')
            self.assertFalse(r['whole_event_equivalence']);self.assertFalse(r['original_native_execution'])

    def test_all_eleven_original_boolean_routes_and_untouched_identities(self):
        source_indices=(22,23,46,47,48,49,50,51,52,53,21)
        source_terms=('32208','32239','54314','57159','57855','57860','57863','57866','57869','57872','57875')
        targets=('33493','33501','60109','60114','60117','60120','60123','60126','60129','60132','60135')
        for chosen in range(11):
            args=pure_arguments(core,sparse_payload());page=list(args['new_value'])
            for i in source_indices:page[i]=False
            page[source_indices[chosen]]=True;args['new_value']=tuple(page)
            r=core.project_event_30817(**args);out=r['local_assignments'][0]['value'];expected=list(args['local_reads']['30929'])
            for j,i in enumerate(source_indices):expected[j+2]=page[i]
            self.assertEqual(out,tuple(expected));self.assertIs(r['leaf_observations'][0]['inputs']['33954'],out)
            for i in set(range(29))-set(range(2,13)):self.assertIs(out[i],args['local_reads']['30929'][i])
            self.assertEqual([(f['source_terminal_uid'],f['raw_flattened_field_index'],f['typed_position_path'],f['destination_terminal_uid'],f['destination_typed_position_path'])for f in r['field_updates']],[(s,i,(i,),t,(j+2,))for j,(s,i,t)in enumerate(zip(source_terms,source_indices,targets))])
        self.assertEqual(r['local_assignments'][0]['explicit_paramIdx'],176)

    def test_all_twenty_nine_busy_bits_and_nonaccess(self):
        for i in range(29):
            args=pure_arguments(core,minimal_payload());bits=[False]*29;bits[i]=True;args['local_reads']['30929']=tuple(bits);wire=Tripwire()
            for key in ('new_value','reference_bindings','unwired_inputs','event_time_30833','intrinsic_inputs','event_outputs'):args[key]=wire
            args['literal_inputs']['34420']=wire;args['native_boundaries']['33792']=wire
            r=core.project_event_30817(**args)
            self.assertEqual(r['selected_case_frame'],'42181');self.assertEqual(r['local_assignments'],[])
            self.assertEqual(r['source_Wait_input_value'],17);self.assertIs(r['supplied_unused_event_outputs'],wire)
            self.assertEqual([x['node_uid']for x in r['leaf_observations']],['43942'])

    def test_error_reference_unwired_and_unused_return_identities(self):
        args=pure_arguments(core,full_payload());r=core.project_event_30817(**args)
        out=args['native_boundaries']['33792']['outputs'];ref=args['reference_bindings']['31469']['native_reference']
        self.assertIs(r['leaf_observations'][0]['inputs']['33804'],ref)
        self.assertIs(r['leaf_observations'][0]['inputs']['33899'],args['unwired_inputs']['33899'])
        self.assertIs(r['leaf_observations'][0]['supplied_outputs'],out)
        self.assertIs(r['case_observations'][0]['source_input_error'],out['33926'])
        self.assertIs(r['byte_concat']['Error_source_bytes'],out['33926'].source_bytes)
        self.assertEqual(r['byte_concat']['value'],core.PREFIX_BYTES+b'\x00\xff')
        self.assertEqual(r['local_assignments'][1]['explicit_paramIdx'],184)
        self.assertEqual(r['byte_concat']['ordered_input_terminal_uids'],('37567','37575'))

    def test_hypothetical_error_selector_is_independent_of_status(self):
        for status in (False,True):
            for arm in (False,True):
                p=full_payload();p['native_boundaries']['33792']['outputs']['33926']['status']=status;p['intrinsic_inputs']['33976']=arm;p['completed_sinks']=[]
                r=core.replay_saved_sup_event_30817(p)
                self.assertEqual(r['case_observations'][0]['selected_frame'],'34401'if arm else'34174')
                self.assertEqual(len(r['local_assignments']),2 if arm else 1)
                self.assertFalse(r['native_ErrorCluster_Case_selection_qualified'])

    def test_empty_error_arm_prefix_nonaccess(self):
        args=pure_arguments(core,sparse_payload());wire=Tripwire();args['literal_inputs']={'34420':wire,'42193':wire}
        args['native_boundaries']['43942']['outputs']=wire;r=core.project_event_30817(**args)
        self.assertNotIn('byte_concat',r);self.assertEqual(r['decoded_literal_observations'],[])
        self.assertIs(r['leaf_observations'][-1]['supplied_outputs'],wire)

    def test_source_time_border_and_busy_literal_u32_are_distinct(self):
        for n in (0,1,2**32-1):
            p=minimal_payload();p['literal_inputs']['42193']=n;r=core.replay_saved_sup_event_30817(p);self.assertEqual(r['source_Wait_input_value'],n)
            p=sparse_payload();p['event_time_30833']=n;p['event_outputs']['30876']='unused source Time output';r=core.replay_saved_sup_event_30817(p)
            self.assertEqual(r['source_Wait_input_value'],n);self.assertEqual(r['event_time_source_observation']['terminal_uid'],'30833')
        for bad in (-1,2**32,True,1.0,'0',None):
            p=minimal_payload();p['literal_inputs']['42193']=bad
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)
            p=sparse_payload();p['event_time_30833']=bad
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)

    def test_exact_flat_page_types_and_inert_dbl_carriers(self):
        p=sparse_payload();r=core.replay_saved_sup_event_30817(p)
        for i in range(31,45):
            q=copy.deepcopy(p);q['new_value'][i]=(-1.0 if i%2 else 1.0)*2.0**(i-37)
            self.assertEqual(core.replay_saved_sup_event_30817(q)['local_assignments'],r['local_assignments'])
            for bad in (True,0,float('inf'),float('nan')):
                q['new_value'][i]=bad
                with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(q)
        for i in (0,21,22,23,30,45,46,53,58):
            q=copy.deepcopy(p);q['new_value'][i]=0
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(q)
        for n in (58,60):
            q=copy.deepcopy(p);q['new_value']=([False]*n)
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(q)

    def test_exact_maximal_byte_concat_and_boundary_refusals(self):
        p=full_payload();p['native_boundaries']['33792']['outputs']['33926']['source_hex']='00FF'*2048
        r=core.replay_saved_sup_event_30817(p);self.assertEqual(len(r['byte_concat']['value']['bytes_hex']),8370)
        self.assertEqual(r['byte_concat']['value']['bytes_hex'],core._hex(core.PREFIX_BYTES)+'00FF'*2048)
        for text in ('FF'*4097,'ff','0','ZZ'):
            p['native_boundaries']['33792']['outputs']['33926']['source_hex']=text
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)
        for wrong in ('','00',core._hex(core.PREFIX_BYTES)+ '00'):
            q=full_payload();q['literal_inputs']['34420']['bytes_hex']=wrong
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(q)

    def test_completion_observations_are_subsets_not_schedules(self):
        p=full_payload();p['completed_sinks']=['37686','33792','33453','43942'];r=core.replay_saved_sup_event_30817(p)
        self.assertEqual(r['completed_sinks'],p['completed_sinks']);self.assertFalse(r['completion_observations_are_feasible_trace'])
        for bad in (['33792','33792'],['33976'],['37686',0]):
            p['completed_sinks']=bad
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)
        p=sparse_payload();p['completed_sinks']=['37686']
        with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)

    def test_source_identity_false_flags_and_active_boundary_refusals(self):
        for key in ('source_id','source_version','event_uid','frame_uid'):
            p=full_payload();p[key]+='x'
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)
        for key in core.UNQUALIFIED_FLAGS:
            p=full_payload();p['unqualified_boundaries'][key]=0
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)
            p['unqualified_boundaries'][key]=True
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)
        p=full_payload();del p['unqualified_boundaries'][core.UNQUALIFIED_FLAGS[0]]
        with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)
        for key in ('33792','43942'):
            p=full_payload();del p['native_boundaries'][key]
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)
        for bad in (0,1,None,'False'):
            p=full_payload();p['intrinsic_inputs']['33976']=bad
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)

    def test_error_and_reference_carrier_domains(self):
        for bad in (True,-2**31-1,2**31,0.0):
            p=full_payload();p['native_boundaries']['33792']['outputs']['33926']['code']=bad
            with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)
        p=full_payload();p['native_boundaries']['33792']['outputs']['33926']['status']=0
        with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)
        p=full_payload();p['reference_bindings']['31469']['stored_URI_bytes']['bytes_hex']='00'
        with self.assertRaises(ValueError):core.replay_saved_sup_event_30817(p)

if __name__=='__main__':unittest.main()
