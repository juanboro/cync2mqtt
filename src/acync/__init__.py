#CYNC / C-GE bluetooth mesh light control implemented with BLEAK: https://github.com/hbldh/bleak

# lots of information from
#https://github.com/google/python-laurel
#http://wiki.telink-semi.cn/tools_and_sdk/BLE_Mesh/SIG_Mesh/sig_mesh_sdk.zip

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


import random
import requests
import getpass
import json
from pathlib import Path
from acync.mesh import network,device
import logging
import re

logger=logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class xlinkException(Exception):
    pass

def randomLoginResource():
    return ''.join([chr(ord('a')+random.randint(0,26)) for i in range(0,16)])

class acync:
    API_TIMEOUT = 5
    # https://github.com/unixpickle/cbyge/blob/main/login.go
    def _authenticate_2fa():
        """Authenticate with the API and get a token."""
        username=input("Enter Username (or emailed code):")
        if re.match('^\d+$',username):
            code=username
            username=input("Enter Username:")
        else:
            API_AUTH = "https://api.gelighting.com/v2/two_factor/email/verifycode"
            auth_data = {'corp_id': "1007d2ad150c4000", 'email': username,"local_lang": "en-us"}
            r = requests.post(API_AUTH, json=auth_data, timeout=acync.API_TIMEOUT)
            code=input("Enter emailed code:")
            
        password=getpass.getpass()
        API_AUTH = "https://api.gelighting.com/v2/user_auth/two_factor"
        auth_data = {'corp_id': "1007d2ad150c4000", 'email': username,
                    'password': password, "two_factor": code, "resource": randomLoginResource()}
        r = requests.post(API_AUTH, json=auth_data, timeout=acync.API_TIMEOUT)

        try:
            return (r.json()['access_token'], r.json()['user_id'])
        except KeyError:
            raise(xlinkException('API authentication failed'))


    def _get_devices(auth_token, user):
        """Get a list of devices for a particular user."""
        API_DEVICES = "https://api.gelighting.com/v2/user/{user}/subscribe/devices"
        headers = {'Access-Token': auth_token}
        r = requests.get(API_DEVICES.format(user=user), headers=headers,
                        timeout=acync.API_TIMEOUT)
        return r.json()

    def _get_properties(auth_token, product_id, device_id):
        """Get properties for a single device."""
        API_DEVICE_INFO = "https://api.gelighting.com/v2/product/{product_id}/device/{device_id}/property"
        headers = {'Access-Token': auth_token}
        r = requests.get(API_DEVICE_INFO.format(product_id=product_id, device_id=device_id), headers=headers, timeout=acync.API_TIMEOUT)
        return r.json()

    def get_app_meshinfo():
        (auth,userid)=acync._authenticate_2fa()
        mesh_networks=acync._get_devices(auth, userid)
        for mesh in mesh_networks:
            mesh['properties']=acync._get_properties(auth, mesh['product_id'],mesh['id'])
        return mesh_networks

    def app_meshinfo_to_configdict(meshinfo):
        meshconfig={}

        for mesh in meshinfo:
            if 'name' not in mesh or len(mesh['name'])<1: continue
            newmesh={kv: mesh[kv] for kv in ('access_key','name','mac') if kv in mesh}
            meshconfig[mesh['id']]=newmesh
            
            if 'properties' not in mesh or 'bulbsArray' not in mesh['properties']: continue

            newmesh['bulbs']={}
            for bulb in mesh['properties']['bulbsArray']:
                if any(checkattr not in bulb for checkattr in ('deviceID','displayName','mac','deviceType')): continue
                id = int(str(bulb['deviceID'])[-3:])
                bulbdevice=device(None,bulb['displayName'], id, bulb['mac'],bulb['deviceType'])
                newbulb={}
                for attrset in ('name','is_plug','supports_temperature','supports_rgb','mac'):
                    value=getattr(bulbdevice,attrset)
                    if value:
                        newbulb[attrset]=value
                newmesh['bulbs'][id]=newbulb

        configdict={}
        configdict['mqtt_url']='mqtt://127.0.0.1:1883/'
        configdict['meshconfig']=meshconfig

        return configdict

    def __init__(self,**kwargs):
        self.networks={}
        self.devices={}
        self.meshmap={}
        self.xlinkdata=None
        self.callback = kwargs.get('callback',None)

    # define our callback handler
    async def _callback_routine(self,devicestatus):
        device=self.devices[f"{devicestatus.name}/{devicestatus.id}"]
        device.online=True
        for attr in ('brightness','red','green','blue','color_temp'):
            setattr(device,attr,getattr(devicestatus,attr))
        if self.callback is not None:
            await self.callback(self,devicestatus)

    def populate_from_configdict(self, configdict):
        for meshid, mesh in configdict['meshconfig'].items():
            if 'name' not in mesh:
                mesh['name'] = f'mesh_{meshid}'
            meshmacs = {}
            if 'bulbs' in mesh:
                for bulb in mesh['bulbs'].values():
                    # support MAC in config with either colons or not
                    mac = bulb['mac'].replace(':', '')
                    mac = ':'.join(mac[i:i+2] for i in range(0, 12, 2))
                    meshmacs[mac] = bulb['priority'] if 'priority' in bulb else 0

                # print(f"Add network: {mesh['name']}")
                self.meshmap[mesh['mac']] = mesh['name']

                usebtlib = None
                if 'usebtlib' in mesh:
                    usebtlib = mesh['usebtlib']
                mesh_network = network(meshmacs, mesh['mac'], str(mesh['access_key']), usebtlib=usebtlib)

                async def cb(devicestatus):
                    return await self._callback_routine(devicestatus)

                mesh_network.callback = cb

                self.networks[mesh['name']] = mesh_network

                for bulbid, bulb in mesh['bulbs'].items():
                    devicetype = bulb['type'] if 'type' in bulb else None
                    bulbname = bulb['name'] if 'name' in bulb else f"device_{bulbid}"
                    newdevice = device(mesh_network, bulbname, bulbid, bulb['mac'], devicetype)
                    for attrset in ('is_plug', 'supports_temperature', 'supports_rgb'):
                        if attrset in bulb:
                            setattr(newdevice, attrset, bulb[attrset])
                    self.devices[f"{mesh['mac']}/{bulbid}"] = newdevice

    def populate_from_jsonfile(self,jsonfile):
        jsonfile=Path(jsonfile)

        with jsonfile.open("rt") as fp:
            self.xlinkdata=json.load(fp)
        for mesh in self.xlinkdata:
            if 'name' not in mesh or len(mesh['name'])<1: continue
            if 'properties' not in mesh or 'bulbsArray' not in mesh['properties']: continue
            meshmacs=[]
            for bulb in mesh['properties']['bulbsArray']:
                mac = [bulb['mac'][i:i+2] for i in range(0, 12, 2)]
                mac = "%s:%s:%s:%s:%s:%s" % (mac[0], mac[1], mac[2], mac[3], mac[4], mac[5])
                meshmacs.append(mac)

            #print(f"Add network: {mesh['name']}")
            self.meshmap[mesh['mac']]=mesh['name']
            usebtlib=None
            if 'usebtlib' in mesh: 
                usebtlib=mesh['usebtlib']
            mesh_network=network(meshmacs,mesh['mac'],str(mesh['access_key']),usebtlib=usebtlib)
            async def cb(devicestatus):
                return await self._callback_routine(devicestatus)
            mesh_network.callback=cb

            self.networks[mesh['name']]=mesh_network

            for bulb in mesh['properties']['bulbsArray']:
                id = int(bulb['deviceID'][-3:])
                self.devices[f"{mesh['mac']}/{id}"]=device(mesh_network,bulb['displayName'], id, bulb['mac'],bulb['deviceType'])

    async def disconnect(self):
        for device in self.devices.values():
            device.online=False

        for mesh in self.networks.values():
            await mesh.disconnect()

    async def connect(self):
        connected=list()
        try:
            for meshname,mesh in self.networks.items():
                if await mesh.connect():
                    connected.append(meshname)
        except:
            await self.disconnect()
            raise Exception("Unable to connect to mesh network(s)")

        return connected
