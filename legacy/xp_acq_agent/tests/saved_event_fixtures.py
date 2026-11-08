"""Supplied input fixtures for stateless original-event integration checks."""


def sup_frequency_payload():
    return dict(source_id='APP-17', event_uid='5909', frame_uid='70866',
        local_reads={'60452': [index + 0.25 for index in range(33)]},
        event_returns={'70885': {'70890': 1073741826, '70893': 'opaque event time',
            '71466': 'opaque control reference', '71471': {'unused': 'old value'},
            '71474': 4294967295}},
        references={'70272': {'opaque_native_ref': 'supplied'}},
        unwired_inputs={'70261': {'opaque_effective_error': 'supplied'}},
        writer_returns={'70253': {'70258': 'unused ref output',
            '70264': {'status': True, 'code': -17, 'source': 'supplied fault'}}},
        completed_sinks=['70253', '59714'])


def acq_control_payload(new_value=True):
    steps = [
        ('step', '33741'), ('step', '33731'), ('step', '33723'),
        ('step', '33747'), ('leaf_call', '33755'), ('leaf_return', '33755'),
        ('stage_complete', '33697'), ('step', '33812'), ('step', '33802'),
        ('step', '33796'), ('stage_complete', '33780'),
        ('step', '33958'), ('step', '33905'), ('step', '33891'),
        ('step', '34353'), ('step', '34337'), ('step', '34320'),
        ('stage_complete', '33828'), ('step', '34030'),
        ('leaf_call', '34036'), ('leaf_return', '34036'),
        ('leaf_call', '34076'), ('leaf_return', '34076'),
        ('leaf_call', '34022'), ('leaf_return', '34022'),
        ('stage_complete', '33986'),
    ]
    return dict(source_id='APP-00', event_uid='43', frame_uid='33620', new_value=new_value,
        schedule=[dict(kind=kind, uid=uid) for kind, uid in steps],
        snapshots={'33741': [False] * 32, '33812': [True] * 32,
            '33958': [False] * 12 + [True] + [False] * 16,
            '34353': [True] * 77, '34030': [True] * 29},
        leaf_returns={'33755': {'33757': 0}, '34022': {'34024': 0},
            '34036': {'34041': 'unused opaque returned ref',
                '34047': dict(status=True, code=-17, source='supplied PSP fault')},
            '34076': {'34079': False, '34082': -123, '34094': 'unused source',
                '34097': dict(status=False, code=-21, source='unused handler output'),
                '34100': 'unused description'}},
        unwired_inputs={'34044': dict(status=False, code=17, source='supplied unwired error'),
            '34085': {'opaque_void': 'supplied'}, '34088': -9,
            '34091': 'supplied unwired string', '34103': 65535},
        reference_binding=dict(constant_uid='34004',
            saved_uri='ni.var.psp://10.20.30.2/SUPERVISION/DPS',
            native_ref={'opaque_native_ref': 'supplied'}))
