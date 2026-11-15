"""Small, deliberately restricted BluFi client. No heater or arbitrary command API."""
import asyncio

SERVICE = "0000ffff-0000-1000-8000-00805f9b34fb"
WRITE = "0000ff01-0000-1000-8000-00805f9b34fb"
NOTIFY = "0000ff02-0000-1000-8000-00805f9b34fb"


def frame(kind, sequence, payload=b"", ack=True):
    if len(payload)>16:
        raise ValueError("This client only sends single-MTU payloads (16 bytes maximum).")
    return bytes([kind, 8 if ack else 0, sequence, len(payload)])+payload


def parse_frame(raw):
    if len(raw)<4 or len(raw)!=4+raw[3] or raw[1]&0x13:
        # No encryption, checksum, or fragmented response is interpreted by this client.
        return None
    return raw[0], raw[2], raw[4:]


def device_info(payload):
    # Stock command 0 returns: command, Wi-Fi MAC[6], hardware[2], software[2],
    # then additional bytes. Ignore undefined trailing bytes in legacy builds.
    if len(payload) != 14 or payload[0] != 0:
        return None
    mac = payload[1:7]
    if mac in (bytes(6), b'\xff' * 6) or mac[0] & 1:
        return None
    return {
        'wifi_mac': ':'.join(f'{value:02x}' for value in mac),
        'hardware': f'{payload[7]}.{payload[8]}',
        'software_family': f'{payload[9]}.{payload[10]}',
    }


class Blufi:
    def __init__(self, client, emit=print):
        self.client, self.emit = client, emit
        self.sequence = 0
        self.acks = {}
        self.version = asyncio.Event()
        self.online = asyncio.Event()
        self.version_value = None
        self.info_event = asyncio.Event()
        self.info = None

    async def start(self):
        service = self.client.services.get_service(SERVICE)
        if service is None:
            raise RuntimeError("Pura did not expose BluFi. Hold its setup button until the nightlight breathes blue; keep phone Bluetooth off.")
        self.tx, self.rx = service.get_characteristic(WRITE), service.get_characteristic(NOTIFY)
        if self.tx is None or self.rx is None:
            raise RuntimeError("BluFi characteristics are missing. No writes sent.")
        self.with_response = "write" in self.tx.properties
        await self.client.start_notify(self.rx, self.notified)
        await self.send(0x1c, ack=False)
        await asyncio.wait_for(self.version.wait(), 10)
        if self.version_value != b"\x01\x02":
            raise RuntimeError("Untested BluFi protocol version. No provisioning or update command sent.")

    def notified(self, _, data):
        parsed = parse_frame(bytes(data))
        if parsed is None:
            return
        kind, _, payload = parsed
        if kind==0 and len(payload)==1 and payload[0] in self.acks:
            self.acks[payload[0]].set()
        elif kind==0x41 and len(payload)==2:
            self.version_value=payload
            self.version.set()
        elif kind==0x3d and len(payload)>=3 and payload[1]==0:
            self.online.set()
        elif kind==0x4d:
            info = device_info(payload)
            if info:
                self.info = info
                self.info_event.set()
        elif kind==0x49:
            self.emit("The Pura reported a Bluetooth protocol error.")

    async def send(self, kind, payload=b"", ack=True):
        seq=self.sequence
        self.sequence=(seq+1)%256
        event=asyncio.Event()
        if ack:
            self.acks[seq]=event
        try:
            await self.client.write_gatt_char(self.tx, frame(kind, seq, payload, ack), response=self.with_response)
            if ack:
                await asyncio.wait_for(event.wait(), 10)
        finally:
            self.acks.pop(seq, None)

    async def provision(self, ssid, password):
        # Keep packet payloads inside the default BLE ATT MTU; no fragmented credential frames.
        if not 1<=len(ssid.encode())<=16 or not 8<=len(password.encode())<=16:
            raise ValueError("Installer SSID must be 1–16 bytes; password 8–16 bytes.")
        await self.send(0x08, b"\x01")
        await self.send(0x09, ssid.encode())
        await self.send(0x0d, password.encode())
        await self.send(0x0c)
        for _ in range(15):
            await asyncio.sleep(2)
            await self.send(0x14)
            if self.online.is_set():
                self.emit("Pura reports a Wi-Fi connection. Waiting for the local firmware check.")
                return
        raise RuntimeError("Pura did not report a Wi-Fi connection. Check the temporary access point.")

    async def read_device_info(self):
        await self.send(0x4d, b"\x00")
        await asyncio.wait_for(self.info_event.wait(), 10)
        return self.info

    async def request_update(self):
        await self.send(0x4d, b"\x1c")
        self.emit("Update-check command acknowledged; this alone does not confirm flashing.")


async def scan(timeout=10):
    from bleak import BleakScanner
    found=await BleakScanner.discover(timeout=timeout, return_adv=True)
    return [(d, a) for d,a in found.values()
            if SERVICE in [u.lower() for u in a.service_uuids] or (a.local_name or d.name or "").startswith("Pura-")]
