"""Pure saved selection,reset and separate publication snapshots."""
import unittest
from elyse_agent import saved_dispatch as core


def payload(facet='dispatch',event=None):
    uid='8105' if facet=='dispatch' else core.TAILS[event][3 if facet=='reset' else 4]
    return dict(source_id='APP-00',uid=uid,facet=facet,dps=[False]*29,event_index=event)


class SavedDispatchTests(unittest.TestCase):
    def test_idle_selector_writes_action_false(self):
        self.assertEqual(core.dispatch_values((False,)*29),(-1,0,'NO_REQUEST',False,None,None))

    def test_all24_explicit_targets_including_orphan(self):
        for index,(ddo,event) in enumerate(core.TARGETS):
            result=core.dispatch_values(tuple(i==index for i in range(29)))
            self.assertEqual(result,(index,index+1,'EXPLICIT_PROPERTY',None,ddo,event))
        self.assertIsNone(core.TARGETS[22][1])

    def test_all_nonempty_tail_masks_use_saved_default_without_property(self):
        for mask in range(1,32):
            bank=(False,)*24+tuple(bool(mask & (1<<i)) for i in range(5))
            first=next(i for i,bit in enumerate(bank) if bit)
            self.assertEqual(core.dispatch_values(bank),(first,first+1,'SAVED_DEFAULT',False,None,None))
            data=payload()
            data['dps']=list(bank)
            outputs=core.replay_saved_dispatch(data)['outputs']
            self.assertIs(outputs['action_assignment'],False)
            self.assertEqual(outputs['property_assignments'],[])
            self.assertIs(outputs['unknown_case_outputs'],False)
            self.assertEqual(data['dps'],list(bank))

    def test_first_true_wins_without_mutation(self):
        bank=tuple(i in (3,22,27) for i in range(29))
        self.assertEqual(core.dispatch_values(bank)[0],3)
        self.assertEqual(sum(bank),3)

    def test_each_handler_clears_only_own_bit(self):
        for event,tail in core.TAILS.items():
            result=core.reset_values((True,)*29,event)
            self.assertEqual(result,tuple(i!=tail[0] for i in range(29)))

    def test_publication_reads_independent_snapshot(self):
        reset=core.reset_values((True,)*29,3)
        publish=(True,)*29
        writer,uri,result=core.publication_values(publish,3)
        self.assertIs(result,publish)
        self.assertNotEqual(result,reset)
        self.assertEqual(writer,core.TAILS[3][1])
        self.assertTrue(uri.endswith('/DPS'))

    def test_exact_saved_uid_and_boolean_storage_required(self):
        data=payload('reset',3)
        data['uid']='3'
        self.assertRaises(ValueError,core.replay_saved_dispatch,data)
        data=payload()
        data['dps'][0]=1
        self.assertRaises(TypeError,core.replay_saved_dispatch,data)
        self.assertRaises(TypeError,core.dispatch_values,[False]*29)

    def test_every_json_facet_is_inert(self):
        for facet,event in (('dispatch',None),('reset',3),('publication',3)):
            result=core.replay_saved_dispatch(payload(facet,event))
            for key in ('execution_allowed','external_calls_executed','hardware_writes',
                'psp_delivery_qualified','event_acknowledgement_qualified','atomic_snapshots_qualified',
                'whole_event_equivalence','native_runtime_equivalence'):
                self.assertIs(result[key],False)


if __name__=='__main__':
    unittest.main()
