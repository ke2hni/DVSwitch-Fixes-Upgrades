#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Version: 1.0.1
# Created: 2026-11-11T16:20:00-05:00 by KE2HNI
# Updated: 2026-11-12T19:00:00-05:00 by KE2HNI — capture all loopback packet protocols; filter M17 USRP packets in extract_pcm.
"""Mirror decoded M17 USRP PCM to a local-only dashboard WebSocket."""
from __future__ import annotations
import base64, configparser, hashlib, socket, struct, threading
from pathlib import Path
from urllib.parse import urlsplit
CONFIG=Path('/etc/USRP2M17.ini')
LISTEN_HOST='127.0.0.1'; LISTEN_PORT=8081
WEBSOCKET_GUID='258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

def read_usrp_route(path: Path=CONFIG) -> tuple[str,int,int]:
    config=configparser.ConfigParser(interpolation=None)
    if not config.read(path,encoding='utf-8') or not config.has_section('USRP Network'):
        raise ValueError('USRP2M17 [USRP Network] config is unavailable.')
    section=config['USRP Network']; address=socket.gethostbyname(section.get('Address','').strip())
    try: dst_port=section.getint('DstPort'); local_port=section.getint('LocalPort')
    except (ValueError,configparser.Error) as error: raise ValueError('USRP2M17 USRP ports must be numeric.') from error
    if not address.startswith('127.'): raise ValueError('M17 audio monitoring requires the Asterisk destination to be loopback.')
    if not (1<=dst_port<=65535 and 1<=local_port<=65535): raise ValueError('USRP2M17 USRP ports are outside the valid range.')
    return address,local_port,dst_port

def extract_pcm(ip_packet: bytes,route: tuple[str,int,int]) -> tuple[int,bytes] | None:
    if len(ip_packet)<20 or ip_packet[0]>>4!=4 or ip_packet[9]!=socket.IPPROTO_UDP: return None
    ip_length=(ip_packet[0]&0x0F)*4; total_length=struct.unpack_from('!H',ip_packet,2)[0]
    if ip_length<20 or total_length<ip_length+8 or total_length>len(ip_packet): return None
    destination=socket.inet_ntoa(ip_packet[16:20]); expected_address,expected_source_port,expected_destination_port=route
    source_port,destination_port,udp_length=struct.unpack_from('!HHH',ip_packet,ip_length)
    if destination!=expected_address or source_port!=expected_source_port or destination_port!=expected_destination_port or udp_length!=360: return None
    usrp=ip_packet[ip_length+8:ip_length+udp_length]
    if len(usrp)!=352 or usrp[:4]!=b'USRP' or usrp[15]!=1 or usrp[20]!=0: return None
    return struct.unpack_from('!I',usrp,4)[0],usrp[32:352]

def websocket_frame(payload: bytes,opcode: int=2) -> bytes:
    size=len(payload)
    if size<126: header=bytes((0x80|opcode,size))
    elif size<65536: header=bytes((0x80|opcode,126))+struct.pack('!H',size)
    else: header=bytes((0x80|opcode,127))+struct.pack('!Q',size)
    return header+payload

class AudioMonitor:
    def __init__(self,route): self.route=route; self.clients={}; self.clients_lock=threading.Lock()
    @staticmethod
    def _read_exact(client,count):
        data=bytearray()
        while len(data)<count:
            try: chunk=client.recv(count-len(data))
            except socket.timeout: continue
            if not chunk: return None
            data.extend(chunk)
        return bytes(data)
    def _handshake(self,client):
        request=bytearray()
        while b'\r\n\r\n' not in request and len(request)<16384:
            chunk=client.recv(4096)
            if not chunk: return False
            request.extend(chunk)
        lines=bytes(request).split(b'\r\n')
        if not lines or not lines[0].startswith(b'GET / '): return False
        headers={}
        for line in lines[1:]:
            if b':' in line:
                key,value=line.split(b':',1); headers[key.decode('latin1').strip().lower()]=value.decode('latin1').strip()
        key=headers.get('sec-websocket-key'); host=headers.get('host','').split(':',1)[0].lower()
        origin_host=(urlsplit(headers.get('origin','')).hostname or '').lower()
        connection_tokens={token.strip().lower() for token in headers.get('connection','').split(',')}
        if not key or headers.get('upgrade','').lower()!='websocket' or 'upgrade' not in connection_tokens or (origin_host and host!=origin_host): return False
        accept=base64.b64encode(hashlib.sha1((key+WEBSOCKET_GUID).encode('ascii')).digest()).decode('ascii')
        response='HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+'\r\n\r\n'
        client.sendall(response.encode('ascii')); return True
    def _client_loop(self,client):
        lock=threading.Lock()
        try:
            if not self._handshake(client): return
            client.settimeout(1.0)
            with self.clients_lock: self.clients[client]=lock
            while True:
                prefix=self._read_exact(client,2)
                if prefix is None: break
                opcode=prefix[0]&0x0F; masked=bool(prefix[1]&0x80); length=prefix[1]&0x7F
                if length==126:
                    raw=self._read_exact(client,2)
                    if not raw: break
                    length=struct.unpack('!H',raw)[0]
                elif length==127:
                    raw=self._read_exact(client,8)
                    if not raw: break
                    length=struct.unpack('!Q',raw)[0]
                if length>4096: break
                mask=self._read_exact(client,4) if masked else b''; payload=self._read_exact(client,length) if length else b''
                if mask is None or payload is None: break
                if masked and payload: payload=bytes(byte^mask[index%4] for index,byte in enumerate(payload))
                if opcode==8: break
                if opcode==9:
                    with lock: client.sendall(websocket_frame(payload,10))
        except (ConnectionError,OSError,ValueError): pass
        finally:
            with self.clients_lock: self.clients.pop(client,None)
            try: client.close()
            except OSError: pass
    def _accept_clients(self,listener):
        while True:
            try: client,_=listener.accept()
            except socket.timeout: continue
            except OSError: return
            threading.Thread(target=self._client_loop,args=(client,),daemon=True).start()
    def broadcast(self,pcm):
        frame=websocket_frame(pcm)
        with self.clients_lock: clients=list(self.clients.items())
        for client,lock in clients:
            try:
                with lock: client.sendall(frame)
            except OSError:
                with self.clients_lock: self.clients.pop(client,None)
                try: client.close()
                except OSError: pass
    def run(self):
        listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM); listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        listener.bind((LISTEN_HOST,LISTEN_PORT)); listener.listen(8); listener.settimeout(1.0)
        # Loopback packets were visible to tcpdump but not to a socket filtered
        # at creation/bind time for ETH_P_IP. Capture all protocols on lo and
        # let extract_pcm enforce the configured IPv4/UDP/USRP route.
        capture=socket.socket(socket.AF_PACKET,socket.SOCK_DGRAM,socket.htons(0x0003)); capture.bind(('lo',socket.htons(0x0003))); capture.settimeout(1.0)
        print(f'M17 monitor ready on {LISTEN_HOST}:{LISTEN_PORT}; USRP {self.route[1]}->{self.route[2]}',flush=True)
        threading.Thread(target=self._accept_clients,args=(listener,),daemon=True).start(); last_sequence=None
        while True:
            try: packet,_=capture.recvfrom(65535)
            except socket.timeout: continue
            audio=extract_pcm(packet,self.route)
            if audio is None: continue
            sequence,pcm=audio
            if sequence==last_sequence: continue
            last_sequence=sequence; self.broadcast(pcm)

def main(): AudioMonitor(read_usrp_route()).run()
if __name__=='__main__': main()
