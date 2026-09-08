"""Exercise real nftables in disposable network namespaces, never host rules.

Run as root: python3 scripts/tests/vps_firewall_test.py infra/vps/firewall.nft
Requires iproute2, nft, Python; no Docker/VM restart or external traffic.
"""
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

prefix = "ani-fw-test-" + uuid.uuid4().hex[:8]
names = {role: prefix + "-" + role for role in ("fw", "public", "peer", "container")}
created = []
servers = []


def run(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs)


def ns(role, *args, **kwargs):
    return run("ip", "netns", "exec", names[role], *args, **kwargs)


listener = '''
import socket,threading,time,sys
def listen(port,family):
    s=socket.socket(family);s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    if family==socket.AF_INET6:s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)
    s.bind(('::' if family==socket.AF_INET6 else '0.0.0.0',port));s.listen()
    while True:
        c,_=s.accept();c.close()
def udp():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('0.0.0.0',443))
    while True:
        b,a=s.recvfrom(1024);s.sendto(b,a)
for p in map(int,sys.argv[1:]):
    for family in (socket.AF_INET,socket.AF_INET6):threading.Thread(target=listen,args=(p,family),daemon=True).start()
threading.Thread(target=udp,daemon=True).start()
time.sleep(90)
'''

probe = '''
import json,socket,sys
for host,port,expected,kind,source in json.loads(sys.argv[1]):
    s=socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET,socket.SOCK_DGRAM if kind=='udp' else socket.SOCK_STREAM)
    s.settimeout(0.6)
    if source:s.bind((source,0))
    try:
        if kind=='udp':s.sendto(b'probe',(host,port));ok=s.recv(32)==b'probe'
        else:s.connect((host,port));ok=True
    except OSError:ok=False
    finally:s.close()
    assert ok==expected, (host,port,kind,source,expected,ok)
    print('PASS',host,port,kind,'allowed' if ok else 'blocked')
'''

try:
    for name in names.values():
        run("ip", "netns", "add", name)
        created.append(name)
        run("ip", "-n", name, "link", "set", "lo", "up")
    for role, interface, address, remote in (
        ("public", "eth0", "10.250.0.1/24", "10.250.0.2/24"),
        ("peer", "awg0", "10.78.0.1/24", "10.78.0.2/24"),
        ("container", "br-test", "172.18.0.1/24", "172.18.0.2/24"),
    ):
        run("ip", "-n", names["fw"], "link", "add", interface, "type", "veth", "peer", "name", "test0", "netns", names[role])
        run("ip", "-n", names["fw"], "addr", "add", address, "dev", interface)
        run("ip", "-n", names["fw"], "link", "set", interface, "up")
        run("ip", "-n", names[role], "addr", "add", remote, "dev", "test0")
        run("ip", "-n", names[role], "link", "set", "test0", "up")
        run("ip", "-n", names[role], "route", "add", "default", "via", address.split("/")[0])
    run("ip", "-n", names["peer"], "addr", "add", "10.78.0.3/24", "dev", "test0")
    run("ip", "-n", names["fw"], "-6", "addr", "add", "fd42:ace::1/64", "dev", "eth0", "nodad")
    run("ip", "-n", names["public"], "-6", "addr", "add", "fd42:ace::2/64", "dev", "test0", "nodad")
    ns("fw", "sysctl", "-qw", "net.ipv4.ip_forward=1")
    rules = Path(sys.argv[1]).read_text()
    ns("fw", "nft", "-f", "-", input=rules)
    # Prove the replace transaction works and does not accumulate rules.
    ns("fw", "nft", "-f", "-", input="delete table inet anicast_edge\n" + rules)
    # Model Docker's DNAT into a separate namespace. Later Docker filters can
    # only restrict further; they cannot undo drops in the Anicast chain.
    ns("fw", "nft", "-f", "-", input='''
table ip test_docker_nat {
 chain prerouting {
  type nat hook prerouting priority dstnat;
  ip daddr { 10.250.0.1, 10.78.0.1 } tcp dport { 3000, 9100 } dnat to 172.18.0.2
 }
}
''')
    for role, ports in (("fw", (22, 80, 443, 8443, 9099)), ("public", (8080,)), ("container", (3000, 9100))):
        servers.append(subprocess.Popen(["ip", "netns", "exec", names[role], sys.executable, "-c", listener, *map(str, ports)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE))
    time.sleep(0.8)
    cases = {
        "public": [("10.250.0.1", p, p in (22, 80, 443), "tcp", "") for p in (22, 80, 443, 8443, 9099, 3000, 9100)] + [("10.250.0.1", 443, True, "udp", ""), ("10.250.0.1", 444, False, "udp", "")],
        "peer": [("10.78.0.1", p, p in (22, 8443, 9100), "tcp", "") for p in (22, 8443, 9100, 3000, 9099)] + [("10.78.0.1", 9100, False, "tcp", "10.78.0.3")],
        "container": [("10.250.0.2", 8080, True, "tcp", "")],
        "fw": [("127.0.0.1", 9099, True, "tcp", "")],
    }
    cases["public"] += [("fd42:ace::1", p, p in (22, 80, 443), "tcp", "") for p in (22, 80, 443, 8443, 9099)]
    cases["peer"] += [("10.250.0.2", 8080, True, "tcp", ""), ("10.250.0.2", 8080, False, "tcp", "10.78.0.3")]
    for role, tests in cases.items():
        print(role + ":")
        print(ns(role, sys.executable, "-c", probe, json.dumps(tests)).stdout, end="")
    print("Firewall namespace tests passed; no production traffic or rules touched")
finally:
    for process in servers:
        process.terminate()
        process.wait(timeout=5)
    for name in reversed(created):
        subprocess.run(["ip", "netns", "del", name], check=True)
