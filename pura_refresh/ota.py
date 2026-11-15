"""Isolated HTTPS endpoint implementing only the traced stock updater protocol."""
import contextlib
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

IMAGE_PATH='/pura-setup.bin'


class Delivery:
    def __init__(self, blob, host='prod.api.purascents.com', armed=False, emit=print, expected_model=None):
        self.blob,self.armed,self.emit=blob,armed,emit
        self.expected_model=expected_model
        self.model_mismatch=threading.Event()
        self.config=(f'INTERVAL=3600\r\nVERSION=2147483646\r\nSIZE={len(blob)}\r\n'
                     f'FILE={IMAGE_PATH}\r\nHOST={host}\r\n').encode('ascii')
        self.requested=threading.Event()
        self.config_requested=threading.Event()
        self.delivered=threading.Event()
        self.lock=threading.Lock()
        self.attempts=0


def handler_for(delivery):
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'

        def reply(self,status,body,content='text/plain'):
            self.send_response(status)
            self.send_header('Content-Type',content)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Connection','close')
            self.end_headers()
            for offset in range(0,len(body),16384):
                self.wfile.write(body[offset:offset+16384])
            self.wfile.flush()
            self.close_connection=True

        def do_GET(self):
            path=self.path.split('?',1)[0]
            if delivery.expected_model is not None and (
                    self.headers.get('pura-device-version') != delivery.expected_model or
                    self.headers.get('pura-device-type') != 'dual-wall'):
                delivery.model_mismatch.set()
                delivery.emit('Updater model headers do not match the selected board; refusing firmware delivery.')
                self.reply(503,b'')
                return
            try:
                if path=='/api/firmware/config':
                    delivery.config_requested.set()
                    delivery.emit('Stock updater requested local configuration.')
                    self.reply(200,delivery.config)
                elif path==IMAGE_PATH:
                    delivery.requested.set()
                    if not delivery.armed:
                        delivery.emit('Rehearsal succeeded: image requested, firmware bytes withheld.')
                        self.reply(503,b'')
                    elif not delivery.lock.acquire(blocking=False):
                        self.reply(503,b'')
                    else:
                        try:
                            if delivery.delivered.is_set() or delivery.attempts>=3:
                                self.reply(503,b'')
                                return
                            delivery.attempts+=1
                            delivery.emit(f'Pura requested the application image; transferring {len(delivery.blob)} bytes.')
                            self.reply(200,delivery.blob,'application/octet-stream')
                            delivery.delivered.set()
                            delivery.emit('Application image sent. Waiting for the new firmware to boot.')
                        finally:
                            delivery.lock.release()
                else:
                    self.reply(503,b'')
            except (BrokenPipeError, ConnectionResetError, TimeoutError, ssl.SSLError):
                delivery.emit('Transfer interrupted; at most three download attempts are allowed.')

        def do_POST(self):
            self.reply(503,b'')

        def log_message(self,*unused):
            pass # Never print arbitrary URLs, bodies or credentials.
    return Handler


class RestrictedTLS(ThreadingHTTPServer):
    daemon_threads=True

    def __init__(self,address,handler,context,target):
        self.context,self.target=context,target
        super().__init__(address,handler)

    def get_request(self):
        raw,addr=self.socket.accept()
        if addr[0]!=self.target:
            raw.close()
            raise ConnectionAbortedError('Non-target source')
        raw.settimeout(12)
        return raw,addr

    def finish_request(self,request,client_address):
        try:
            with self.context.wrap_socket(request,server_side=True) as tls:
                self.RequestHandlerClass(tls,client_address,self)
        except (OSError,ssl.SSLError):
            request.close()

    def handle_error(self,request,client_address):
        pass


@contextlib.contextmanager
def serve(bind,target,cert,key,delivery,port=443):
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert,key)
    server=RestrictedTLS((bind,port),handler_for(delivery),context,target)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
