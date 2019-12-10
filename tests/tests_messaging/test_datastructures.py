from utilities.data.datastructures.mes_dependent import OrderedDictMod, OrderedDictMesTypeCounter, PendingDemand
from tests.tests_messaging.fixtures import standard_OrderedDict
import pytest

def test_OrderedDictMod(standard_OrderedDict):
    ords = standard_OrderedDict
    name = 'test'
    ordq = OrderedDictMod(name=name)

    # testing compatibility with OrderedDict
    for key, value in ords.items():
        ordq[key] = value
    assert ordq == ords
    assert ordq.keys() == ords.keys()

    # Testing ODQ for adding existing element
    try:
        key = 'last_added'
        ordq['last_added'] = 100
        assert False
    except KeyError as e:
        assert True

    try:
        ordq['extra_element'] = 200
        assert True
    except KeyError as e:
        pass


def STOP_test_OrderedDictMesTypeCounter(all_messages_generation):
    messages = all_messages_generation
    ordc = OrderedDictMesTypeCounter(name='ordc')

    for i in range(len(messages)):
        ordc[str(i)] = messages[i]

    print(ordc.mes_types)
    assert ordc.mes_types == {'reply': 4, 'info': 6, 'demand': 3}
    del ordc['0']
    del ordc['2']
    del ordc['6']
    print(ordc.mes_types)
    assert ordc.mes_types == {'reply': 2, 'info': 6, 'demand': 2}

    ordc = OrderedDictMesTypeCounter(name='ordc')
    for i in range(len(messages)):
        ordc[str(i)] = PendingDemand(messages[i])

    print(ordc.mes_types)
    assert ordc.mes_types == {'reply': 4, 'info': 6, 'demand': 3}
    del ordc['0']
    del ordc['2']
    del ordc['6']
    print(ordc.mes_types)
    assert ordc.mes_types == {'reply': 2, 'info': 6, 'demand': 2}

