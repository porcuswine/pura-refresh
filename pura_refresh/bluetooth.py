"""Explicit recovery for an idle Raspberry Pi Bluetooth adapter."""
import asyncio
import os
import re
import subprocess

async def recover_idle(adapter='hci0'):
    if os.geteuid() != 0:
        raise RuntimeError('Bluetooth recovery requires sudo.')
    if not re.fullmatch(r'hci\d+', adapter):
        raise ValueError('Invalid Bluetooth adapter.')
    from dbus_fast.aio import MessageBus
    from dbus_fast import BusType, Message, MessageType
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    try:
        reply = await bus.call(Message(destination='org.bluez', path='/',
            interface='org.freedesktop.DBus.ObjectManager', member='GetManagedObjects'))
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError('Could not inspect Bluetooth connections; refusing a reset.')
        prefix = '/org/bluez/' + adapter + '/'
        for path, interfaces in reply.body[0].items():
            props = interfaces.get('org.bluez.Device1', {})
            if path.startswith(prefix) and 'Connected' in props and props['Connected'].value:
                raise RuntimeError('Bluetooth has an active connection. Disconnect it before recovery.')
        # This was required on the test Pi when BlueZ discovery became stuck.
        # Do not restart unrelated services or reset a connected radio.
        subprocess.run(['hciconfig', adapter, 'reset'], check=True, capture_output=True, text=True)
    finally:
        bus.disconnect()
