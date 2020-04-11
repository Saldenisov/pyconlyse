import pprint
from pathlib import Path
from typing import List, Iterable, Generator, Union
pp = pprint.PrettyPrinter()

def dirpath_to_dict(path: Path, d: dict) -> dict:

    name = path.parts[-1]

    if path.is_dir():
        if name not in d['dirs']:
            d['dirs'][name] = {'dirs': {}, 'files': []}
            for x in path.glob('*'):
                dirpath_to_dict(x, d['dirs'][name])
    else:
        d['files'].append(name)
    return d

def paths_to_dict(paths: Union[Iterable[Union[Path, str]], Generator], d={'dirs': {}, 'files': []}) -> dict:
    def fill_dict(parts: List[str], d: dict, filename: str):
        part = parts.pop(0)
        if part != filename:
            if part not in d['dirs']:
                d['dirs'][part] = {'dirs': {}, 'files': []}
            if parts:
                fill_dict(parts, d['dirs'][part], filename)
        else:
            d['files'].append(part)

    for path in paths:
        if not isinstance(path, Path):
            path = Path(path)
        fill_dict(list(path.parts), d, path.name)
    return d


mydict = dirpath_to_dict(Path('C:\\dev\\pyconlyse\\bin'), d={'dirs': {}, 'files': []})
mydict2 = paths_to_dict([Path('C:\\dev\\pyconlyse\\bin\\service.py'), Path('C:\\dev\\pyconlyse\\bin\\VD2.py')])
mydict3 = paths_to_dict(['C:\\dev\\pyconlyse\\bin\\service.py', 'C:\\dev\\pyconlyse\\bin\\VD2.py',
                         'C:\\dev\\pyconlyse\\bin\\VD2__.py'])

pp.pprint(mydict3)

