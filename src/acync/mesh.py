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
import bluepy.btle
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import random
import asyncio
from collections import namedtuple
import logging
import queue
import functools
import concurrent.futures

logger=logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

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

class bluepyDelegate(bluepy.btle.DefaultDelegate):
    def __init__(self, notifyqueue):
        bluepy.btle.DefaultDelegate.__init__(self)
        self.notifyqueue=notifyqueue

    def handleNotification(self, cHandle, data):
        self.notifyqueue.put((cHandle,data))

class btle_gatt(object):
    def __init__(self, mac,uselib="bleak"):
        self.mac=mac
        self.is_connected=None
        self.notifytasks=None
        self.notifyqueue= None
        self._notifycallbacks={}
        self.loop=asyncio.get_running_loop()
        self.bluepy_lock = asyncio.Lock()

        if uselib=="bleak":
            self.client=BleakClient(mac)
        elif uselib=="bluepy":
            self.client=bluepy.btle.Peripheral()
        else:
            raise ValueError(f"bluetooth library: {uselib} not supported")

    async def notify_worker(self):
        pool=concurrent.futures.ThreadPoolExecutor(1)
        while True:
            (handle,data)=await self.loop.run_in_executor(pool,self.notifyqueue.get)
            if handle in self._notifycallbacks:
                await self._notifycallbacks[handle](handle,data)

            await self.loop.run_in_executor(pool,self.notifyqueue.task_done)

    async def notify_waiter(self):
        pool=concurrent.futures.ThreadPoolExecutor(1)
        while True:
            async with self.bluepy_lock:
                await asyncio.sleep(0.25)
                await self.loop.run_in_executor(pool,self.client.waitForNotifications,0.25)
 
    async def connect(self):
        self.macdata=None
        self.sk=None
        self._uuidchars={}

        if self.is_connected: return

        if isinstance(self.client,bluepy.btle.Peripheral):
            async with self.bluepy_lock:
                result = await self.loop.run_in_executor(concurrent.futures.ThreadPoolExecutor(1), functools.partial(self.client.connect,self.mac, addrType=bluepy.btle.ADDR_TYPE_PUBLIC))
                self.notifyqueue=queue.Queue()
                self.notifytasks=[]
                self.notifytasks.append(asyncio.create_task(self.notify_worker()))
                self.client.setDelegate( bluepyDelegate(self.notifyqueue))
                self.is_connected=True
            return result
        else:
            status=await self.client.connect()
            self.is_connected=True
            return status

    async def bluepy_get_char_from_uuid(self,uuid):
        if uuid in self._uuidchars:
            return self._uuidchars[uuid]
        else:
            async with self.bluepy_lock:
                char=(await self.loop.run_in_executor(concurrent.futures.ThreadPoolExecutor(1), functools.partial(self.client.getCharacteristics,uuid=uuid)))[0]
                self._uuidchars[uuid]=char
            return char

    async def write_gatt_char(self,uuid,data,withResponse=False):
        if isinstance(self.client,bluepy.btle.Peripheral):
            char=await self.bluepy_get_char_from_uuid(uuid)
            async with self.bluepy_lock:
                result=await self.loop.run_in_executor(concurrent.futures.ThreadPoolExecutor(1), functools.partial(char.write,data,withResponse=withResponse))
            return result
        else:
            return await self.client.write_gatt_char(uuid,data,withResponse)

    async def read_gatt_char(self,uuid):
        if isinstance(self.client,bluepy.btle.Peripheral):
            char=await self.bluepy_get_char_from_uuid(uuid)
            async with self.bluepy_lock:
                result=await self.loop.run_in_executor(concurrent.futures.ThreadPoolExecutor(1), char.read)
            return result
        else:
            return await self.client.read_gatt_char(uuid)

    async def disconnect(self):
        if self.notifytasks is not None:
            for notifytask in self.notifytasks:
                notifytask.cancel()

        if isinstance(self.client,bluepy.btle.Peripheral):
            async with self.bluepy_lock:
                result=await self.loop.run_in_executor(concurrent.futures.ThreadPoolExecutor(1), self.client.disconnect)
            return result
        else:
            return await self.client.disconnect()

    async def start_notify(self,uuid, callback_handler):
        if isinstance(self.client,bluepy.btle.Peripheral):
            char=await self.bluepy_get_char_from_uuid(uuid)
            async with self.bluepy_lock:
                handle=await self.loop.run_in_executor(concurrent.futures.ThreadPoolExecutor(1),char.getHandle)
            self._notifycallbacks[handle]=callback_handler
            self.notifytasks.append(asyncio.create_task(self.notify_waiter()))
        else:
            return await self.client.start_notify(uuid,callback_handler)

class atelink_mesh:
    #http://wiki.telink-semi.cn/wiki/protocols/Telink-Mesh/

    notification_char = "00010203-0405-0607-0809-0a0b0c0d1911"
    control_char="00010203-0405-0607-0809-0a0b0c0d1912"
    pairing_char="00010203-0405-0607-0809-0a0b0c0d1914"

    def __init__(self, vendor,meshmacs, name, password,usebtlib=None):
        self.vendor=vendor
        self.meshmacs = {x : 0 for x in meshmacs} if type(meshmacs) is list else meshmacs
        self.name = name
        self.password = password
        self.packet_count = random.randrange(0xffff)
        self.macdata=None
        self.sk=None
        self.client=None
        self.currentmac=None
        if usebtlib is None:
            self.uselib='bleak'
        else:
            self.uselib=usebtlib

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
                logger.info("disconnect returned false")
            self.client=None

    async def callback_handler(self,sender, data):
        print("{0}: {1}".format(sender, decrypt_packet(self.sk,self.macdata,list(data))))

    async def connect(self):
        self.macdata=None
        self.sk=None

        for retry in range(0,3):
            if self.sk is not None: break
            for mac in sorted(self.meshmacs,key=lambda x: self.meshmacs[x]):
                if self.meshmacs[mac]<0: continue
                self.client=btle_gatt(mac,uselib=self.uselib)

                try:
                    await self.client.connect()
                except:
                    self.meshmacs[mac]+=1
                    logger.info(f"Unable to connect to mesh mac: {mac}")
                    await asyncio.sleep(0.1)
                    continue
                if not self.client.is_connected:
                    logger.info(f"Unable to connect to mesh mac: {mac}")
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
                    logger.info(f"Unable to connect to mesh mac: {mac}")
                    await self.client.disconnect()
                    self.sk=None
                    continue
                else:
                    self.sk = generate_sk(self.name, self.password, data[0:8], data2[1:9])

                    try:
                        await self.client.start_notify(atelink_mesh.notification_char, self.callback_handler)
                        await asyncio.sleep(0.3)
                        await self.client.write_gatt_char(atelink_mesh.notification_char,bytes([0x1]),True)
                        await asyncio.sleep(0.3)
                        data3 = await self.client.read_gatt_char(atelink_mesh.notification_char)
                        logger.info(f"Connected to mesh mac: {mac}")
                    except Exception as e: 
                        logger.info(f"Unable to connect to mesh mac for notify: {mac} - {e}")
                        await self.client.disconnect()
                        self.sk=None
                        continue
                    break

        return self.sk is not None
        
    async def update_status(self):
        if self.sk is None:
            logger.info("Attempt re-connect...")
            if not self.connect():
                return False

        ok=False
        for trycount in range(0,3):
            if ok:
                break            
            try:
                await self.client.write_gatt_char(atelink_mesh.notification_char,bytes([0x1]),True)
                await asyncio.sleep(0.3)
                data3 = await self.client.read_gatt_char(atelink_mesh.notification_char)
                ok=True
            except:
                logger.info("update_status - Unable to connect to send to mesh, retry...")
                try2=0
                connected=False
                while not connected and try2<3:
                    self.meshmacs[self.currentmac]+=1
                    self.currentmac=None
                    await asyncio.sleep(0.1)
                    logger.info("Disconnect...")
                    await self.disconnect()
                    await asyncio.sleep(0.1)
                    logger.info("Disconnected... reconnecting...")
                    connected=await self.connect()
                    try2+=1
                if not connected:
                    return False
        return ok

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
                logger.info(f"send_packet - Unable to connect to send to mesh")
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

    devicestatus=namedtuple('DeviceStatus',['name','id','brightness','rgb','red','green','blue','color_temp'])

    def __init__(self,meshmacs, name, password,usebtlib=None,**kwargs):
        self.callback = kwargs.get('callback',None)
        return atelink_mesh.__init__(self, 0x0211,meshmacs, name, password,usebtlib)

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
            color_temp=0
            if brightness >= 128:
                    brightness = brightness - 128
                    red = int(((response[3] & 0xe0) >> 5) * 255 / 7)
                    green = int(((response[3] & 0x1c) >> 2) * 255 / 7)
                    blue = int((response[3] & 0x3) * 255 / 3)
                    rgb = True
            else:
                color_temp = response[3]
                rgb = False
            await self.callback(network.devicestatus(self.name,id,brightness,rgb,red,green,blue,color_temp))

class device:
    #from: https://github.com/nikshriv/cync_lights/blob/main/custom_components/cync_lights/cync_hub.py
    Capabilities = {
        "ONOFF":[1,5,6,7,8,9,10,11,13,14,15,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,48,49,51,52,53,54,55,56,57,58,59,61,62,63,64,65,66,67,68,80,81,82,83,85,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,156,158,159,160,161,162,163,164,165],
        "BRIGHTNESS":[1,5,6,7,8,9,10,11,13,14,15,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,48,49,55,56,80,81,82,83,85,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,156,158,159,160,161,162,163,164,165],
        "COLORTEMP":[5,6,7,8,10,11,14,15,19,20,21,22,23,25,26,28,29,30,31,32,33,34,35,80,82,83,85,129,130,131,132,133,135,136,137,138,139,140,141,142,143,144,145,146,147,153,154,156,158,159,160,161,162,163,164,165],
        "RGB":[6,7,8,21,22,23,30,31,32,33,34,35,131,132,133,137,138,139,140,141,142,143,146,147,153,154,156,158,159,160,161,162,163,164,165],
        "MOTION":[37,49,54],
        "AMBIENT_LIGHT":[37,49,54],
        "WIFICONTROL":[36,37,38,39,40,48,49,51,52,53,54,55,56,57,58,59,61,62,63,64,65,66,67,68,80,81,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,156,158,159,160,161,162,163,164,165],
        "PLUG":[64,65,66,67,68],
        "FAN":[81],
        "MULTIELEMENT":{'67':2}
    }

    def __init__ (self, mesh_network, name,id,mac,type=None):
        self.network = mesh_network
        self.name = name
        self.id = id
        self.mac = mac
        self.type = type
        self.brightness = 0
        self.color_temp = 0
        self.red = 0
        self.green = 0
        self.blue = 0
        self.rgb = False
        self.online=False
        self._supports_rgb=None
        self._supports_temperature=None
        self._is_plug=None
        self.reported_temp = 0

    async def set_temperature(self, color_temp):
        if not self.online: return False
        if await self.network.send_packet(self.id, 0xe2, [0x05, color_temp]):
            self.color_temp = color_temp
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
        if self._is_plug is not None: return self._is_plug
        if self.type is None: return False
        return self.type in device.Capabilities['PLUG']

    @is_plug.setter
    def is_plug(self,value):
        self._is_plug=value

    @property
    def supports_rgb(self):
        if self._supports_rgb is not None: return self._supports_rgb
        if self._supports_rgb or self.type in device.Capabilities['RGB']:
            return True
        return False

    @supports_rgb.setter
    def supports_rgb(self,value):
        self._supports_rgb=value

    @property
    def supports_temperature(self):
        if self._supports_temperature is not None: return self._supports_temperature
        if self.supports_rgb or self.type in device.Capabilities['COLORTEMP']:
            return True
        return False

    @supports_temperature.setter
    def supports_temperature(self,value):
        self._supports_temperature=value
