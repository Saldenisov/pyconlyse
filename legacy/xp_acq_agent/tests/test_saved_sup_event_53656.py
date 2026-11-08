import copy
import unittest
from elyse_agent import saved_sup_event_53656 as k
from sup_event_53656_fixtures import full_payload,minimal_payload,sparse_payload,pure_arguments

class Tripwire(object):
    def __getitem__(self,key):raise AssertionError('UNUSED_ACCESSED')
    def __iter__(self):raise AssertionError('UNUSED_ACCESSED')
    def __bool__(self):raise AssertionError('UNUSED_ACCESSED')

class SavedSUP53656Tests(unittest.TestCase):
    def test_three_portable_examples_and_input_preservation(self):
        for factory in(full_payload,minimal_payload,sparse_payload):
            p=factory();before=copy.deepcopy(p)
            self.assertEqual(k.replay_saved_sup_event_53656(p),k._encode(k.project_event_53656(**pure_arguments(k,p))));self.assertEqual(p,before)

    def test_original_case_and_phase_identities(self):
        for factory,frame,seq,diags,leaf in((full_payload,'76439','77973',['77981','81258','85997'],['53908','54213','81888','86028','86045']),
            (sparse_payload,'56504','56518',['56523','56742','56785'],['56584','56650','56768','56849','56870'])):
            r=k.replay_saved_sup_event_53656(factory())
            self.assertEqual((r['source_case_uid'],r['source_selector_terminal_uid'],r['selected_case_frame'],r['sequence_uid']),('76431','76455',frame,seq))
            self.assertEqual(r['source_sequence_actual_diagram_uids'],diags);self.assertEqual([x['node_uid']for x in r['leaf_observations']],leaf)
            self.assertEqual([x['sequence_phase']for x in r['leaf_observations']],[0,0,1,2,2])

    def test_independent_snapshot_copy_and_fanout(self):
        for factory,pos,rows in((full_payload,22,[('53890','53908','53934','79753'),('86012','86028','86042','86078')]),
            (sparse_payload,26,[('56568','56584','56647','56550'),('56833','56849','56867','56817')])):
            a=pure_arguments(k,factory());r=k.project_event_53656(**a);calls={x['node_uid']:x for x in r['leaf_observations']}
            for j,(read,writer,face,literal)in enumerate(rows):
                value=r['local_assignments'][j]['value'];self.assertIs(value,calls[writer]['inputs'][face]);self.assertEqual(value[pos],a['literal_inputs'][literal])
                for i in range(40):
                    if i!=pos:self.assertIs(value[i],a['local_reads'][read][i])
            self.assertEqual([x['raw_flattened_field_index']for x in r['field_updates']],[pos,pos]);self.assertEqual(len(r['local_assignments']),2)

    def test_error_reference_and_unwired_identity(self):
        for factory,rows in((full_payload,[('53908','53930','54213','70702','53910','54139'),('86028','86039','86045','86075','86030','86088')]),
            (sparse_payload,[('56584','56644','56650','56706','56586','56529'),('56849','56864','56870','56900','56851','56792')])):
            a=pure_arguments(k,factory());r=k.project_event_53656(**a);calls={x['node_uid']:x for x in r['leaf_observations']}
            for w,e,h,t,rf,ref in rows:
                self.assertIs(calls[h]['inputs'][t],a['native_boundaries'][w]['outputs'][e]);self.assertIs(calls[w]['inputs'][rf],a['reference_bindings'][ref]['native_reference'])
            for face,value in a['unwired_inputs'].items():
                owner=next(u for u in calls if face in k.INPUT_ORDER[u]);self.assertIs(calls[owner]['inputs'][face],value)

    def test_wait_is_supplied_observation_with_exact_saved_input(self):
        for factory,node,face in((full_payload,'81888','81908'),(sparse_payload,'56768','56779')):
            r=k.replay_saved_sup_event_53656(factory());row=next(x for x in r['leaf_observations']if x['node_uid']==node)
            self.assertEqual(row['inputs'],{face:int('000003E8',16)});self.assertIs(row['callee_or_native_executed'],False)

    def test_literal_hypotheses_both_boolean_pairs(self):
        for factory in(full_payload,sparse_payload):
            for first in(False,True):
                for last in(False,True):
                    p=factory();ids=k._keys('literals',k._arm(p['new_value']));p['literal_inputs']=dict(zip(ids,(first,last)))
                    r=k.replay_saved_sup_event_53656(p);self.assertEqual([x['value'][22 if p['new_value']==0 else 26]for x in r['local_assignments']],[first,last])
                    self.assertTrue(all(x['decoded_literal_is_hypothetical']for x in r['field_updates']))

    def test_unselected_mapping_entries_and_unused_outputs_are_not_read(self):
        trap=Tripwire()
        for factory in(full_payload,sparse_payload):
            a=pure_arguments(k,factory());arm=k._arm(a['new_value']);other=k._arm(1-a['new_value'])
            for param,kind in(('local_reads','reads'),('literal_inputs','literals'),('reference_bindings','refs'),('native_boundaries','leaves'),('unwired_inputs','unwired')):
                for uid in k._keys(kind,other):a[param][uid]=trap
            for uid in(arm['first']['handler'],arm['wait']['node'],arm['last']['handler']):a['native_boundaries'][uid]['outputs']=trap
            a['event_outputs']=trap;r=k.project_event_53656(**a);self.assertIs(r['supplied_unused_event_outputs'],trap)
            for row in r['leaf_observations']:
                if row['node_uid']in(arm['first']['handler'],arm['wait']['node'],arm['last']['handler']):self.assertIs(row['supplied_outputs'],trap)

    def test_case_default_and_non_u16_refusals(self):
        for v in(False,True,None,0.0,1.0,'0',-1,2,65535,65536):
            p=full_payload();p['new_value']=v;self.assertRaises(ValueError,k.replay_saved_sup_event_53656,p)

    def test_missing_active_boundaries_and_wrong_types(self):
        for param in('local_reads','literal_inputs','reference_bindings','native_boundaries','unwired_inputs'):
            p=full_payload();p[param].pop(next(iter(p[param])));self.assertRaises(ValueError,k.replay_saved_sup_event_53656,p)
        p=full_payload();p['local_reads']['53890'][0]=0;self.assertRaises(ValueError,k.replay_saved_sup_event_53656,p)
        p=full_payload();p['literal_inputs']['79753']=1;self.assertRaises(ValueError,k.replay_saved_sup_event_53656,p)

    def test_completion_reports_are_not_feasible_trace(self):
        p=full_payload();p['completed_sinks']=['86045'];r=k.replay_saved_sup_event_53656(p)
        self.assertEqual(r['completed_sinks'],['86045']);self.assertIs(r['completion_observations_are_feasible_trace'],False)
        for reports in(['86045','86045'],['56650'],[0]):
            p['completed_sinks']=reports;self.assertRaises(ValueError,k.replay_saved_sup_event_53656,p)

    def test_entity_policy_and_raw_byte_domains(self):
        for key in('source_id','source_version','event_uid','frame_uid'):
            p=full_payload();p[key]='wrong';self.assertRaises(ValueError,k.replay_saved_sup_event_53656,p)
        for flag in k.UNQUALIFIED_FLAGS:
            p=full_payload();p['unqualified_boundaries'][flag]=True;self.assertRaises(ValueError,k.replay_saved_sup_event_53656,p)
        for raw in('fF','F','GG','00'*4097):
            p=full_payload();p['native_boundaries']['53908']['outputs']['53930']['source_hex']=raw;self.assertRaises(ValueError,k.replay_saved_sup_event_53656,p)

    def test_exact_byte_limit_and_json_roundtrip(self):
        p=full_payload();p['native_boundaries']['53908']['outputs']['53930']['source_hex']='00FF'*2048
        r=k.replay_saved_sup_event_53656(p);self.assertEqual(next(x for x in r['leaf_observations']if x['node_uid']=='54213')['inputs']['70702']['source_hex'],'00FF'*2048)

if __name__=='__main__':unittest.main()
