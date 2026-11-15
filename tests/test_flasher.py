import asyncio
import http.client
import json
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch, MagicMock

from pura_refresh.blufi import Blufi, frame, parse_frame, SERVICE, WRITE, NOTIFY
from pura_refresh.image import load_image, inspect_image
from pura_refresh.network import configs, normalize_mac
from pura_refresh.ota import Delivery, IMAGE_PATH, serve
from pura_refresh.cli import status

IMAGES=Path(__file__).resolve().parents[1]/'pura_refresh'/'images'


class ProtocolTest(unittest.IsolatedAsyncioTestCase):
    async def test_provision_and_update_order(self):
        packets=[]
        class Characteristic:
            properties=['write']
        class Service:
            def get_characteristic(self,uuid): return Characteristic()
        class Services:
            def get_service(self,uuid): return Service() if uuid==SERVICE else None
        class Client:
            services=Services()
            async def start_notify(self,rx,callback): self.callback=callback
            async def write_gatt_char(self,tx,packet,response):
                packets.append(packet)
                if packet[0]==0x1c: self.callback(None,bytes.fromhex('410400020102'))
                else:
                    self.callback(None,bytes([0,4,0,1,packet[2]]))
                    if packet[0]==0x0c: self.callback(None,bytes.fromhex('3d040003010000'))
        protocol=Blufi(Client(),lambda _:None)
        await protocol.start()
        await protocol.provision('Pura-12345678','0123456789abcdef')
        await protocol.request_update()
        self.assertEqual(packets[0],bytes.fromhex('1c000000'))
        self.assertEqual([p[0] for p in packets],[0x1c,8,9,13,12,20,77])
        self.assertEqual([p[2] for p in packets],list(range(7)))
        self.assertEqual(packets[-1],bytes.fromhex('4d0806011c'))

    async def test_malformed_notifications_and_mtu(self):
        for packet in (b'',bytes.fromhex('4104000201'),bytes.fromhex('411400020102')):
            self.assertIsNone(parse_frame(packet))
        with self.assertRaises(ValueError): frame(9,0,b'x'*17)


class ImageAndNetworkTest(unittest.TestCase):
    def test_packaged_image_and_corruption(self):
        blob,m=load_image('v2')
        self.assertLess(len(blob),0x12c000)
        broken=bytearray(blob); broken[200]^=1
        with self.assertRaises(ValueError): inspect_image(broken, 'v2')
        with self.assertRaises(ValueError): inspect_image(b'\xff'*0x1000+blob, 'v2')

    def test_missing_bootloader_compatibility_proof_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)
            blob,m=load_image('v2')
            (p/'application.bin').write_bytes(blob)
            m.pop('startup_hook_order_checked')
            (p/'manifest.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'compatibility hook'):
                load_image('v2', p)

    def test_wrong_device_or_version_never_confirms_boot(self):
        for response in ({'mac':'aa:bb:cc:dd:ee:00','version':'pura-setup-3','heaters_off':True},
                         {'mac':'aa:bb:cc:dd:ee:ff','version':'stock','heaters_off':True},
                         {'mac':'aa:bb:cc:dd:ee:ff','version':'pura-setup-3','heaters_off':False}):
            opener=MagicMock()
            opener.open.return_value.__enter__.return_value.read.return_value=json.dumps(response).encode()
            with patch('pura_refresh.cli.urllib.request.build_opener',return_value=opener):
                self.assertIsNone(status('172.29.241.1','aa:bb:cc:dd:ee:ff','pura-setup-3'))

    def test_legacy_bootloader_memory_limits(self):
        blob,_=load_image('v2')
        changed=bytearray(blob)
        changed[24:28]=(0x400a0000).to_bytes(4,'little')
        with self.assertRaisesRegex(ValueError,'memory regions'): inspect_image(changed, 'v2')

    def test_closed_network_configuration(self):
        ap,dns=configs('wlan0','Pura-test','0123456789abcdef','02:00:00:00:00:01')
        self.assertIn('wpa=2',ap)
        self.assertIn('max_num_sta=1',ap)
        self.assertIn('dhcp-ignore=tag:!pura',dns)
        self.assertIn('dhcp-host=02:00:00:00:00:01',dns)
        self.assertIn('no-resolv',dns)
        self.assertIn('local=/api.purascents.com/',dns)
        self.assertNotIn('server=',dns)
        with self.assertRaises(ValueError): configs('wlan0\nother=1','test','password1','aa:bb:cc:dd:ee:ff')
        with self.assertRaises(ValueError): normalize_mac('not-a-mac')


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.cert=Path(cls.tmp.name)/'cert.pem'; cls.key=Path(cls.tmp.name)/'key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                        '-subj','/CN=localhost','-keyout',str(cls.key),'-out',str(cls.cert)],
                       check=True,capture_output=True)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def request(self,port,path,headers=None):
        client=http.client.HTTPSConnection('127.0.0.1',port,context=ssl._create_unverified_context(),timeout=3)
        try:
            client.request('GET',path,headers=headers or {})
            response=client.getresponse()
            return response.status,response.read()
        finally: client.close()

    def test_rehearsal_never_sends_firmware(self):
        d=Delivery(b'example-image',emit=lambda _:None)
        with serve('127.0.0.1','127.0.0.1',self.cert,self.key,d,port=0) as server:
            port=server.server_port
            code,body=self.request(port,'/api/firmware/config')
            self.assertEqual(code,200)
            self.assertIn(b'SIZE=13',body)
            self.assertEqual(self.request(port,IMAGE_PATH),(503,b''))
            self.assertEqual(self.request(port,'/../../etc/passwd'),(503,b''))
        self.assertTrue(d.requested.is_set())
        self.assertFalse(d.delivered.is_set())

    def test_armed_serves_once_and_denies_other_sources(self):
        d=Delivery(b'image',armed=True,emit=lambda _:None)
        with serve('127.0.0.1','127.0.0.1',self.cert,self.key,d,port=0) as server:
            self.assertEqual(self.request(server.server_port,IMAGE_PATH),(200,b'image'))
            self.assertEqual(self.request(server.server_port,IMAGE_PATH),(503,b''))
        self.assertTrue(d.delivered.is_set())
        d=Delivery(b'image',armed=True,emit=lambda _:None)
        with serve('127.0.0.1','127.0.0.2',self.cert,self.key,d,port=0) as server:
            with self.assertRaises((OSError,ssl.SSLError)):
                self.request(server.server_port,IMAGE_PATH)
        self.assertFalse(d.requested.is_set())


class BoardIdentityTest(unittest.TestCase):
    def test_images_cannot_cross_boards(self):
        for board, other in [('v2', 'v3'), ('v3', 'v2')]:
            blob, manifest = load_image(board)
            self.assertEqual(inspect_image(blob, board)['sha256'], manifest['sha256'])
            with self.assertRaises(ValueError): inspect_image(blob, other)

    def test_metadata_ignores_undefined_legacy_bytes(self):
        from pura_refresh.blufi import device_info
        from pura_refresh.cli import validate_device_info
        prefix = bytes.fromhex('000200000000010201020a')
        for tail in [bytes(3), bytes.fromhex('ffffff')]:
            info = device_info(prefix + tail)
            self.assertEqual(info, {'wifi_mac': '02:00:00:00:00:01', 'hardware': '2.1', 'software_family': '2.10'})
            validate_device_info(info, 'v2', '02:00:00:00:00:01', '2.10')
            for board, mac, version in [('v3', info['wifi_mac'], '2.7'), ('v2', '02:00:00:00:00:02', '2.10'), ('v2', info['wifi_mac'], '2.9')]:
                with self.assertRaises(ValueError): validate_device_info(info, board, mac, version)
        self.assertIsNone(device_info(bytes(14)))

    def test_report_is_private_and_does_not_follow_symlinks(self):
        from pura_refresh.cli import write_report
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            write_report(path, {'ok': True})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            link = Path(directory) / 'link.json'
            link.symlink_to(path)
            with self.assertRaises(OSError): write_report(link, {})

class ModelGateTest(ServerTest):
    def test_wrong_or_missing_model_never_receives_image(self):
        for model in ['v2', 'v3l']:
            d=Delivery(b'image',armed=True,emit=lambda _:None,expected_model=model)
            with serve('127.0.0.1','127.0.0.1',self.cert,self.key,d,port=0) as server:
                self.assertEqual(self.request(server.server_port,IMAGE_PATH),(503,b''))
                self.assertEqual(self.request(server.server_port,IMAGE_PATH, {'pura-device-version':'wrong','pura-device-type':'dual-wall'}),(503,b''))
                self.assertFalse(d.delivered.is_set())
                self.assertEqual(self.request(server.server_port,IMAGE_PATH, {'pura-device-version':model,'pura-device-type':'dual-wall'}),(200,b'image'))

if __name__=='__main__': unittest.main()
