import pyvisa
rm = pyvisa.ResourceManager()
inst = rm.open_resource('GPIB0::10::INSTR')


a = input('Type 1 for 10Hz Streak, 2 for 5Hz Streak, 3 for V0 measurements: ')

try:
    a = int(a)
    if a in [1, 2, 3]:
        inst.write(f"*RCL {a}")
        print('Done')
    else:
        raise Exception(f'Incorrect choice: {a}. Must be 1, 2 or 3.')
except Exception as e:
    print(e)



