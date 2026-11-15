"""Temporary, isolated Wi-Fi radio namespace; no router rules, NAT or global DNS edits."""
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import time

GATEWAY='192.168.88.1'
TARGET='192.168.88.2'
JOURNAL=Path('/run/pura-refresh-recovery.json')


def run(*args,check=True):
    return subprocess.run(args,check=check,capture_output=True,text=True)


def normalize_mac(value):
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',value):
        raise ValueError('Enter the Pura Wi-Fi MAC as six colon-separated hex bytes.')
    return value.lower()


def configs(interface,ssid,password,wifi_mac):
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,15}',interface): raise ValueError('Invalid interface name')
    if not re.fullmatch(r'[a-zA-Z0-9-]{1,16}',ssid): raise ValueError('Invalid installer SSID')
    if not re.fullmatch(r'[a-zA-Z0-9]{8,16}',password): raise ValueError('Invalid installer password')
    mac=normalize_mac(wifi_mac)
    hostapd=(f'interface={interface}\ndriver=nl80211\nssid={ssid}\nhw_mode=g\nchannel=6\n'
             'wmm_enabled=1\nauth_algs=1\nwpa=2\nwpa_key_mgmt=WPA-PSK\nrsn_pairwise=CCMP\n'
             f'wpa_passphrase={password}\nmax_num_sta=1\nap_isolate=1\n')
    dnsmasq=(f'interface={interface}\nbind-interfaces\nlisten-address={GATEWAY}\n'
             'no-resolv\nno-hosts\ndhcp-authoritative\n'
             'dhcp-range=192.168.88.0,static,255.255.255.0,10m\n'
             f'dhcp-host={mac},set:pura,{TARGET}\ndhcp-ignore=tag:!pura\n'
             f'dhcp-option=3,{GATEWAY}\ndhcp-option=6,{GATEWAY}\n'
             f'address=/api.purascents.com/{GATEWAY}\nlocal=/api.purascents.com/\n')
    return hostapd,dnsmasq


def restore(journal=JOURNAL):
    if not journal.exists(): return
    state=json.loads(journal.read_text())
    ns,phy,interface=state['namespace'],state['phy'],state['interface']
    # A namespace may remain after an interrupted run. Do not delete it while it holds the radio.
    if not re.fullmatch(r'pura-refresh-[0-9a-f]{8}',ns) or not re.fullmatch(r'phy\d+',phy) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,14}',interface):
        raise RuntimeError('Recovery journal has invalid identifiers; inspect it manually.')
    namespaces=run('ip','netns','list').stdout.splitlines()
    if any(line.split()[0]==ns for line in namespaces):
        for pid in run('ip','netns','pids',ns).stdout.split():
            if pid.isdigit(): run('kill','-TERM',pid,check=False)
        time.sleep(.3)
        # PID 1 remains in the host network namespace, including after this installer dies.
        result=run('ip','netns','exec',ns,'iw','phy',phy,'set','netns','1',check=False)
        if result.returncode and not Path(f'/sys/class/ieee80211/{phy}').exists():
            raise RuntimeError('Could not restore Wi-Fi radio. Recovery journal and namespace retained.')
        run('ip','netns','delete',ns)
    if state.get('managed'):
        run('nmcli','device','set',interface,'managed','yes')
        if state.get('connection') and state['connection']!='--':
            run('nmcli','connection','up','uuid',state['connection'],check=False)
    journal.unlink()


class AccessPoint:
    def __init__(self,interface,wifi_mac,emit=print):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,14}',interface):
            raise ValueError('Invalid Wi-Fi interface name')
        self.interface,self.wifi_mac,self.emit=interface,normalize_mac(wifi_mac),emit
        self.namespace='pura-refresh-'+secrets.token_hex(4)
        self.ssid='Pura-'+secrets.token_hex(4)
        self.password=secrets.token_hex(8)
        self.processes=[]
        self.directory=None

    def __enter__(self):
        if os.geteuid()!=0: raise RuntimeError('The isolated access point must run with sudo.')
        for binary in ('ip','iw','hostapd','dnsmasq','nmcli','openssl','wpa_supplicant'):
            if not shutil.which(binary): raise RuntimeError(f'Missing dependency: {binary}. Run install-pi.sh first.')
        if JOURNAL.exists(): raise RuntimeError('An earlier session needs cleanup: sudo pura-refresh recover')
        radio=Path('/sys/class/net')/self.interface/'phy80211'
        if not radio.exists(): raise RuntimeError('Selected interface is not a Wi-Fi radio.')
        self.phy=radio.resolve().name
        if not re.fullmatch(r'phy\d+',self.phy): raise RuntimeError('Unexpected Wi-Fi radio identifier')
        siblings=list((radio.resolve()/'device'/'net').glob('*'))
        if len(siblings)>1: raise RuntimeError('Radio has multiple interfaces; use a dedicated Wi-Fi adapter.')
        ssh_peer=os.environ.get('SSH_CONNECTION','').split()
        if ssh_peer:
            route=run('ip','route','get',ssh_peer[0]).stdout.split()
            if 'dev' in route and route[route.index('dev')+1]==self.interface:
                raise RuntimeError('SSH is using this Wi-Fi interface. Connect Ethernet before starting.')
        managed=run('nmcli','-g','GENERAL.NM-MANAGED','device','show',self.interface).stdout.strip()=='yes'
        connection=run('nmcli','-g','GENERAL.CON-UUID','device','show',self.interface).stdout.strip()
        state=dict(namespace=self.namespace,phy=self.phy,interface=self.interface,managed=managed,connection=connection)
        # Write rollback instructions before changing any network state.
        fd=os.open(JOURNAL,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f: json.dump(state,f)
        try:
            self.directory=Path(tempfile.mkdtemp(prefix='pura-refresh-',dir='/run'))
            if managed: run('nmcli','device','set',self.interface,'managed','no')
            run('ip','netns','add',self.namespace)
            run('iw','phy',self.phy,'set','netns','name',self.namespace)
            self.inside('ip','link','set','lo','up')
            self.inside('ip','address','add',GATEWAY+'/24','dev',self.interface)
            self.inside('ip','link','set',self.interface,'up')
            ap,dns=configs(self.interface,self.ssid,self.password,self.wifi_mac)
            for name,body in [('hostapd.conf',ap),('dnsmasq.conf',dns)]:
                path=self.directory/name
                path.write_text(body)
                path.chmod(0o600)
            run('openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2',
                '-subj','/CN=prod.api.purascents.com','-addext','subjectAltName=DNS:prod.api.purascents.com',
                '-keyout',str(self.directory/'key.pem'),'-out',str(self.directory/'cert.pem'))
            (self.directory/'key.pem').chmod(0o600)
            self.spawn('hostapd',str(self.directory/'hostapd.conf'))
            self.spawn('dnsmasq','--keep-in-foreground','--conf-file='+str(self.directory/'dnsmasq.conf'),
                       '--dhcp-leasefile='+str(self.directory/'leases'),'--pid-file=')
            time.sleep(2)
            self.check()
            self.emit('Isolated installation Wi-Fi is running. Existing LAN and DNS services remain separate.')
            return self
        except BaseException:
            self.__exit__(None,None,None)
            raise

    def inside(self,*args):
        return run('ip','netns','exec',self.namespace,*args)

    def spawn(self,*args):
        log=(self.directory/'services.log').open('ab')
        try:
            p=subprocess.Popen(['ip','netns','exec',self.namespace,*args],stdout=log,stderr=log)
        finally:
            log.close()
        self.processes.append(p)
        return p

    def check(self):
        if any(p.poll() is not None for p in self.processes):
            raise RuntimeError('An access-point service exited. Inspect services.log before retrying.')

    def connect_recovery(self,ssid):
        if not re.fullmatch(r'Pura-Setup-[0-9A-F]{4}',ssid): raise ValueError('Invalid recovery SSID')
        self.emit('Switching the isolated radio to the Pura recovery Wi-Fi for boot verification.')
        for p in self.processes:
            if p.poll() is None:
                p.terminate()
                try: p.wait(timeout=3)
                except subprocess.TimeoutExpired: p.kill(); p.wait()
        self.processes=[]
        self.inside('ip','link','set',self.interface,'down')
        self.inside('ip','address','flush','dev',self.interface)
        self.inside('iw','dev',self.interface,'set','type','managed')
        self.inside('ip','address','add','172.29.241.200/24','dev',self.interface)
        self.inside('ip','link','set',self.interface,'up')
        path=self.directory/'recovery.conf'
        path.write_text(f'ctrl_interface={self.directory}/wpa\nupdate_config=0\nnetwork={{\n'
                        f' ssid="{ssid}"\n psk="pura-setup"\n key_mgmt=WPA-PSK\n scan_ssid=1\n}}\n')
        path.chmod(0o600)
        self.spawn('wpa_supplicant','-Dnl80211','-i',self.interface,'-c',str(path))
        time.sleep(1)
        self.check()

    def __exit__(self,*unused):
        for p in self.processes:
            if p.poll() is None:
                p.terminate()
                try: p.wait(timeout=3)
                except subprocess.TimeoutExpired: p.kill(); p.wait()
        restore()
        if self.directory: shutil.rmtree(self.directory)
        self.emit('Temporary network removed; previous Wi-Fi management restored.')
