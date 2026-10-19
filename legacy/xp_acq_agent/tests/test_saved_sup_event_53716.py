import copy
from decimal import Decimal
from fractions import Fraction
import unittest

from elyse_agent import saved_sup_event_53716 as k
from sup_event_53716_fixtures import full_payload


def fixture(mask,base=None):
    p=full_payload();p['completed_sinks']=None
    n=p['event_returns']['53735']['53762']
    for i in k.REQUEST_PATHS:n[i]=False
    for j,i in enumerate(k.REQUEST_PATHS):n[i]=bool(mask&(1<<j))
    if base is not None:
        n[5 if mask<=8 else 17]=base
    return p


class Event53716Tests(unittest.TestCase):
    def test_full_carrier_fault_boundary(self):
        p=full_payload();o=k.replay_saved_sup_event_53716(p)
        self.assertEqual(o['request_mask'],4);self.assertEqual(o['writer_call']['data'][4],11.0)
        self.assertEqual(o['local_assignments']['53024']['data'][5],11.0)
        self.assertEqual(o['returned_error']['code'],-17)
        self.assertFalse(o['writer_success_gates_local_assignment'])
        self.assertEqual(o['completed_sinks'],['53024','52858'])
        self.assertEqual(o['error_text_hex'],o['error_prefix_hex']+'00FF')

    def test_eight_independent_fraction_expectations(self):
        for mask in(1,2,4,8,16,32,64,128):
            base=10.0 if mask<=8 else 20.0;p=fixture(mask,base);o=k.replay_saved_sup_event_53716(p)
            sign=-1 if mask in(1,2,16,32)else 1
            delta=5 if mask==1 else 10 if mask in(16,128)else 1
            expected=float(Fraction(int(base))+sign*Fraction(delta))
            self.assertEqual(o['writer_call']['data'][4 if mask<=8 else 3],expected)
            r=list(o['range_by_uid'].values())[0];self.assertEqual(r['value'],expected)
            self.assertFalse(r['unused_boolean_output_evaluated'])
            a=list(o['arithmetic_by_uid'].values())[0]
            self.assertEqual(a['input_slots'],{'1':float(delta),'2':base})
            self.assertEqual(len(o['local_reads']),2)
            data=o['local_assignments'][k.BRANCHES[mask]['pagewrite']]['data']
            for i in k.REQUEST_PATHS:self.assertIs(data[i],False)

    def test_decimal_exact_binary_quarters(self):
        for mask in(1,2,4,8,16,32,64,128):
            p=fixture(mask,10.25 if mask<=8 else 20.25);o=k.replay_saved_sup_event_53716(p)
            sign=-1 if mask in(1,2,16,32)else 1;delta=5 if mask==1 else 10 if mask in(16,128)else 1
            expected=Decimal('10.25'if mask<=8 else'20.25')+Decimal(sign*delta)
            self.assertEqual(Decimal.from_float(list(o['range_by_uid'].values())[0]['value']),expected)

    def test_endpoint_outside_and_nonfinite_refusals(self):
        for base in(-1.0,19.0,20.0,100.0,float('nan'),float('inf')):
            with self.assertRaises((ValueError,TypeError)):k.replay_saved_sup_event_53716(fixture(4,base))
        for lower in(11.0,12.0,20.0,float('nan'),1,True):
            p=fixture(4,10.0);p['literal_inputs']['58402']=lower
            with self.assertRaises((ValueError,TypeError)):k.replay_saved_sup_event_53716(p)

    def test_composite_masks_refused(self):
        for mask in(3,5,6,7,9,15,17,31,63,127,255):
            with self.assertRaises(ValueError):k.replay_saved_sup_event_53716(fixture(mask))

    def test_no_request_false_dps_branch(self):
        p=fixture(0);p['event_returns']['53735']['53762'][7]=True
        o=k.replay_saved_sup_event_53716(p)
        self.assertEqual(o['writer_call']['node_uid'],'55466');self.assertIsNone(o['wait_call'])
        self.assertIs(o['writer_call']['data'][13],True);self.assertIs(o['writer_call']['data'][14],False)
        self.assertEqual(len(o['local_reads']),1);self.assertEqual(o['supplied_literal_observations'],{})

    def test_dps_any_no_request_supplied_empty_literal(self):
        p=fixture(0);p['local_reads']['53769'][0]=True;p['literal_inputs']['55804']='00FF'
        o=k.replay_saved_sup_event_53716(p)
        self.assertIsNone(o['writer_call']);self.assertIsNone(o['wait_call'])
        self.assertEqual(o['error_prefix_hex'],'00FF');self.assertEqual(o['error_text_hex'],'00FFFF00')
        self.assertTrue(o['returned_error']['status']);self.assertEqual(o['returned_error']['code'],-29);self.assertFalse(o['native_literal_storage_decode_qualified'])

    def test_identity_and_unselected_nonaccess_direct(self):
        sentinel=object();n=list(full_payload()['event_returns']['53735']['53762']);n[5]=10.0
        c8=tuple(float(i+300)for i in range(10));dps=(False,)*29
        reads={u:sentinel for u in k.READ_UIDS};reads['53769']=dps;reads['52907']=c8
        writers={u:sentinel for u in k.WRITER_UIDS};writers['52858']=k.WriterBoundary(sentinel,sentinel,k.WriterReturn(sentinel,k.ErrorValue(False,5,b'\x00\xff')))
        waits={u:sentinel for u in k.WAIT_UIDS};waits['52966']=k.WaitReturn(sentinel)
        borders={u:sentinel for u in k.BORDER_UIDS};borders['53723']=0
        ev=k.EventDataReturn(sentinel,sentinel,sentinel,sentinel,tuple(n),sentinel)
        r=k.project_event_53716(ev,reads,k.NativeBoundaries(borders,writers,waits),True,{'58402':0.0,'55804':sentinel,'55821':sentinel},('52858',))
        self.assertIs(r.event_return,ev);self.assertIs(r.writer_call.boundary.reference_in,sentinel)
        self.assertIs(r.wait_call.returned_timer,sentinel);self.assertIs(r.local_reads[0].data,dps)
        self.assertIs(r.local_reads[1].data,c8)
        for i in range(10):
            if i!=4:self.assertIs(r.writer_call.data[i],c8[i])
        for i,v in enumerate(ev.new_value):
            if i not in k.REQUEST_PATHS and i!=5:self.assertIs(r.local_assignments[0].data[i],v)

    def test_unused_literal_nonaccess(self):
        p=fixture(16,20.0);p['literal_inputs']={'58402':{'unknown_storage':True},'55804':None,'55821':None}
        o=k.replay_saved_sup_event_53716(p);self.assertEqual(o['supplied_literal_observations'],{})
        p=fixture(0);p['literal_inputs']={'58402':None,'55804':{'unknown_storage':True},'55821':{'unknown_storage':True}}
        o=k.replay_saved_sup_event_53716(p);self.assertEqual(o['supplied_literal_observations'],{})

    def test_strict_source_and_type_guards(self):
        for key in('source_id','source_version','event_uid','frame_uid'):
            p=full_payload();p[key]+='x'
            with self.assertRaises(ValueError):k.replay_saved_sup_event_53716(p)
        for key in('literal_inputs','event_returns','local_reads','native_returns'):
            p=full_payload();p[key]['unexpected']=None
            with self.assertRaises(ValueError):k.replay_saved_sup_event_53716(p)
        p=full_payload();p['event_returns']['53735']['53762'][3]=1
        with self.assertRaises(TypeError):k.replay_saved_sup_event_53716(p)

    def test_byte_concat_and_selector_hypotheses(self):
        self.assertEqual(k.concatenate_error_bytes(b'\xff\x00',b'\x00\xff'),b'\xff\x00\x00\xff')
        for selector in(False,True):
            p=full_payload();p['error_case_selector']=selector;o=k.replay_saved_sup_event_53716(p)
            self.assertEqual('58262'in o['local_assignments'],selector)
            self.assertFalse(o['native_error_selector_projection_qualified'])
        p=full_payload();p['error_case_selector']=1
        with self.assertRaises(TypeError):k.replay_saved_sup_event_53716(p)

    def test_completion_observation_domain(self):
        p=full_payload();p['completed_sinks']=['52858','53024'];k.replay_saved_sup_event_53716(p)
        for completion in(['52858','52858'],['wrong'],['74147'],[1]):
            p=full_payload();p['completed_sinks']=completion
            with self.assertRaises(ValueError):k.replay_saved_sup_event_53716(p)


if __name__=='__main__':unittest.main()
