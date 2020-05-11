
def importCode(code, name, add_to_sys_modules=0):
    """ code can be any object containing code -- string, file object, or
       compiled code object. Returns tests_devices new module object initialized
       by dynamically importing the given code and optionally adds it
       to sys.modules under the given name.
    """
    import importlib
    module = importlib.import_module(name)

    if add_to_sys_modules:
        import sys
        sys.modules[name] = module
    exec(code)

    return module
code = """
def testFunc():
    print("spam!")

class testClass:
    def testMethod(self):
        print("eggs!")
"""

m = importCode(code, "test")
m.testFunc()
o = m.testClass()
o.testMethod()