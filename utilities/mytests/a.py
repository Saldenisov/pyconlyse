file_path = 'C:/DATA/test-bruit.his'
pos = 0
with open(file_path, 'rb') as file:
    head_64_bytes = bytearray(file.read(64))
    pos += 64
    comments_length = int.from_bytes(head_64_bytes[2:4], byteorder='little')
    # TODO: need to find where ends real header with text
    # TODO: need to understand what are the comments, how do they relate to datastructures
    header = file.read(4610)  # .decode(encoding='utf-8')
    header = header.decode(encoding='UTF-8',errors='ignore')
    print(header)