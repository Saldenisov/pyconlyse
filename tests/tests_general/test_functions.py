from utilities.myfunc import unique_id
from utilities.tools.files_work import write_to_file_unique

def test_unique_id():
    ids = []
    #you can pass any object in the function
    ids.append(unique_id(test_unique_id))
    ids.append(unique_id((1,2)))
    for i in range(100):
        gen_id = unique_id(i)
        assert gen_id not in ids
        ids.append(gen_id)


def test_write_to_file_uniqie():
    data_arr = []

    import random
    import string
    from pathlib import Path
    file_name = 'write_to_file_test.txt'
    with open('write_to_file_test.txt', 'w+') as f:
        f.write('test')

    def get_random_string(length):
        letters = string.ascii_lowercase
        result_str = ''.join(random.choice(letters) for _ in range(length))
        return result_str

    def get_random_dict(length):
        d = {}
        for _ in range(length):
            s = get_random_string(2)
            d[s] = random.randint(0, 100)
        return d

    for i in range(10):
        s = get_random_string(15)
        data_arr.append(s)
        data_arr.append(s)
        d = get_random_dict(5)
        data_arr.append(d)
        data_arr.append(d)

    file_path = Path('write_to_file_test.txt')
    for data in data_arr:
        write_to_file_unique(file_path, data)