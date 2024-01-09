from msl.equipment import EquipmentRecord, ConnectionRecord, Backend

record1 = EquipmentRecord(
    manufacturer='Avantes',
    model='AvaSpec-2048L',  # update for your device
    serial='1810225U1',  # update for your device
    connection=ConnectionRecord(
        address='SDK::C:/dev/pyconlyse/DeviceServers/AVANTES_CCD/avaspecx64.dll'
    )
)

record2 = EquipmentRecord(
    manufacturer='Avantes',
    model='AvaSpec-2048L',  # update for your device
    serial='1810226U1',  # update for your device
    connection=ConnectionRecord(
        address='SDK::C:/dev/pyconlyse/DeviceServers/AVANTES_CCD/avaspecx64.dll'
    )
)

spectrometer1 = record1.connect()
print(spectrometer1._handle)
spectrometer2 = record2.connect()
print(spectrometer2._handle)