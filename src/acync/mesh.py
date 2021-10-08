#CYNC / C-GE bluetooth mesh light control implemented with BLEAK: https://github.com/hbldh/bleak

#some information from:
#http://wiki.telink-semi.cn//tools_and_sdk/BLE_Mesh/Telink_Mesh/telink_mesh_sdk.zip

#implementation largely based on:
#https://github.com/google/python-dimond
#and
#https://github.com/google/python-laurel

#which are...

# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contains code derived from python-tikteck,
# Copyright 2016 Matthew Garrett <mjg59@srcf.ucam.org>

from bleak import BleakClient
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import random
import asyncio
from collections import namedtuple
import logging

def encrypt(key, data):
    k = AES.new(bytes(reversed(key)), AES.MODE_ECB)
    data = reversed(list(k.encrypt(bytes(reversed(data)))))
    rev = []
    for d in data:
        rev.append(d)
    return rev

def generate_sk(name, password, data1, data2):
    name = name.ljust(16, chr(0))
    password = password.ljust(16, chr(0))
    key = [ord(a) ^ ord(b) for a,b in zip(name,password)]
    data = data1[0:8]
    data += data2[0:8]
    return encrypt(key, data)

def key_encrypt(name, password, key):
    name = name.ljust(16, chr(0))
    password = password.ljust(16, chr(0))
    data = [ord(a) ^ ord(b) for a,b in zip(name,password)]
    return encrypt(key, data)

def encrypt_packet(sk, address, packet):
    auth_nonce = [address[0], address[1], address[2], address[3], 0x01,
                packet[0], packet[1], packet[2], 15, 0, 0, 0, 0, 0, 0, 0]

    authenticator = encrypt(sk, auth_nonce)

    for i in range(15):
        authenticator[i] = authenticator[i] ^ packet[i+5]

    mac = encrypt(sk, authenticator)

    for i in range(2):
        packet[i+3] = mac[i]

    iv = [0, address[0], address[1], address[2], address[3], 0x01, packet[0],
        packet[1], packet[2], 0, 0, 0, 0, 0, 0, 0]

    temp_buffer = encrypt(sk, iv)
    for i in range(15):
        packet[i+5] ^= temp_buffer[i]

    return packet

def decrypt_packet(sk, address, packet):
    iv = [address[0], address[1], address[2], packet[0], packet[1], packet[2],
        packet[3], packet[4], 0, 0, 0, 0, 0, 0, 0, 0] 
    plaintext = [0] + iv[0:15]

    result = encrypt(sk, plaintext)

    for i in range(len(packet)-7):
        packet[i+7] ^= result[i]

    return packet

class atelink_mesh:
    #http://wiki.telink-semi.cn/wiki/protocols/Telink-Mesh/

    notification_char = "00010203-0405-0607-0809-0a0b0c0d1911"
    control_char="00010203-0405-0607-0809-0a0b0c0d1912"
    pairing_char="00010203-0405-0607-0809-0a0b0c0d1914"

    def __init__(self, vendor,meshmacs, name, password):
        self.vendor=vendor
        self.meshmacs = {x : 0 for x in meshmacs}
        self.name = name
        self.password = password
        self.packet_count = random.randrange(0xffff)
        self.macdata=None
        self.sk=None
        self.client=None
        self.log=getattr(self,'log',logging.getLogger(__name__))
        self.currentmac=None

    async def __aenter__(self):
        await self.connect()
        return self
  
    async def __aexit__(self, exc_t, exc_v, exc_tb):
        await self.disconnect()

    async def disconnect(self):
        if self.client is not None:
            try:
                await self.client.disconnect()
            except:
                self.log.info("disconnect returned false")
            self.client=None

    async def callback_handler(self,sender, data):
        print("{0}: {1}".format(sender, decrypt_packet(self.sk,self.macdata,list(data))))

    async def connect(self):
        self.macdata=None
        self.sk=None
        for mac in sorted(self.meshmacs,key=lambda x: self.meshmacs[x]):
            self.client=BleakClient(mac)
            try:
                await self.client.connect()
            except:
                self.meshmacs[mac]+=1
                self.log.info(f"Unable to connect to mesh mac: {mac}")
                await asyncio.sleep(0.1)
                continue
            if not self.client.is_connected:
                self.log.info(f"Unable to connect to mesh mac: {mac}")
                continue

            self.currentmac=mac
            macarray = mac.split(':')
            self.macdata = [int(macarray[5], 16), int(macarray[4], 16), int(macarray[3], 16), int(macarray[2], 16), int(macarray[1], 16), int(macarray[0], 16)]

            data = [0] * 16
            random_data = get_random_bytes(8)
            for i in range(8):
                data[i] = random_data[i]
            enc_data = key_encrypt(self.name, self.password, data)
            packet = [0x0c]
            packet += data[0:8]
            packet += enc_data[0:8]
            try:
                await self.client.write_gatt_char(atelink_mesh.pairing_char,bytes(packet),True)
                await asyncio.sleep(0.3)
                data2 = await self.client.read_gatt_char(atelink_mesh.pairing_char)
            except:
                self.log.info(f"Unable to connect to mesh mac: {mac}")
                await asyncio.sleep(0.1)
            else:
                self.sk = generate_sk(self.name, self.password, data[0:8], data2[1:9])

                try:
                    await self.client.start_notify(atelink_mesh.notification_char, self.callback_handler)
                    await asyncio.sleep(0.3)

                    await self.client.write_gatt_char(atelink_mesh.notification_char,bytes([0x1]),True)
                    await asyncio.sleep(0.3)
                    data3 = await self.client.read_gatt_char(atelink_mesh.notification_char)
                    self.log.info(f"Connected to mesh mac: {mac}")
                    #print(list(data3))
                except Exception as e: 
                    self.log.info(f"Unable to connect to mesh mac: {mac} - {e}")
                    continue
                break

        return self.sk is not None
        
    async def update_status(self):
        for trycount in range(0,3):
            try:
                await self.client.write_gatt_char(atelink_mesh.notification_char,bytes([0x1]),True)
                await asyncio.sleep(0.3)
                data3 = await self.client.read_gatt_char(atelink_mesh.notification_char)
            except:
                self.log.info(f"update_status - Unable to connect to send to mesh, retry...")
                if trycount<2:
                    self.meshmacs[self.currentmac]+=1
                    self.currentmac=None
                    await asyncio.sleep(0.1)
                    await self.disconnect()
                    await asyncio.sleep(0.1)
                    await self.connect()
                else:
                    return False
            break
        return True

    @property
    def online(self):
        return self.client is not None and self.sk is not None and self.macdata is not None

    async def send_packet(self,target, command, data):
        if not self.online:
            if not await self.connect():
                return False

        packet = [0] * 20
        packet[0] = self.packet_count & 0xff
        packet[1] = self.packet_count >> 8 & 0xff
        packet[5] = target & 0xff
        packet[6] = (target >> 8) & 0xff
        packet[7] = command
        packet[8] = self.vendor & 0xff
        packet[9] = (self.vendor >> 8) & 0xff
        for i in range(len(data)):
            packet[10 + i] = data[i]
        enc_packet = encrypt_packet(self.sk, self.macdata, packet)
        self.packet_count += 1
        if self.packet_count > 65535:
            self.packet_count = 1

        for trycount in range(0,3):
            try:
                await self.client.write_gatt_char(network.control_char,bytes(enc_packet))
            except:
                self.log.info(f"send_packet - Unable to connect to send to mesh")
                if trycount<2:
                    self.meshmacs[self.currentmac]+=1
                    self.currentmac=None
                    await asyncio.sleep(0.1)
                    await self.disconnect()
                    await asyncio.sleep(0.1)
                    await self.connect()
                else:
                    return False
            break
        return True

class network(atelink_mesh):
    devicestatus=namedtuple('DeviceStatus',['name','id','brightness','rgb','red','green','blue','temperature'])

    def __init__(self,meshmacs, name, password,**kwargs):
        self.log = kwargs.get('log',logging.getLogger(__name__))
        self.callback = kwargs.get('callback',None)
        return atelink_mesh.__init__(self, 0x0211,meshmacs, name, password)

    async def callback_handler(self, sender, data):
        if self.callback is None: return
        data=list(data)
        if len(data)<19: return

        data=decrypt_packet(self.sk,self.macdata,data)
        if data[7] != 0xdc:
            return

        responses = data[10:18]
        for i in (0, 4):
            response = responses[i:i+4]
            if response[1]==0: continue
            id = response[0]
            brightness = response[2]
            (red,green,blue)=(0,0,0)
            temperature=0
            if brightness >= 128:
                    brightness = brightness - 128
                    red = int(((response[3] & 0xe0) >> 5) * 255 / 7)
                    green = int(((response[3] & 0x1c) >> 2) * 255 / 7)
                    blue = int((response[3] & 0x3) * 255 / 3)
                    rgb = True
            else:
                temperature = response[3]
                rgb = False
            await self.callback(network.devicestatus(self.name,id,brightness,rgb,red,green,blue,temperature))

class device:
    def __init__ (self, mesh_network, name,id,mac,type):
        self.network = mesh_network
        self.name = name
        self.id = id
        self.mac = mac
        self.type = type
        self.brightness = 0
        self.temperature = 0
        self.red = 0
        self.green = 0
        self.blue = 0
        self.rgb = False
        self.online=False

    async def set_temperature(self, temperature):
        if not self.online: return False
        if await self.network.send_packet(self.id, 0xe2, [0x05, temperature]):
            self.temperature = temperature
            return True
        return False

    async def set_rgb(self, red, green, blue):
        if not self.online: return False
        if await self.network.send_packet(self.id, 0xe2, [0x04, red, green, blue]):
            self.red = red
            self.green = green
            self.blue = blue
            return True
        return False

    async def set_brightness(self, brightness):
        if not self.online: return False
        if await self.network.send_packet(self.id, 0xd2, [brightness]):
            self.brightness = brightness
            return True
        return False

    async def set_power(self, power):
        if not self.online: return False
        return await self.network.send_packet(self.id, 0xd0, [int(power)])

    @property
    def is_plug(self):
        return self.type==65

    @property
    def supports_rgb(self):
        if self.type == 6 or \
           self.type == 7 or \
           self.type == 8 or \
           self.type == 21 or \
           self.type == 22 or \
           self.type == 23:
            return True
        return False

    @property
    def supports_temperature(self):
        if self.supports_rgb or \
           self.type == 5 or \
           self.type == 19 or \
           self.type == 20 or \
           self.type == 80 or \
           self.type == 83 or \
           self.type == 85:
            return True
        return False
