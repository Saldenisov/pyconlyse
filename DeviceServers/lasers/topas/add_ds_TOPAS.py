"""Explicitly register a TOPAS instance; registration never starts vendor software."""
import argparse
import socket

from tango import Database, DbDevInfo, DbServerInfo, DevFailed

from DeviceServers.lasers.topas.client import TopasClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device-name', default='manip/laser/topas_t21082')
    parser.add_argument('--instance', default='T21082')
    parser.add_argument('--serial', required=True)
    parser.add_argument('--api-host', default='127.0.0.1')
    parser.add_argument('--api-port', type=int, default=8004)
    args = parser.parse_args()
    client = TopasClient(args.api_host, args.api_port, args.serial)
    client.close()
    db = Database()
    server = 'DS_TOPAS/' + args.instance
    try:
        existing = db.get_device_info(args.device_name)
    except DevFailed as exc:
        if not any(getattr(error, 'reason', '') in {'DB_DeviceNotDefined', 'API_DeviceNotDefined'} for error in exc.args):
            raise
    else:
        raise RuntimeError(f'{args.device_name} is already registered on {existing.ds_full_name}; inspect it before changing properties')
    device = DbDevInfo()
    device.name, device._class, device.server = args.device_name, 'DS_TOPAS', server
    db.add_device(device)
    db.put_device_property(args.device_name, {
        'api_host': args.api_host, 'api_port': args.api_port, 'topas_serial': args.serial,
        'timeout_s': 2.0, 'poll_interval_s': 1.0, 'stale_after_s': 5.0,
    })
    info = DbServerInfo()
    info.name, info.host, info.mode, info.level = server, socket.getfqdn(), 1, 1
    db.put_server_info(info)
    print(f'Registered {args.device_name} on {server}; vendor software and hardware were not started')


if __name__ == '__main__':
    main()
