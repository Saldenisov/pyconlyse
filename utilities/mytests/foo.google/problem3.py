def solution(src, dest):
    if src == dest:
        return 0

    def pos_to_coordinate(cell):
        """
        Convert cell number to grid coordinate
        """
        y_pos = int(cell // 8)
        x_pos = cell - 8 * y_pos
        return x_pos, y_pos

    def move_is_allowed(pos, move):
        allowed = False
        xm, ym = move
        xp, yp = pos
        xr = xp + xm
        yr = yp + ym
        if (xr >= 0 and xr < 8 and yr >= 0 and yr < 8):
            allowed = True
        return allowed

    def possible_end_positions(coordinate_init):
        # Moves of a knight
        xm = (2, 2, -2, -2, 1, 1, -1, -1)
        ym = (1, -1, 1, -1, 2, -2, 2, -2)

        allowed_positions = []
        xp, yp = coordinate_init
        for x, y in zip(xm, ym):
            if move_is_allowed(coordinate_init, (x, y)):
                allowed_positions.append((xp + x, yp + y))
        return allowed_positions

    def check_dest(coordinate_dest, moves_array):
        if coordinate_dest in moves_array:
            return True
        return False

    i = 0

    src_coordinate = pos_to_coordinate(src)
    dest_coordinate = pos_to_coordinate(dest)
    moves = possible_end_positions(src_coordinate)
    moves_deeper = []

    while True:
        i += 1
        if dest_coordinate in moves:
            return i
        for m in moves:
            moves_deeper.extend(possible_end_positions(m))
            if dest_coordinate in moves_deeper:
                return i + 1
        moves = moves_deeper
        moves_deeper = []

res = solution(19, 36)
assert res == 1
res = solution(0, 1)
assert res == 3

import math


def pos_to_coords(pos):
    """
    Converts a position [0..63] into a pair of coord (x, y)
    """
    x = int(math.floor(pos / 8))
    y = int(pos % 8)
    return (x, y)



def get_possible_moves(x, y):
    """
    Returns a list of valid coordinates for next move
    """
    all_moves = []
    all_moves.append((x + 2, y + 1))
    all_moves.append((x + 2, y - 1))
    all_moves.append((x - 2, y + 1))
    all_moves.append((x - 2, y - 1))
    all_moves.append((x + 1, y + 2))
    all_moves.append((x + 1, y - 2))
    all_moves.append((x - 1, y + 2))
    all_moves.append((x - 1, y - 2))

    valid_moves = []
    for (x, y) in all_moves:
        if (x >= 0 and x < 8 and y >= 0 and y < 8):
            valid_moves.append((x, y))

    return valid_moves


def solution_2(src, dest):
    if src == dest:
        return 0

    # Get the current and target tile
    src_x, src_y = pos_to_coords(src)
    dst_x, dst_y = pos_to_coords(dest)

    # Create a queue with all the positions I need to check
    queue = get_possible_moves(src_x, src_y)
    depth_queue = []

    # the depth, or solution
    depth = 0

    while True:
        depth += 1

        # We check each move available at this depth
        for move in queue:
            # Let's see if we arrived to destination
            if move[0] == dst_x and move[1] == dst_y:
                return depth

            # we build the next depth queue, which will replace the queue after we tested them all
            # this is necessary to test one level at a time
            depth_queue.extend(get_possible_moves(move[0], move[1]))

        queue = depth_queue
        depth_queue = []


for i in range(64):
    for j in range(64):
        res = solution(i, j)
        res2 = solution_2(i, j)
        assert res == res2