import serial
import serial.tools.list_ports


def find_arduino(serial_number='75833353934351B05090') -> str:
    """
    Searches for Arduino with a given serial number and returns its COM com_port.
    :param serial_number: Arduino serial id
    :return: COM PORT
    """
    for pinfo in serial.tools.list_ports.comports():
        if pinfo.serial_number == serial_number:
            return pinfo.device
    raise IOError(f"Could not find an Arduino {serial_number}. Check connection.")



print(find_arduino())