from utilities.datastructures.mes_dependent.dicts import Events_Dict
from communication.logic.thinker import ThinkerEvent


def test_event_dict():
    event = ThinkerEvent(name='test', logic_func=None, parent=None,
                         external_name='test_external', event_id='event_id')
    dct = Events_Dict()
    dct[event.id] = event
    assert event.id in dct
    assert event.name in dct
    assert 'a' not in dct
    assert '' not in dct
    print(dct, dct.name_id)

    try:
        assert dct[event.name]== event
    except KeyError:
        assert False

    try:
        assert dct[event.id] == event
    except KeyError:
        assert False

    try:
        del dct[event.id]
        assert dct.name_id == {}
        assert dct == {}
    except KeyError:
        assert False

    dct[event.id] = event

    try:
        del dct[event.name]
        assert dct.name_id == {}
        assert dct == {}
    except KeyError:
        assert False