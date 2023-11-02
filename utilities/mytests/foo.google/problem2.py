train = [[["1.11", "2.0.0", "1.2", "2", "0.1", "1.2.1", "1.1.1", "2.0"],
          ["0.1", "1.1.1", "1.2", "1.2.1", "1.11", "2", "2.0", "2.0.0"]],
         [["1.1.2", "1.0", "1.3.3", "1.0.12", "1.0.2"],
          ["1.0", "1.0.2", "1.0.12", "1.1.2", "1.3.3"]]]



def solution(l):

    def convert_l(l):
        converted_l = []

        def split_to_l_int(split, extra):
            arr = []
            for elem in split:
                arr.append(int(elem))
            if extra != 0:
                for i in range(extra):
                    arr.append(-1)
            return tuple(arr)

        for elem in l:
            split = elem.split('.')
            converted_l.append(split_to_l_int(split, 3 - len(split)))

        return converted_l

    def sort(converted_l):
        """
        input_seq[ix1], input_seq[ix2] = input_seq[ix2], input_seq[ix1]
        """
        sorted_l = []
        sort_run = True
        step = 0
        i = 0
        def exchange(converted_l, index):
            """
            "1.11.-1", "2.0.0"
            """
            elem_i = converted_l[i]
            elem_i1 = converted_l[i + 1]

            def should_exchange(val1, val2):
                if val1 < val2:
                    return -1
                elif val1 == val2:
                    return 0
                else:
                    return 1

            for val1, val2 in zip(elem_i, elem_i1):
                res = should_exchange(val1, val2)
                if res == 1:
                    return True
                elif res == -1:
                    return False
                elif res == 0:
                    pass


        while sort_run:
            if i < len(converted_l) - 1:
                res = exchange(converted_l, i)
                if res:
                    converted_l[i], converted_l[i+1] = converted_l[i+1], converted_l[i]
                    i = 0
                else:
                    i += 1
            else:
                sort_run = False
        return converted_l

    def convert_back(sorted_l):
        solved_l = []
        for elem in sorted_l:
            solved_l.append('.'.join([str(num) for num in elem if num >= 0]))
        return solved_l

    return convert_back(sort(convert_l(l)))

res = solution(train[0][0])
assert res == train[0][1]
res = solution(train[1][0])
assert res == train[1][1]
