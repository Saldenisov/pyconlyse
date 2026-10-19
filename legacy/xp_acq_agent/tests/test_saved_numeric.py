import unittest
from elyse_agent import saved_numeric as core


def payload(operation='parse'):
    shared = dict(operation=operation, decimal_separator='.', use_system_decimal_point=True)
    if operation == 'parse':
        shared.update(text='-4.7e-3x', offset=0, default=0.0)
    else:
        shared.update(number=4.911, width=5, precision=2)
    return shared


class NumericTests(unittest.TestCase):
    def test_documented_examples(self):
        self.assertEqual(core.fract_exp_to_dbl('-4.7e-3x', supplied_decimal_separator='.'),(-.0047,7))
        self.assertEqual(core.fract_exp_to_dbl('+5.3.2', supplied_decimal_separator='.'),(5.3,4))
        for number,width,precision,expected in [(4.911,5,2,'4.91e0'),(.003926,10,2,'   3.93e-3'),(216.01,5,0,'  2e2')]:
            self.assertEqual(core.dbl_to_exp_string(number,width,precision,supplied_decimal_separator='.'),expected)

    def test_explicit_locale_profile(self):
        self.assertEqual(core.fract_exp_to_dbl('1,25e2x',supplied_decimal_separator=','),(125.0,6))
        self.assertEqual(core.fract_exp_to_dbl('1.25e2x',use_system_decimal_point=False,supplied_decimal_separator=','),(125.0,6))
        self.assertEqual(core.dbl_to_exp_string(1.25,0,2,supplied_decimal_separator=','),'1,25e0')
        with self.assertRaises(ValueError):core.fract_exp_to_dbl('1.25')

    def test_preserves_inputs(self):
        for operation in ('parse','format'):
            data=payload(operation);before=dict(data);core.replay_payload(data);self.assertEqual(data,before)

    def test_unqualified_domains(self):
        for text in ('',' 1','+','NaN','Inf','1e+','-0','1e300','1e-300','é1'):
            with self.assertRaises(ValueError):core.fract_exp_to_dbl(text,supplied_decimal_separator='.')
        for value in (float('nan'),float('inf'),-0.0,1e-13,1e13):
            with self.assertRaises(ValueError):core.dbl_to_exp_string(value,0,2,supplied_decimal_separator='.')
        with self.assertRaises(ValueError):core.dbl_to_exp_string(1.25,0,1,supplied_decimal_separator='.')
        with self.assertRaises(ValueError):core.replay_payload(dict(payload(),extra=1))


if __name__=='__main__':unittest.main()
