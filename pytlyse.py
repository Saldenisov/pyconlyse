import sys
from pathlib import Path
from subprocess import call
if __name__ == '__main__':
    try:
        l = len(sys.argv)
        if l < 2:
            raise IndexError
        else:
            script = sys.argv[1]
            args = sys.argv[2:]
            print("Starting: " + script + " with parameters: " + str(args))
    except IndexError:
        print("Not enough parameters were given to script: len(sys.argv) equals to: " + str(l))

    try:
        script_path = str(Path(__file__).resolve().parent / 'bin' / script)
        com = [sys.executable, script_path]
        for arg in args:
            com.append(arg)
        print(com)
        call(com)
    except:
        print('Error occured')