"""Portable new G71 bounded tests; fixture contains literal source-shaped data."""
import copy,unittest,math
from fractions import Fraction
from elyse_agent import saved_sup_event_5847 as m
from sup_event_5847_fixtures import make_payload,pure_arguments
# Independent expectation table, saved exact literal values and source direction.
STEPS={128:((1.,10.),(5.,50.),(.1,1.),(.1,1.)),256:((.1,1.),(1.,5.),(.01,.1),(.01,.1)),512:((.1,1.),(1.,5.),(.01,.1),(.01,.1)),1024:((1.,10.),(5.,50.),(.1,1.),(.1,1.))}
def family(i):return 0 if i==1 else 1 if i==2 else 2 if i in(0,7,8)else 3
class G71BodyTests(unittest.TestCase):
    def test_all_saved_masks_indices_selectors(self):
        for mask in(0,1,16,128,256,512,1024):
            for i in range(11):
                for b in(False,True):
                    p=make_payload(mask,i,b)
                    if mask>=128 and i in(1,2):p['native_boundaries']['65015']['outputs']['65045'][5]=60. if i==1 else 180.
                    a=pure_arguments(m,p);o=m.project_event_5847(**a);j=m.replay_saved_sup_event_5847(p)
                    self.assertEqual(o.loop_count,11);self.assertEqual(o.maximum_mask,mask);self.assertEqual(o.maximum_index,i);self.assertEqual(tuple(j['masks']),o.masks)
                    current=a['native_boundaries']['65015']['outputs']['65045'];expected=current[5]
                    if mask>=128:
                        step=STEPS[mask][family(i)][int(b)];expected=float(Fraction(current[5])+(Fraction(step)if mask in(512,1024)else-Fraction(step)))
                        self.assertEqual(o.arithmetic_trace[0]['result'],expected);self.assertEqual(o.arithmetic_trace[0]['source_slot1'],step);self.assertEqual(o.arithmetic_trace[0]['source_slot2'],current[5]);self.assertFalse(o.arithmetic_trace[0]['unused_Boolean_evaluated'])
                    self.assertEqual(o.property_value[5],expected);self.assertEqual(j['property_value'][5],expected);self.assertEqual(o.property_value[:5],current[:5]);self.assertIs(o.property_value[6],current[6]);self.assertEqual(o.property_value[7:],(False,)*4)
                    self.assertEqual(len(o.local_assignments),3 if mask>=128 else 0);self.assertEqual(len(o.leaf_observations),17)
    def test_fresh_carrier_epochs_and_field_identity(self):
        a=pure_arguments(m,make_payload());o=m.project_event_5847(**a);writes={x.node_uid:x.data for x in o.local_assignments};v=a['local_reads']['15459']
        for target,read,updates in [('6122','15529',{0:3,1:4,2:5,3:6,4:9,5:10}),('8562','9302',{8:0,5:1,0:7,1:8}),('7702','15570',{5:2})]:
            for j in range(10):self.assertIs(writes[target][j],v[updates[j]][5]if j in updates else a['local_reads'][read][j])
        leaves={x.node_uid:x for x in o.leaf_observations}
        for w,read,dataface in [('12969','8032','13013'),('13145','9134','13269'),('13838','9426','13919'),('13981','10599','14001')]:self.assertIs(leaves[w].inputs[dataface],a['local_reads'][read])
        self.assertIs(leaves['8025'].inputs['8039'],o.property_value);self.assertIs(leaves['16572'].inputs['42572'],a['native_boundaries']['8025']['outputs']['8036'])
        self.assertIs(leaves['7957'].inputs['7959'],a['native_boundaries']['7985']['outputs']['7987']);self.assertIs(leaves['8048'].inputs['8050'],a['native_boundaries']['7957']['outputs']['7971'][3])
        self.assertIs(o.old_value,a['old_value']);self.assertIs(o.new_value,a['new_value']);self.assertIs(o.event_outputs,a['event_outputs'])
    def test_raw_absence_preserved(self):
        o=m.project_event_5847(**pure_arguments(m,make_payload()));z={(x.node_uid,x.terminal_uid):x for x in o.field_projections}
        for key in(('8096','8155'),('8174','8224'),('7543','14067'),('8553','14331')):
            self.assertIsNone(z[key].raw_flattened_field_index);self.assertEqual(z[key].typed_position_path,(0,))
    def test_ties_require_hypothetical_constrained_index(self):
        p=make_payload(0,4);p['max_index_7844']=None
        with self.assertRaises(ValueError):m.replay_saved_sup_event_5847(p)
        p['max_index_7844']=4;self.assertIn('hypothetical',m.replay_saved_sup_event_5847(p)['maximum_index_scope'])
        p=make_payload(16,3);p['new_value'][7][4]=True
        with self.assertRaises(ValueError):m.replay_saved_sup_event_5847(p)
        p['max_index_7844']=7;self.assertEqual(m.replay_saved_sup_event_5847(p)['maximum_index'],7)
        p['max_index_7844']=1
        with self.assertRaises(ValueError):m.replay_saved_sup_event_5847(p)
    def test_composite_and_unmatched_refusals(self):
        for mask in(17,129,257,513,1025,384,768,1920,1937):
            with self.assertRaises(ValueError):m.replay_saved_sup_event_5847(make_payload(mask))
    def test_strict_range_endpoints_outside_nonfinite(self):
        for v in(-5.1,4.9,5.,-6.,float('nan'),float('inf')):
            p=make_payload(1024,3);p['native_boundaries']['65015']['outputs']['65045'][5]=v
            with self.assertRaises((ValueError,TypeError)):m.replay_saved_sup_event_5847(p)
    def test_inactive_local_and_literal_nonaccess(self):
        class Opaque:
            def __iter__(self):raise AssertionError('unselected access')
            def __bool__(self):raise AssertionError('unselected bool')
        a=pure_arguments(m,make_payload(16,3))
        for u in('15459','15529','9302','15570'):a['local_reads'][u]=Opaque()
        for u in('10997','11174','15347','16904','17030','7607','8620','8879'):a['literal_inputs'][u]=Opaque()
        a['event_outputs']=Opaque();m.project_event_5847(**a)
    def test_unused_native_outputs_nonaccess(self):
        class Opaque:
            def __iter__(self):raise AssertionError('unused output')
            def __bool__(self):raise AssertionError('unused output')
        a=pure_arguments(m,make_payload())
        for u,l in m.NATIVE_LEAVES.items():
            for t in l['outputs']:
                if not t['consumed']:a['native_boundaries'][u]['outputs'][t['uid']]=Opaque()
        m.project_event_5847(**a)
    def test_unmatched_shape_and_numeric_types(self):
        for path,value in [(('new_value',),[]),(('old_value',0,5),0),(('old_value',0,0),1),(('max_index_7844',),True),(('native_boundaries','7957','outputs','7971'),[]),(('native_boundaries','65015','outputs','65045'),[])]:
            p=make_payload();c=p
            for k in path[:-1]:c=c[k]
            c[path[-1]]=value
            with self.assertRaises((ValueError,TypeError)):m.replay_saved_sup_event_5847(p)
    def test_source_identity_and_json_refusals(self):
        for key in('source_id','source_version','event_uid','frame_uid'):
            p=make_payload();p[key]='wrong'
            with self.assertRaises(ValueError):m.replay_saved_sup_event_5847(p)
        p=make_payload();p['extra']=1
        with self.assertRaises(ValueError):m.replay_saved_sup_event_5847(p)
        p=make_payload();p['native_boundaries']['7985']['outputs']['7990']['source_hex']='ff'
        with self.assertRaises(ValueError):m.replay_saved_sup_event_5847(p)
    def test_completion_reports_not_source_traces(self):
        p=make_payload();p['completed_sinks']=['8654','12969'];o=m.replay_saved_sup_event_5847(p);self.assertEqual(o['completed_sinks'],['8654','12969']);self.assertFalse(o['boundary_scope']['completion_observations_are_feasible_trace'])
        for x in(["6122","6122"],["bad"]):
            p=make_payload();p['completed_sinks']=x
            with self.assertRaises(ValueError):m.replay_saved_sup_event_5847(p)
    def test_exact_supplied_error_bytes_and_bound(self):
        p=make_payload();p['native_boundaries']['12969']['outputs']['13010']['source_hex']='00FF'*2048;o=m.replay_saved_sup_event_5847(p);self.assertEqual(next(x for x in o['leaf_observations']if x['node_uid']=='8654')['inputs']['9120']['source_hex'],'00FF'*2048)
        p['native_boundaries']['12969']['outputs']['13010']['source_hex']+='00'
        with self.assertRaises((ValueError,TypeError)):m.replay_saved_sup_event_5847(p)
if __name__=='__main__':unittest.main()
