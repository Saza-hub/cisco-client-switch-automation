#!/usr/bin/env python3
"""Generate IOS/IOS-XE switch configs, validate intent, and optionally deploy by SSH."""
import argparse
import datetime as dt
import difflib
import ipaddress
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'

def load(path):
    text = Path(path).read_text(encoding='utf-8')
    if path.endswith('.json'):
        return json.loads(text)
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit('Install dependencies: pip install -r requirements.txt') from exc
    return yaml.safe_load(text)

def name(s, desc='name'):
    if not isinstance(s, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,62}', s):
        raise ValueError(f'Invalid {desc}: {s!r}')
    return s

def ios_lines(profile):
    hostname = name(profile['hostname'], 'hostname')
    vlans = profile['vlans']
    if not isinstance(vlans, list) or not vlans:
        raise ValueError('At least one VLAN is required')
    ids = set()
    lines = ['! Generated switch configuration: REVIEW BEFORE USE', f'hostname {hostname}', 'no ip http server', 'no ip http secure-server', 'service password-encryption', '!']
    for v in vlans:
        vid = int(v['id'])
        if vid < 1 or vid > 4094 or vid in ids:
            raise ValueError('VLAN IDs must be unique and in 1..4094')
        ids.add(vid)
        lines += [f'vlan {vid}', f' name {name(v["name"], "VLAN name")}', ' exit']
    management = profile.get('management')
    if management:
        vid = int(management['vlan'])
        if vid not in ids:
            raise ValueError('Management VLAN must exist in vlans')
        addr = ipaddress.IPv4Interface(management['address'])
        gw = ipaddress.IPv4Address(management['gateway'])
        if gw not in addr.network:
            raise ValueError('Gateway must belong to management subnet')
        lines += [f'interface Vlan{vid}', ' description MANAGEMENT', f' ip address {addr.ip} {addr.network.netmask}', ' no shutdown', ' exit', f'ip default-gateway {gw}']
    interfaces = profile.get('interfaces', [])
    seen = set()
    for port in interfaces:
        iface = port['name']
        if not re.fullmatch(r'(?:GigabitEthernet|TenGigabitEthernet|FastEthernet|TwentyFiveGigE|FortyGigabitEthernet|HundredGigE|Ethernet)\d+(?:/\d+){1,3}', iface):
            raise ValueError(f'Invalid interface name: {iface}')
        if iface in seen:
            raise ValueError(f'Duplicate interface {iface}')
        seen.add(iface)
        desc = port.get('description', 'CLIENT_PORT')
        if not isinstance(desc, str) or not re.fullmatch(r'[A-Za-z0-9 _./-]{1,80}', desc):
            raise ValueError('Unsafe interface description')
        mode = port['mode']
        lines += [f'interface {iface}', f' description {desc}', ' switchport']
        if mode == 'access':
            vid = int(port['vlan'])
            if vid not in ids:
                raise ValueError(f'Unknown access VLAN {vid}')
            lines += [' switchport mode access', f' switchport access vlan {vid}', ' spanning-tree portfast', ' spanning-tree bpduguard enable']
        elif mode == 'trunk':
            allowed = [int(x) for x in port['allowed_vlans']]
            if not allowed or any(x not in ids for x in allowed):
                raise ValueError('Trunk VLANs must be nonempty and defined')
            native = int(port.get('native_vlan', 1))
            if native not in ids or native not in allowed:
                raise ValueError('Native VLAN must exist and be allowed')
            lines += [' switchport mode trunk', f' switchport trunk native vlan {native}', ' switchport trunk allowed vlan ' + ','.join(str(x) for x in sorted(set(allowed)))]
        else:
            raise ValueError('mode must be access or trunk')
        lines += [' no shutdown' if port.get('enabled', True) else ' shutdown', ' exit']
    lines.append('end')
    return '\n'.join(lines) + '\n'

def render(profile_path):
    profile = load(str(profile_path))
    if not isinstance(profile, dict):
        raise ValueError('Profile must contain a mapping')
    config = ios_lines(profile)
    return profile, config

def deployment(profile, config, inventory_path, approve, device_name):
    if not approve:
        raise SystemExit('Deployment blocked: pass --approve after reviewing generated output')
    try:
        from netmiko import ConnectHandler
    except ImportError:
        raise SystemExit('Missing netmiko: pip install -r requirements.txt')
    inventory = load(str(inventory_path))
    host = inventory.get(device_name)
    if not isinstance(host, dict):
        raise ValueError(f'Device {device_name!r} not found in inventory')
    address = host['host']
    ipaddress.ip_address(address)
    username = os.getenv('CISCO_USERNAME')
    password = os.getenv('CISCO_PASSWORD')
    secret = os.getenv('CISCO_ENABLE_SECRET')
    if not username or not password:
        raise SystemExit('Set CISCO_USERNAME and CISCO_PASSWORD as environment variables')
    kwargs = dict(device_type='cisco_ios', host=address, username=username, password=password, timeout=20)
    if secret:
        kwargs['secret'] = secret
    OUT.mkdir(exist_ok=True)
    with ConnectHandler(**kwargs) as conn:
        if secret:
            conn.enable()
        if conn.find_prompt() is None:
            raise RuntimeError('Switch prompt not detected')
        running = conn.send_command('show running-config', read_timeout=60)
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = OUT / f'{device_name}.{stamp}.running-config.txt'
        backup.write_text(running + '\n', encoding='utf-8')
        print(f'Backup created: {backup}')
        commands = [ln.strip() for ln in config.splitlines() if ln.strip() and not ln.startswith('!') and ln.strip() != 'end']
        result = conn.send_config_set(commands, error_pattern=r'% (?:Invalid input|Error|Incomplete command|Ambiguous command)')
        print(result)
        print('Review device state. Startup config NOT saved automatically.')

def main():
    ap = argparse.ArgumentParser(description='Cisco IOS/IOS-XE switch intent runner')
    ap.add_argument('command', choices=['validate', 'generate', 'deploy'])
    ap.add_argument('--profile', required=True, type=Path)
    ap.add_argument('--inventory', type=Path, default=ROOT / 'inventory' / 'devices.example.yaml')
    ap.add_argument('--device', help='Inventory alias; required for deploy')
    ap.add_argument('--approve', action='store_true', help='Acknowledge reviewed configuration for deploy')
    args = ap.parse_args()
    try:
        profile, config = render(args.profile)
        if args.command == 'validate':
            print(f'Valid: {profile["hostname"]} ({len(profile["interfaces"])} interfaces)')
        elif args.command == 'generate':
            OUT.mkdir(exist_ok=True)
            dest = OUT / (name(profile['hostname']) + '.cfg')
            dest.write_text(config, encoding='utf-8')
            print(f'Generated: {dest}')
        else:
            if not args.device:
                ap.error('--device is required for deploy')
            deployment(profile, config, args.inventory, args.approve, args.device)
    except (KeyError, TypeError, ValueError) as exc:
        ap.error(f'Invalid client profile: {exc}')

if __name__ == '__main__':
    main()
