import ifaddr

adapters = ifaddr.get_adapters()

ips_l = []
for adapter in adapters:
    for ip in adapter.ips:
        if ip.network_prefix < 64:
            ips_l.append(ip.ip)
def get129(ips_l):
    for ip in ips_l:
        if '129.' in ip:
            return ip
print(ips_l, get129(ips_l))
