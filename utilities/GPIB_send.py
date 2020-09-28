import pyvisa
rm = pyvisa.ResourceManager()
inst = rm.open_resource('GPIB0::10::INSTR')
inst.write("*RCL 3")

