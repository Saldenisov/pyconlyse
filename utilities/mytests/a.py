from configparser import ConfigParser, RawConfigParser
config = RawConfigParser()

config.add_section('main')
config.set('main', 'key1', 'value1')
config.set('main', 'key2', 'value2')
config.set('main', 'key3', 'value3')
config.set('main', 'key1', '{sdfsdfsdf: sdf}')

import io

f = open('test',)


with open(f, 'w') as a:
    config.write(a)

a = f.read()

print(a)