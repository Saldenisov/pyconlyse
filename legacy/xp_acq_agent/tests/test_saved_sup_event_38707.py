"""Fresh G70 portable supplied-data cases; no source/native execution."""
import copy,math,unittest
from fractions import Fraction
from elyse_agent import saved_sup_event_38707 as k
from legacy.xp_acq_agent.tests import sup_event_38707_fixtures as f

class Tripwire(object):
    def __bool__(self):raise AssertionError('Unused value accessed')
    def __iter__(self):raise AssertionError('Unused value accessed')
    def __float__(self):raise AssertionError('Unused value accessed')

class SavedSUP38707Tests(unittest.TestCase):
    def test_eight_source_arithmetic_arms(self):
        for mask in (1,2,4,8,16,32,64,128):
            p=f.payload(mask);args=f.pure_inputs(p);r=k.project_event_38707(*args);a=k.ARM_ROWS[mask]
            value=args[0].new_value[a['page_position']];step=Fraction.from_float(k.stored_double(a['step_hex']));expected=Fraction.from_float(value)-step if mask in(1,2,16,32)else Fraction.from_float(value)+step
            self.assertEqual(r.arithmetic_trace[0]['result'],float(expected));self.assertIs(r.Error_result,args[2].writers[a['writer_uid']].error_out)
            self.assertEqual([o.node_uid for o in r.local_assignments],[a['carrier_write_uid'],a['page_write_uid'],'41201']);self.assertEqual(r.request_mask,mask)
            self.assertEqual(r.selected_frames[-2],(a['sequence_uid'],a['sequence_diagram'],0));self.assertEqual(r.leaf_observations[1].inputs[a['wait_input_face']],17)
            self.assertEqual(r.error_message,r.error_prefix+r.Error_result.source_bytes)
    def test_dps_no_request_and_both_property_cases(self):
        p=f.payload(0,stop=True,start=True);p['event_returns']['38726']['38743'][9:12]=[True,False,True];r=f.project(p)
        updated=r.local_assignments[0].data
        self.assertEqual(tuple(updated[i]for i in(15,17,16,18,19)),(False,True,True,True,True));self.assertEqual(len(r.leaf_observations),9)
        self.assertEqual([o.inputs[k.PROPERTY_PORTS[o.node_uid]['4']]for o in r.leaf_observations[1:]], [1]*4+[23]*4)
        self.assertEqual(r.local_assignments[0].node_uid,'38967');self.assertIs(r.local_assignments[0].data,r.leaf_observations[0].inputs['39003'])
    def test_busy_no_request_supplied_literal_and_max_bytes(self):
        p=f.payload(0,busy=True);p['literal_inputs']['39257']='00FF'*2048;p['literal_inputs']['39271']['source_hex']='FF00'*2048;r=k.replay_saved_sup_event_38707(p)
        self.assertEqual(len(r['error_message_hex']),16384);self.assertEqual(r['error_message_hex'][:4],'00FF');self.assertEqual(len(r['local_assignments']),1);self.assertEqual(r['leaf_observations'],[])
        p['literal_inputs']['39257']+='00';self.assertRaises((ValueError,TypeError),k.replay_saved_sup_event_38707,p)
    def test_busy_does_not_suppress_saved_request_arm(self):
        r=f.project(f.payload(4,busy=True));self.assertTrue(r.DPS_busy);self.assertTrue(r.request_any);self.assertEqual(r.arithmetic_trace[0]['arithmetic_uid'],'61317')
    def test_raw_absent_i_not_zero(self):
        for mask in(1,2,4,8):
            a=k.ARM_ROWS[mask];r=k.replay_saved_sup_event_38707(f.payload(mask));row=next(x for x in r['field_projections']if x['terminal_uid']==a['carrier_face'])
            self.assertIsNone(row['raw_flattened_field_index']);self.assertEqual(row['descriptor_projection_ordinal'],0);self.assertEqual(row['typed_position_path'],[0])
    def test_inactive_boundaries_are_opaque(self):
        args=f.pure_inputs(f.payload(1));opaque=Tripwire();active=k.ARM_ROWS[1]
        for uid in k.READ_UIDS:
            if uid not in('38750',active['carrier_read_uid']):args[1][uid]=opaque
        for mapping,active_uid in[(args[2].writers,active['writer_uid']),(args[2].waits,active['wait_uid'])]:
            for uid in mapping:
                if uid!=active_uid:mapping[uid]=opaque
        for uid in args[2].properties:args[2].properties[uid]=opaque
        for uid in args[4]:
            if uid not in(active['reference_literal_uid'],active['reset_literal_uid']):args[4][uid]=opaque
        args[0]=k.EventDataReturn(opaque,opaque,opaque,opaque,args[0].new_value,opaque);r=k.project_event_38707(*args);self.assertIs(r.event_return.old_value,opaque)
    def test_composite_and_range_refusals(self):
        for mask in(3,5,6,7,9,15,31,63,127,129,255):self.assertRaises(ValueError,f.project,f.payload(mask))
        for mask,value in[(1,7.0),(1,21.0),(2,float('nan')),(4,float('inf')),(16,205.0),(128,395.0)]:
            p=f.payload(mask);p['event_returns']['38726']['38743'][k.ARM_ROWS[mask]['page_position']]=value;self.assertRaises(ValueError,f.project,p)
    def test_carrier_and_page_epoch_identity(self):
        args=f.pure_inputs(f.payload(128));a=k.ARM_ROWS[128];before=args[1][a['carrier_read_uid']];new=args[0].new_value;r=k.project_event_38707(*args);out=r.local_assignments[0].data
        self.assertIsNot(out,before);self.assertEqual(out[6],305.0)
        for i in range(10):
            if i!=6:self.assertIs(out[i],before[i])
        updated=r.local_assignments[1].data
        for i in range(28):
            if i not in k.REQUEST_POSITIONS+(18,):self.assertIs(updated[i],new[i])
        self.assertIs(out,r.leaf_observations[0].inputs[k.WRITER_PORTS[a['writer_uid']]['4']])
    def test_supplied_error_selector_and_completion_report(self):
        p=f.payload(1,error_selector=False);r=f.project(p);self.assertTrue(r.Error_result.status);self.assertIsNone(r.error_message)
        p['completed_sinks']=['41201','39649'];p['intrinsic_outputs']['41026']=True;r=f.project(p);self.assertEqual(r.completed_sinks,('41201','39649'))
        p['completed_sinks']=['41480','41480'];self.assertRaises(ValueError,f.project,p)
        p['completed_sinks']=['38989'];self.assertRaises(ValueError,f.project,p)
    def test_json_source_and_domains(self):
        p=f.payload();r=k.replay_saved_sup_event_38707(p);self.assertEqual(r['frame_uid'],'38707');self.assertFalse(r['whole_event_runtime_equivalence'])
        for key,v in [('source_version','0'*64),('frame_uid','33463'),('event_uid','5910')]:
            q=copy.deepcopy(p);q[key]=v;self.assertRaises(ValueError,k.replay_saved_sup_event_38707,q)
        q=copy.deepcopy(p);q['intrinsic_outputs']['41026']=1;self.assertRaises(TypeError,k.replay_saved_sup_event_38707,q)
        q=copy.deepcopy(p);q['border_inputs']['38714']=True;self.assertRaises(TypeError,k.replay_saved_sup_event_38707,q)
    def test_active_storage_and_reference_boundaries(self):
        p=f.payload(0,start=True);p['literal_inputs']['84932']=256;self.assertRaises(TypeError,f.project,p)
        p=f.payload();p['literal_inputs']['41470']=1;self.assertRaises(TypeError,f.project,p)
        p=f.payload(0,busy=True);p['literal_inputs']['39271']['code']=2**31;self.assertRaises(TypeError,f.project,p)
        p=f.payload();p['native_returns']['39649']['39698']['source_hex']='ff';self.assertRaises(ValueError,k.replay_saved_sup_event_38707,p)
    def test_inactive_dbl_native_returns_and_event_faces(self):
        p=f.payload(0);args=f.pure_inputs(p);page=list(args[0].new_value);page[12]=float('nan');args[0]=args[0]._replace(new_value=tuple(page));r=k.project_event_38707(*args);self.assertEqual(r.request_mask,0)
        p['event_returns']['38726']['38743'][12]=float('nan');self.assertRaises(ValueError,k.replay_saved_sup_event_38707,p)

if __name__=='__main__':unittest.main()
