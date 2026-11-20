"""Encode partial NETIO writes without firmware-dependent no-change actions."""

def output_actions(ids, actions):
    ids, actions = list(ids), list(actions)
    if len(ids) != len(actions) or not ids or len(set(ids)) != len(ids):
        raise ValueError('NETIO output IDs and actions must match without duplicates')
    result = []
    for output_id, action in zip(ids, actions):
        output_id, action = int(output_id), int(action)
        if output_id <= 0 or action not in range(7):
            raise ValueError('Invalid NETIO output ID or action')
        # FW 2.4.4 can accept the HTTP request but ignore the whole action
        # array when it includes Action 5. Omit untouched outlets entirely;
        # a partial Outputs array is supported by the vendor JSON protocol.
        if action not in (5, 6):
            result.append({'ID': output_id, 'Action': action})
    return result


def parse_snapshot(payload):
    """Validate both legacy and current JSON replies before replacing cache."""
    if not isinstance(payload, dict) or not isinstance(payload.get('Agent'), dict):
        raise ValueError('NETIO reply has no Agent identity')
    agent, outputs = payload['Agent'], payload.get('Outputs')
    if not str(agent.get('SerialNumber', '')).strip() or not isinstance(outputs, list) or not outputs:
        raise ValueError('NETIO identity or Outputs are missing')
    ids = [int(output['ID']) for output in outputs]
    states = [int(output['State']) for output in outputs]
    if len(set(ids)) != len(ids) or any(i <= 0 for i in ids) or any(s not in (0, 1) for s in states):
        raise ValueError('NETIO output IDs/states are invalid')
    return dict(ids=ids, states=states, names=[str(o['Name']) for o in outputs],
                actions=[int(o.get('Action', 6)) for o in outputs],
                delays=[int(o.get('Delay', 0)) for o in outputs],
                serial=str(agent['SerialNumber']), model=str(agent.get('Model', '')),
                firmware=str(agent.get('Version', '')))
