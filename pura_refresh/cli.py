"""One installer for the two explicitly selected, tested board families."""
import argparse
import asyncio
import base64
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import ssl
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request

from .blufi import Blufi, scan
from .boards import BOARDS, get_board
from .image import load_image
from .network import AccessPoint, GATEWAY, TARGET, normalize_mac, restore
from .ota import Delivery, serve, IMAGE_PATH

RECOVERY_IP = '172.29.241.1'


def emit(message):
    print(message, flush=True)


def write_report(path, data):
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(data, stream, indent=2)
        stream.write('\n')


def status(target, expected_mac, expected_version):
    request = urllib.request.Request(f'http://{target}/status', headers={
        'Authorization': 'Basic ' + base64.b64encode(b'pura:pura-setup').decode()})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=3) as response:
        data = json.loads(response.read(16384))
    return data if (data.get('version') == expected_version and
                    data.get('mac', '').lower() == expected_mac.lower() and
                    data.get('heaters_off') is True) else None


def validate_device_info(info, board_name, wifi_mac, stock_version):
    board = get_board(board_name)
    if stock_version not in board.stock_versions:
        raise ValueError(f'Unsupported stock version for {board.name}; see the compatibility table.')
    if info['wifi_mac'] != normalize_mac(wifi_mac):
        raise ValueError('The device-reported Wi-Fi MAC differs from the selected MAC. No provisioning sent.')
    if info['hardware'] != board.hardware:
        raise ValueError('The device-reported hardware differs from the selected board. No provisioning sent.')
    family = '.'.join(stock_version.split('.')[:2])
    if info['software_family'] != family:
        raise ValueError('The device-reported software family differs from the selected stock version.')


def check_dns():
    labels = b''.join(bytes([len(x)]) + x.encode() for x in 'prod.api.purascents.com'.split('.')) + b'\0'
    packet = struct.pack('!6H', 0x5055, 0x100, 1, 0, 0, 0) + labels + struct.pack('!2H', 1, 1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(3)
        sock.sendto(packet, (GATEWAY, 53))
        reply = sock.recv(1024)
    if reply[:2] != b'PU' or socket.inet_aton(GATEWAY) not in reply:
        raise RuntimeError('Local updater DNS check failed. No Bluetooth provisioning sent.')


def network_self_test(cert, key):
    check_dns()
    delivery = Delivery(b'network-test', emit=lambda _: None)
    with serve(GATEWAY, GATEWAY, cert, key, delivery, port=0) as server:
        client = http.client.HTTPSConnection(GATEWAY, server.server_port,
            context=ssl._create_unverified_context(), timeout=3)
        try:
            client.request('GET', '/api/firmware/config')
            response = client.getresponse()
            if response.status != 200 or ('FILE=' + IMAGE_PATH).encode() not in response.read():
                raise RuntimeError('Local HTTPS self-test failed.')
        finally:
            client.close()
    emit('Isolated DHCP/DNS/HTTPS services started; DNS and HTTPS requests passed. No Pura commands sent.')


async def find_device(identifier, timeout=120):
    from bleak import BleakScanner
    device = await BleakScanner.find_device_by_address(identifier, timeout=timeout)
    if device is None:
        raise RuntimeError('Selected Pura not found. Use breathing-blue setup mode with its phone app disconnected.')
    return device


async def inspect_stock(identifier):
    from bleak import BleakClient
    device = await find_device(identifier, timeout=45)
    async with BleakClient(device, timeout=30) as client:
        protocol = Blufi(client, emit)
        await protocol.start()
        return await protocol.read_device_info()


async def worker(session):
    from bleak import BleakClient
    board = get_board(session['board'])
    blob, manifest = load_image(board.name)
    check_dns()
    delivery = Delivery(blob, armed=session['flash'], emit=emit, expected_model=board.model)
    with serve(GATEWAY, TARGET, session['cert'], session['key'], delivery):
        emit(f'Local updater ready for {board.title}. Finding the selected device…')
        device = await find_device(session['device'])
        protocol = None
        info_checked = False
        try:
            async with BleakClient(device, timeout=30) as client:
                protocol = Blufi(client, emit)
                await protocol.start()
                info = await protocol.read_device_info()
                validate_device_info(info, board.name, session['wifi_mac'], session['stock_version'])
                info_checked = True
                emit('Device-reported MAC, hardware and software family match. Provisioning temporary Wi-Fi.')
                await protocol.provision(session['ssid'], session['password'])
                await protocol.request_update()
        except Exception:
            # Stock can begin HTTPS as soon as Wi-Fi joins, then drop Bluetooth.
            # A failed identity check must never be turned into an update attempt.
            await asyncio.sleep(3)
            if not info_checked or not (delivery.config_requested.is_set() or
                                       (protocol and protocol.online.is_set())):
                raise
            emit('Bluetooth disconnected after Wi-Fi joined; continuing transfer/boot monitoring.')
        end = time.monotonic() + session['timeout']
        delivered_at = None
        handoff_requested = False
        while time.monotonic() < end:
            if delivery.model_mismatch.is_set():
                raise RuntimeError('Updater model headers did not match. Firmware delivery was refused.')
            if not session['flash'] and delivery.requested.is_set():
                emit('REHEARSAL PASSED: image requested; all firmware bytes withheld.')
                emit('Stock Wi-Fi was changed. Run flash next or use restore-wifi before leaving the device.')
                return 0
            if session['flash']:
                if delivery.delivered.is_set() and delivered_at is None:
                    delivered_at = time.monotonic()
                if delivered_at and time.monotonic() - delivered_at >= 8 and not handoff_requested:
                    Path(session['directory'], 'handoff.request').touch()
                    handoff_requested = True
                if Path(session['directory'], 'handoff.ready').exists():
                    try:
                        info = await asyncio.to_thread(status, RECOVERY_IP,
                                                       session['wifi_mac'], manifest['version'])
                    except (OSError, ValueError, urllib.error.URLError):
                        info = None
                    if info:
                        ready = (info.get('layout_compatible') is True and
                                 info.get('settings_available') is True and
                                 (board.name != 'v3' or info.get('hardware') == 'pura-v3'))
                        write_report(session['report'], dict(
                            result='boot_verified' if ready else 'booted_not_ready',
                            board=board.name, device_mac=session['wifi_mac'],
                            firmware=manifest['sha256'], status=info))
                        if not ready:
                            raise RuntimeError('New firmware booted but settings/layout checks failed. Diagnostic report saved.')
                        emit(f'BOOT VERIFIED: {info["name"]} is running {manifest["version"]}.')
                        emit(f'Join {info["name"]} Wi-Fi (password pura-setup), then open http://{RECOVERY_IP}.')
                        emit('Sign in as pura / pura-setup. Enter home Wi-Fi and choose a new device password.')
                        return 0
            await asyncio.sleep(2)
        if delivery.delivered.is_set():
            raise RuntimeError('Image delivered, but boot NOT verified. Check recovery Wi-Fi; do not repeat blindly.')
        raise RuntimeError('No completed transfer before timeout. Stock Wi-Fi may have changed; inspect before retrying.')


def validate_selection(board_name, stock_version):
    board = get_board(board_name)
    if stock_version not in board.stock_versions:
        raise ValueError(f'Unsupported stock version for {board_name}; supported: {", ".join(board.stock_versions)}')
    load_image(board_name)  # Validate before any network or device changes.
    return board


def start_session(args):
    board = validate_selection(args.board, args.stock_version)
    wifi_mac = normalize_mac(args.wifi_mac)
    with AccessPoint(args.interface, wifi_mac, emit) as ap:
        session = dict(board=board.name, stock_version=args.stock_version,
            device=args.device, wifi_mac=wifi_mac, ssid=ap.ssid, password=ap.password,
            flash=args.command == 'flash', timeout=args.timeout,
            cert=str(ap.directory / 'cert.pem'), key=str(ap.directory / 'key.pem'),
            directory=str(ap.directory), report=str(Path(args.report).resolve()))
        plan = ap.directory / 'session.json'
        plan.write_text(json.dumps(session))
        plan.chmod(0o600)
        child = subprocess.Popen(['ip', 'netns', 'exec', ap.namespace, sys.executable,
                                  '-m', 'pura_refresh.cli', '_worker', '--session', str(plan)])
        try:
            while child.poll() is None:
                if (ap.directory / 'handoff.request').exists() and not (ap.directory / 'handoff.ready').exists():
                    ap.connect_recovery('Pura-Setup-' + wifi_mac.replace(':', '')[-4:].upper())
                    (ap.directory / 'handoff.ready').touch()
                ap.check()
                time.sleep(.5)
            return child.returncode
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


def wizard(args):
    emit('pura-refresh — V2 and V3 first-flash installer')
    emit('Keep the Pura assembled. Close its phone app, turn phone Bluetooth off, and use breathing-blue setup mode.')
    emit('Installation changes the selected device’s Wi-Fi and replaces its application. Recovery can require UART.')
    for name, board in BOARDS.items():
        emit(f'{name}: {board.title}, tested hardware {board.hardware}')
    args.board = input('Board (v2 or v3): ').strip().lower()
    board = get_board(args.board)
    found = asyncio.run(scan())
    if not found:
        raise RuntimeError('No stock Pura advertised. See the Bluetooth troubleshooting instructions.')
    for index, (device, advertisement) in enumerate(found, 1):
        emit(f'{index}. {advertisement.local_name or device.name}  [{device.address}]')
    number = int(input('Device number: '))
    if not 1 <= number <= len(found):
        raise ValueError('Invalid device number.')
    args.device = found[number - 1][0].address
    info = asyncio.run(inspect_stock(args.device))
    args.wifi_mac = info['wifi_mac']
    args.stock_version = info['software_family']
    validate_device_info(info, board.name, args.wifi_mac, args.stock_version)
    emit(f'Device reports hardware {info["hardware"]}, software family {args.stock_version}, Wi-Fi MAC {args.wifi_mac}.')
    args.command = input('Mode (rehearse or flash): ').strip().lower()
    if args.command not in ('rehearse', 'flash'):
        raise ValueError('Choose rehearse or flash.')
    args.timeout, args.report = 360, 'pura-refresh-report.json'
    return start_session(args)


async def restore_wifi(args):
    import getpass
    from bleak import BleakClient
    ssid = input('Original Wi-Fi name (up to 16 UTF-8 bytes): ')
    password = getpass.getpass('Original Wi-Fi password (8–16 bytes): ')
    device = await find_device(args.device, timeout=45)
    async with BleakClient(device, timeout=30) as client:
        protocol = Blufi(client, emit)
        await protocol.start()
        await protocol.provision(ssid, password)


def main():
    os.environ['PATH'] = os.environ.get('PATH', '') + ':/usr/sbin:/sbin'
    parser = argparse.ArgumentParser(description='pura-refresh: standalone Pi installer for tested Pura V2 and V3 hardware.')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('scan', help='List Pura Bluetooth advertisements; no device writes')
    p = sub.add_parser('inspect', help='Query stock Wi-Fi MAC, hardware and software family; no settings changes')
    p.add_argument('--device', required=True)
    p = sub.add_parser('wizard', help='Select a board/device and install interactively')
    p.add_argument('--interface', default='wlan0')
    sub.add_parser('images', help='Validate and list the two bundled firmware images')
    sub.add_parser('recover', help='Restore Pi Wi-Fi after an interrupted installer session')
    p = sub.add_parser('bluetooth-recover', help='Reset an idle Bluetooth controller; refuses active connections')
    p.add_argument('--adapter', default='hci0')
    p = sub.add_parser('network-test', help='Check isolated AP services; no device commands')
    p.add_argument('--wifi-mac', required=True)
    p.add_argument('--interface', default='wlan0')
    p = sub.add_parser('restore-wifi', help='Restore stock Wi-Fi after rehearsal; prompts privately')
    p.add_argument('--device', required=True)
    for command in ('rehearse', 'flash'):
        p = sub.add_parser(command, help=f'{command.title()} one explicitly selected stock device')
        p.add_argument('--device', required=True, help='Exact identifier printed by scan')
        p.add_argument('--wifi-mac', required=True, help='Device-reported Wi-Fi MAC, not its Bluetooth address')
        p.add_argument('--board', required=True, choices=list(BOARDS))
        p.add_argument('--stock-version', required=True, help='Version from app, or major.minor family from inspect')
        p.add_argument('--interface', default='wlan0')
        p.add_argument('--timeout', type=int, default=360, choices=range(30, 901), metavar='30..900')
        p.add_argument('--report', default='pura-refresh-report.json')
    p = sub.add_parser('_worker', help=argparse.SUPPRESS)
    p.add_argument('--session', type=Path, required=True)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        if args.command == 'images':
            for name in BOARDS:
                _, manifest = load_image(name)
                emit(f'{name}: {manifest["version"]}, {manifest["bytes"]} bytes, SHA256 {manifest["sha256"]}')
            return 0
        if args.command == 'scan':
            for device, advertisement in asyncio.run(scan()):
                emit(f'{device.address}  {advertisement.local_name or device.name or "Pura"}')
            return 0
        if args.command == 'inspect':
            emit(json.dumps(asyncio.run(inspect_stock(args.device)), indent=2))
            return 0
        if args.command == 'wizard':
            return wizard(args)
        if args.command == 'recover':
            restore()
            return 0
        if args.command == 'bluetooth-recover':
            from .bluetooth import recover_idle
            asyncio.run(recover_idle(args.adapter))
            emit('Idle Bluetooth controller reset. Run scan again.')
            return 0
        if args.command == 'network-test':
            with AccessPoint(args.interface, args.wifi_mac, emit) as ap:
                result = ap.inside(sys.executable, '-c',
                    'import sys; from pura_refresh.cli import network_self_test; network_self_test(*sys.argv[1:])',
                    str(ap.directory / 'cert.pem'), str(ap.directory / 'key.pem'))
                emit(result.stdout.strip())
            return 0
        if args.command == 'restore-wifi':
            asyncio.run(restore_wifi(args))
            return 0
        if args.command == '_worker':
            return asyncio.run(worker(json.loads(args.session.read_text())))
        return start_session(args)
    except KeyboardInterrupt:
        emit('Stopped. If network cleanup was interrupted, run pura-refresh recover.')
        return 130
    except Exception as error:
        emit(f'Installer stopped: {type(error).__name__}: {error}')
        emit('If Bluetooth discovery is busy, close other Bluetooth tools; see bluetooth-recover and docs/troubleshooting.md.')
        return 1


if __name__ == '__main__':
    sys.exit(main())
