import pytest
from utilities.myfunc import unique_id


def test_unique_id():
    ids = []
    #you can pass any object in the function
    ids.append(unique_id(test_unique_id))
    ids.append(unique_id((1,2)))
    for i in range(100):
        gen_id = unique_id(i)
        assert gen_id not in ids
        ids.append(gen_id)

