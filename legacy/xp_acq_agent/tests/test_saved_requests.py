"""Saved request facets are pure snapshots, never a PSP publisher or scheduler."""
import copy
import unittest
from elyse_agent import saved_requests as core


def payload(page='ht'):
    uid,arrows,targets=core.PAGE_SPECS[page]
    return dict(facet='supervision_dps',source_id='APP-17',uid=uid,page=page,
        gate_dps=[False]*29,base_dps=[True]*29,adjustments=[False]*arrows,commands=[False]*len(targets))


class Poison(object):
    def __iter__(self):
        raise AssertionError('unselected base read')
    def __len__(self):
        raise AssertionError('unselected base read')


class SavedRequestTests(unittest.TestCase):
    def test_all_five_independent_bases_preserve_unassigned_fields(self):
        for page,(uid,arrows,targets) in core.PAGE_SPECS.items():
            data=payload(page)
            result=core.replay_saved_requests(data)
            self.assertEqual(result['outputs']['projected_dps'],[i not in targets for i in range(29)])
            self.assertTrue(result['outputs']['dps_writer_selected'])
            self.assertFalse(result['external_calls_executed'])
            self.assertFalse(result['atomic_snapshots_qualified'])
            self.assertFalse(result['psp_delivery_qualified'])

    def test_each_gate_bit_skips_writer_without_reading_bundle_base(self):
        for page,(uid,arrows,targets) in core.PAGE_SPECS.items():
            for index in range(29):
                gate=[False]*29
                gate[index]=True
                self.assertIsNone(core.route_page_request(page,gate,[False]*arrows,[True]*len(targets),Poison()))

    def test_each_adjustment_skips_only_the_dps_facet(self):
        for page,(uid,arrows,targets) in core.PAGE_SPECS.items():
            for index in range(arrows):
                data=payload(page)
                data['adjustments'][index]=True
                data['base_dps']=None
                result=core.replay_saved_requests(data)
                self.assertFalse(result['outputs']['dps_writer_selected'])
                self.assertFalse(result['outputs']['other_branches_replayed'])
                self.assertIsNone(result['outputs']['projected_dps'])

    def test_idle_all_false_still_selects_writer_and_inputs_unchanged(self):
        data=payload('magnets')
        data['base_dps']=[False]*29
        before=copy.deepcopy(data)
        result=core.replay_saved_requests(data)
        self.assertTrue(result['outputs']['dps_writer_selected'])
        self.assertEqual(result['outputs']['projected_dps'],[False]*29)
        self.assertEqual(data,before)

    def test_distinct_legacy_snapshot_helpers_still_forward_all_false_write(self):
        self.assertEqual(core.project_page_ht_dps_write([False]*29,[False]*8,[False]*5),tuple([False]*29))
        self.assertEqual(core.project_page_modulator_dps_write([False]*29,[False]*11),tuple([False]*29))
        self.assertEqual(core.project_page_fluides_dps_write([False]*29,[False]*4,[False]*2),tuple([False]*29))
        self.assertEqual(core.project_page_alimentations_dps_write([False]*29,[False]*3),tuple([False]*29))
        self.assertEqual(core.project_page_hf_dps_write([False]*29,[False]*8,[False]*2),tuple([False]*29))

    def test_all_acquisition_entry_flags_and_empty_false_arms(self):
        for index in range(3,26):
            for new in (False,True):
                result=core.replay_saved_requests(dict(facet='acquisition_entry',source_id='APP-00',uid='43',event_index=index,new_value=new))
                outputs=result['outputs']
                self.assertIs(outputs['enters_sequence'],new)
                self.assertEqual(outputs['duration_argument'],(1000 if index==3 else 150) if new else None)
                self.assertEqual(outputs['registration_flags'],-2147483647 if index==25 else 1)

    def test_exact_site_schema_and_absent_unselected_base_policy(self):
        for key,value in (('uid','43'),('source_id','APP-00'),('gate_dps',[False]*28),
                          ('commands',[False]*4),('adjustments',[False]*7),('base_dps',None)):
            data=payload()
            data[key]=value
            with self.assertRaises(ValueError):
                core.replay_saved_requests(data)
        data=payload()
        data['gate_dps'][0]=True
        with self.assertRaises(ValueError):
            core.replay_saved_requests(data)
        data['base_dps']=None
        self.assertFalse(core.replay_saved_requests(data)['outputs']['dps_writer_selected'])

    def test_no_integer_boolean_coercion_or_unknown_entry(self):
        data=payload()
        data['gate_dps'][0]=1
        with self.assertRaises(ValueError):
            core.replay_saved_requests(data)
        for index in (True,0,26):
            with self.assertRaises(ValueError):
                core.procedure_entry_values(index,True)
        with self.assertRaises(TypeError):
            core.procedure_entry_values(3,1)


if __name__=='__main__':
    unittest.main()
