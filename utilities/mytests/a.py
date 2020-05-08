from datastructures.mes_dependent.dicts import Events_Dict, MsgDict

tasks_out = MsgDict(name='tasks_out', size_limit=100, parent_logger=None)


tasks_out[1] = 2
tasks_out[100] = 200

print(tasks_out)

a = tasks_out.popitem(last=False)
print(tasks_out)

b = 2
