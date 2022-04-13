def fill_keys(d, obj):
    if isinstance(obj, int):
        return None
    keys = [obj.keys()]
    if len(obj.keys()) == 0:
        return None
    else:
        for key in obj.keys():
            d[key] = {}
            d[key] = fill_keys(d[key], obj[key])
        return d


p = {'A': {'b': {'c': 1, 'd': 1}}}

a = {}

fill_keys(a, p)

print(a)
