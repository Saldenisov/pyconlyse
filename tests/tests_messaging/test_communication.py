from time import sleep
from collections import OrderedDict as od
from communication.messaging.message_utils import MsgGenerator
from devices.devices import Server, Service
from devices.virtualdevices.clients import SuperUser
from devices.service_devices.stepmotors.stpmtr_emulate import StpMtrCtrl_emulate
from tests.fixtures import server_test, superuser_test, stpmtr_emulate_test
from tests.tests_messaging.auxil import clean_test_queues, start_devices, stop_devices
from utilities.data.messages import Message
from utilities.data.datastructures.mes_independent.devices_dataclass import (FuncActivateInput, FuncActivateOutput,
                                                                             FuncPowerInput, FuncPowerOutput)
from utilities.data.datastructures.mes_independent.stpmtr_dataclass import (AxisStpMtr, AxisStpMtrEssentials,
                                                                            FuncActivateAxisInput,
                                                                            FuncActivateAxisOutput, FuncMoveAxisToInput,
                                                                            FuncMoveAxisToOutput, FuncGetPosInput,
                                                                            FuncGetPosOutput,
                                                                            FuncGetStpMtrControllerStateInput,
                                                                            FuncGetStpMtrControllerStateOutput,
                                                                            FuncStopAxisInput, FuncStopAxisOutput,
                                                                            relative, absolute)

def test_superuser_server_services_functions(server_test: Server,
                                             superuser_test: SuperUser,
                                             stpmtr_emulate_test: StpMtrCtrl_emulate):
    server = server_test
    superuser = superuser_test
    stpmtr_emulate = stpmtr_emulate_test

    devices = od()
    devices[server.id] = server
    devices[superuser.id] = superuser
    devices[stpmtr_emulate.id] = stpmtr_emulate

    services_id = []
    for device_id, device in devices.items():
        if device_id not in [server.id, superuser.id]:
            services_id.append(device_id)

    start_devices(devices)

    sleep(5)

    # Verify Server status
    assert server.device_status.active
    assert stpmtr_emulate.id in server.services_running
    assert superuser.id in server.clients_running

    # Verify SuperUser status
    assert superuser.device_status.active
    assert server.id in superuser.connections

    # Verify Stpmtr_emulate
    assert not stpmtr_emulate.device_status.power
    assert not stpmtr_emulate.device_status.active
    assert server.id in stpmtr_emulate.connections

    # !SuperUser-Server-Stpmtr_emulate are connected!
    # getting hello message for device and deleting it from tasks_out_test
    for device_id, device in devices.items():
        if device_id != server.id:
            msg_id, msg = next(iter(device.thinker.tasks_out_test.items()))
            del device.thinker.tasks_out_test[msg_id]
            assert msg.data.com == MsgGenerator.HELLO.mes_name
            # checking if hello msg arrived to server
            assert msg_id, server.thinker.tasks_in_test
            sleep(0.01)
            del server.thinker.tasks_in_test[msg_id]
            try:
                assert len(device.thinker.tasks_in_test) == 1
            except AssertionError:
                print(f'Device_id: {device.id}. task_in_test: {device.thinker.tasks_in_test}')
                raise

    # getting welcome_info from server task_out_test and check if it has arrived to device: service, user
    for msg_id, msg in server.thinker.tasks_out_test.items():
        msg: Message = msg
        assert msg.data.com == MsgGenerator.WELCOME_INFO.mes_name
        device_receiver = devices[msg.body.receiver_id]
        sleep(0.01)
        assert msg_id in device_receiver.thinker.tasks_in_test
        del device_receiver.thinker.tasks_in_test[msg_id]
    server.thinker.tasks_out_test.clear()

    # superuser asks server about available services
    msg_available_services = MsgGenerator.available_services_demand(superuser)
    superuser.thinker.add_task_out(msg_available_services)
    assert msg_available_services.id in superuser.thinker.tasks_out_test
    del superuser.thinker.tasks_out_test[msg_available_services.id]
    sleep(0.02)
    # server recieves this demand
    assert msg_available_services.id in server.thinker.tasks_in_test
    # get reply from server
    reply_to_demand: Message = next(iter(server.thinker.tasks_out_test.values()))
    del server.thinker.tasks_out_test[reply_to_demand.id]
    assert reply_to_demand.reply_to == msg_available_services.id
    sleep(0.02)
    # superuser receives reply
    reply: Message = next(iter(superuser.thinker.tasks_in_test.values()))
    del superuser.thinker.tasks_in_test[reply.id]
    assert type(reply.data.info) == MsgGenerator.AVAILABLE_SERVICES_REPLY.mes_class
    for service_id in services_id:
        assert service_id in reply.data.info.running_services

    #clear devices
    clean_test_queues(devices)

    # superuser now asks all services POWER ON
    msg_ids = []
    for service_id in services_id:
        msg_power_on = MsgGenerator.do_it(superuser, com='power', input=FuncPowerInput(True), device_id=service_id)
        msg_ids.append(msg_power_on.id)
        superuser.thinker.add_task_out(msg_power_on)
        del superuser.thinker.tasks_out_test[msg_power_on.id]
    sleep(0.02)
    # server must get all of these demands and forward them to services
    for msg_id in msg_ids:
        assert msg_id in server.thinker.tasks_out_test
        del server.thinker.tasks_out_test[msg_id]
    sleep(0.02)
    # checking what services have recieved
    for service_id in services_id:
        service: Service = devices[service_id]
        msg_id, msg_recieved = next(iter(service.thinker.tasks_in_test.items()))
        del service.thinker.tasks_in_test[msg_id]
        assert msg_id in msg_ids
        assert msg_recieved.data.com == 'do_it'
        assert msg_recieved.data.info.input == FuncPowerInput(True)
    sleep(0.05)
    # checking what services are sending back
    for service_id in services_id:
        service: Service = devices[service_id]
        msg_id, msg_send = next(iter(service.thinker.tasks_out_test.items()))
        del service.thinker.tasks_out_test[msg_id]
        assert msg_send.data.com == 'done_it'
        assert msg_send.data.info.result == FuncPowerOutput(comments=f'Power is {service.device_status.power}. '
                                                                    f'But remember, that user switches power manually...',
                                                            func_success=True,
                                                            device_status=service.device_status)
    sleep(0.01)
    # checking what superuser recieves
    msg_id, msg_recieved = next(iter(superuser.thinker.tasks_in_test.items()))
    del superuser.thinker.tasks_in_test[msg_id]
    assert msg_recieved.data.com == 'done_it'
    assert msg_recieved.data.info.result == FuncPowerOutput(comments=f'Power is {service.device_status.power}. '
                                                                 f'But remember, that user switches power manually...',
                                                        func_success=True,
                                                        device_status=service.device_status)

    # superuser now asks all services ACTIVATE ON
    msg_ids = []
    for service_id in services_id:
        msg_power_on = MsgGenerator.do_it(superuser, com='activate', input=FuncActivateInput(True),
                                          device_id=service_id)
        msg_ids.append(msg_power_on.id)
        superuser.thinker.add_task_out(msg_power_on)
        del superuser.thinker.tasks_out_test[msg_power_on.id]
    sleep(0.02)
    # checking what services are sending back
    for service_id in services_id:
        service: Service = devices[service_id]
        msg_id, msg_send = next(iter(service.thinker.tasks_out_test.items()))
        del service.thinker.tasks_out_test[msg_id]
        assert msg_send.data.com == 'done_it'
        assert msg_send.data.info.result.func_success == True
        assert msg_send.data.info.result.device_status == service.device_status

    # Testing receiving
    # pyqtslot is connected

    stop_devices(devices)

