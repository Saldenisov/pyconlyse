def solution(s):
    test = {'code': '100100101010100110100010',
            "Braille": '000001110000111010100000010100111000111000100010',
            "The quick brown fox jumps over the lazy dog":
                '000001011110110010100010000000111110101001010100100100101000000000110000111010101010010111101110000000110100101010101101000000010110101001101100111100011100000000101010111001100010111010000000011110110010100010000000111000100000101011101111000000100110101010110110'}

    import string
    def build_alp(dict):
        d = {}
        for key, val in dict.items():
            i = 0
            for letter in key:
                t = val[i * 6: i * 6 + 6]
                if letter == ' ':
                    if letter not in d:
                        d[letter] = t
                elif letter.isupper():
                    if 'upper' not in d:
                        d['upper'] = t
                    i += 1
                    d[letter.lower()] = val[i * 6: i * 6 + 6]
                else:
                    if letter not in d:
                        d[letter] = t
                i += 1
        return d

    alph = build_alp(test)

    def translate(s, alph):
        s_out = []
        for letter in s:
            if letter.isupper():
                s_out.append(alph['upper'])
            s_out.append(alph[letter.lower()])
        return ''.join(s_out)
    return translate(s, alph)

res = solution('code')
assert res == '100100101010100110100010'
res = solution('Braille')
assert res == '000001110000111010100000010100111000111000100010'
res = solution("The quick brown fox jumps over the lazy dog")
assert res == '000001011110110010100010000000111110101001010100100100101000000000110000111010101010010111101110000000110100101010101101000000010110101001101100111100011100000000101010111001100010111010000000011110110010100010000000111000100000101011101111000000100110101010110110'

