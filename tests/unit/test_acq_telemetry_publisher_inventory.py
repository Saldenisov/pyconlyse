"""Read-only census is a scope ledger, never proof of inserted hooks."""
from pathlib import Path
import unittest

from tools.inventory_acq_telemetry_publishers import inventory
from legacy.xp_acq_agent.elyse_agent.labview_telemetry import ALL_PUBLICATIONS


ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT / '.tmp/acq_original_diagram_census_20261001/0_ACQ_ELYSE/vi_BDHb.xml'
PIN = '36e2857bf3031a1c7ab5a5be9c8a0c2fadeb91e32d60a29652f536f7f3ddb5cb'


class CensusTests(unittest.TestCase):
    def test_pinned_original_has_73_sites_and_19_names(self):
        result = inventory(EXPORT)
        self.assertEqual(result['export_sha256'], PIN)
        self.assertEqual(result['writer_count'], 73)
        self.assertEqual(set(result['publications']), set(ALL_PUBLICATIONS))
        self.assertEqual(len({r['source_site'] for r in result['sites']}), 73)
        self.assertTrue(all(r['uri'].startswith('ni.var.psp://10.20.30.2/SUPERVISION/')
                            for r in result['sites']))
        self.assertFalse(result['instrumented_copy_complete'])
        self.assertTrue(all(r['native_hook_verified'] is False for r in result['sites']))

    def test_known_runtime_and_startup_sites_keep_owner_and_data_wire(self):
        sites = {r['writer_uid']: r for r in inventory(EXPORT)['sites']}
        for uid, owner, publication, terminal in (
                ('7486', '7392', 'C5_IN_DIO96', '7514'),
                ('18703', '7392', 'VTA', '18731'),
                ('16580', '24611', 'C6NI6703', '16600'),
                ('21449', '1507', 'C1011NI6602', '21471')):
            record = sites[uid]
            self.assertEqual((record['diagram_uid'], record['publication'],
                              record['data_terminal_uid']), (owner, publication, terminal))
            self.assertTrue(record['data_wire_uid'])
            self.assertTrue(record['data_type'])


if __name__ == '__main__':
    unittest.main()
