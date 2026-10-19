import copy,math,struct,unittest
from fractions import Fraction
from elyse_agent import saved_sup_event_33463 as k
from legacy.xp_acq_agent.tests import sup_event_33463_fixtures as f
class SavedSup33463(unittest.TestCase):
    def replay(self,p):return k.replay_saved_sup_event_33463(p)
    def test_all_nine_masks_and_source_array_loop(self):
        for i in range(9):
            p=f.payload(128,i);r=self.replay(p)
            self.assertEqual((r['loop_iteration_count'],r['selected_index'],r['max_mask']),(9,i,128));self.assertEqual(r['masks'],[128 if j==i else 0 for j in range(9)])
    def test_select_slot_and_fraction_arithmetic(self):
        for mask in(128,256,512,1024):
            for index in range(9):
                for selector in(False,True):
                    p=f.payload(mask,index,selector,0.5);r=self.replay(p);row=k.ARITH_ROWS[(mask,0 if index in(0,1,2,3,6)else 1)]
                    step=struct.unpack('>d',bytes.fromhex(row[7]if selector else row[6]))[0]
                    q=Fraction.from_float(0.5)+(Fraction.from_float(step)if mask>=512 else -Fraction.from_float(step))
                    self.assertEqual(r['updated_cluster'][5],float(q));self.assertEqual(r['numeric_trace'][0]['selected_step'],step)
    def test_phase2_explicit_reads_and_fields(self):
        p=f.payload();r=self.replay(p);assign={a['node_uid']:a['data']for a in r['local_assignments']}
        c6=list(p['local_reads']['46632']);c7=list(p['local_reads']['46671']);v=p['local_reads']['46585']
        for target,src in[(6,4),(7,5),(9,8),(8,7)]:c6[target]=v[src][5]
        for target,src in[(9,6),(6,0),(7,1),(3,2),(4,3)]:c7[target]=v[src][5]
        self.assertEqual(assign['46665'],c6);self.assertEqual(assign['46698'],c7)
        writer={a['node_uid']:a for a in r['leaf_observations']};self.assertEqual(writer['47022']['inputs']['47036'],p['local_reads']['46864']);self.assertNotEqual(writer['47022']['inputs']['47036'],c6)
    def test_nonrequest_phase2_nonaccess(self):
        args=list(f.direct(f.minimum_unique_payload()));opaque=object();args[1].update({u:opaque for u in('46585','46632','46671')});args[3]=k.IntrinsicBoundaries(opaque,False)
        r=k.project_event_33463(*args);self.assertEqual(len(r.local_reads),4);self.assertEqual(r.local_assignments,());self.assertEqual(r.max_mask,1)
        self.assertEqual(self.replay(f.sparse_payload())['max_mask'],1)
    def test_max_unique_tie_and_zero_intrinsic(self):
        p=f.payload(0,error_selector=False)
        with self.assertRaises(ValueError):self.replay(p)
        p['intrinsic_outputs']['33835']=5;r=self.replay(p);self.assertTrue(r['max_index_supplied']);self.assertEqual(r['selected_index'],5)
        p['intrinsic_outputs']['33835']=True
        with self.assertRaises(ValueError):self.replay(p)
        p=f.payload();p['event_returns']['33480']['33497'][1][7]=True
        with self.assertRaises(ValueError):self.replay(p)
        p['intrinsic_outputs']['33835']=1;self.assertEqual(self.replay(p)['selected_index'],1)
    def test_bounds_composites_and_nonfinite(self):
        for mask in(17,129,257,384,2047):
            with self.assertRaises(ValueError):self.replay(f.payload(mask))
        for current in(16.1,17.0,-15.9,-16.0):
            with self.assertRaises(ValueError):self.replay(f.payload(128,0,False,current))
        for value in(float('nan'),float('inf'),-float('inf')):
            p=f.payload();p['event_returns']['33480']['33494'][0][5]=value
            with self.assertRaises(ValueError):self.replay(p)
    def test_absent_indices_explicit_descriptor_paths(self):
        r=self.replay(f.payload());rows={a['terminal_uid']:a for a in r['field_projections']}
        for uid in('34033','34061'):
            self.assertIsNone(rows[uid]['raw_flattened_field_index']);self.assertEqual(rows[uid]['descriptor_projection_ordinal'],0);self.assertEqual(rows[uid]['typed_position_path'],[0])
        self.assertEqual(rows['46598']['raw_flattened_field_index'],54);self.assertEqual(rows['46598']['typed_position_path'],[4,5])
    def test_original_error_prefix_bytes_and_hypothetical_selector(self):
        p=f.payload();r=self.replay(p);self.assertEqual(r['error_message_hex'],k.hex_bytes(k.ERROR_PREFIX)+p['native_returns']['33935']['33946']['source_hex'])
        p['native_returns']['33935']['33946']['status']=False;self.assertEqual(self.replay(p)['error_message_hex'],r['error_message_hex'])
        p['intrinsic_outputs']['48544']=False;p['completed_sinks'].remove('48604');self.assertIsNone(self.replay(p)['error_message_hex'])
        p['literal_inputs']['46410']=True;self.assertEqual(self.replay(p)['updated_cluster'][7:],[True]*4)
        p=f.payload();p['native_returns']['33935']['33946']['source_hex']='00FF'*2048
        self.assertEqual(self.replay(p)['error_message_hex'],k.hex_bytes(k.ERROR_PREFIX)+'00FF'*2048)
    def test_source_edges_error_reference_and_identity(self):
        args=f.direct(f.payload());r=k.project_event_33463(*args);leaves={a.node_uid:a for a in r.leaf_observations}
        self.assertIs(leaves['33905'].inputs['33916'],args[2].control_reference);self.assertIs(leaves['33859'].inputs['33881'],args[2].cast.error_out)
        self.assertIs(leaves['33935'].inputs['33943'],args[2].variant.error_out);self.assertIs(leaves['33935'].inputs['33949'],r.updated_cluster)
        for row in k.WRITER_ROWS:
            self.assertIs(leaves[row[1]].inputs[row[7]],args[1][row[0]]);self.assertIs(leaves[row[8]].inputs[row[10]],args[2].writers[row[1]].error_out)
            self.assertIs(leaves[row[1]].inputs[row[3]],args[4][row[2]])
    def test_completion_observations_do_not_gate_fanout(self):
        p=f.payload();p['completed_sinks']=['46870'];r=self.replay(p);self.assertEqual(r['completed_sinks'],['46870']);self.assertEqual(len(r['leaf_observations']),16)
        for values in(['46870','46870'],['foreign'],['46698']):
            q=f.minimum_unique_payload();q['completed_sinks']=values
            with self.assertRaises(ValueError):self.replay(q)
    def test_exact_json_shape_and_type_refusals(self):
        p=f.payload()
        for key,value in[('source_version','bad'),('frame_uid','18780'),('event_uid',5909)]:
            q=copy.deepcopy(p);q[key]=value
            with self.assertRaises(ValueError):self.replay(q)
        q=copy.deepcopy(p);q['extra']=0
        with self.assertRaises(ValueError):self.replay(q)
        q=copy.deepcopy(p);q['native_returns']['33935']['33946']['source_hex']='ff'
        with self.assertRaises(ValueError):self.replay(q)
        q=copy.deepcopy(p);q['intrinsic_outputs']['48544']=0
        with self.assertRaises(TypeError):self.replay(q)
        q=copy.deepcopy(p);q['literal_inputs']['46410']=0
        with self.assertRaises(TypeError):self.replay(q)
    def test_inventory_null_types_and_all_native_flags(self):
        r=self.replay(f.payload());self.assertEqual(r['null_model_ports_preserved'],['28333','33657','33724']);self.assertFalse(r['null_ports_are_caller_inputs']);self.assertFalse(r['ctlRefConst33897_is_gRef_bank_read'])
        for key in('native_execution','whole_VI_equivalence','native_float_bitwise_equivalence','native_tie_index_policy_qualified','native_storage_serializer_qualified','native_variant_conversion_qualified','source_schedule_qualified'):self.assertIs(r[key],False)
if __name__=='__main__':unittest.main()
