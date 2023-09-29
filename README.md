# cync2mqtt
Bridge Cync bluetooth mesh to mqtt. Includes auto-discovery for HomeAssistant.  Tested on Raspberry Pi3B+,Pi-Zero-W and [x86-64 linux docker](https://github.com/zimmra/cync2mqtt-docker)

## Features
- Supports home assistant [MQTT Discovery](https://www.home-assistant.io/docs/mqtt/discovery/)
- Supports mesh notifications (bulb status updates published to mqtt regardless of what set them).
- Cleanly recovers from communication errors both with the BLE mesh as well as MQTT broker.

## Requirements
- Linux like OS with bluez bluetooth stack.  Has been tested on a number of X86 and ARM (Raspberry Pi) configurations.  It might work on Windows but as far as I know no one has tried.
- MQTT broker (my config is mosquitto from [Entware](https://github.com/Entware/Entware) running on router).
- GE/Savant Cync Switches, Bulbs.
- Optional (but recommended): [Home Assistant](https://www.home-assistant.io/)

## Setup
See also [Docker Instructions](README.docker.md)
### Create a python3 virtual env
```shell
python3 -mvenv ~/venv/cync2mqtt
```

### install into virtual environment
```shell
~/venv/cync2mqtt/bin/pip3 install git+https://github.com/juanboro/cync2mqtt.git
```
#### Note Python3.10+
[AMQTT](https://github.com/Yakifo/amqtt) does not yet have a released version for Python3.10+.  To run with Python3.10, you can currently install in virtual environment like this:
```shell
git clone https://github.com/juanboro/cync2mqtt.git src_cync2mqtt
~/venv/cync2mqtt/bin/pip3 install -r src_cync2mqtt/requirements.python3.10.txt  src_cync2mqtt/
```
### Download Mesh Configuration from CYNC using 2FA
Make sure your devices are all configured in the Cync app, then:
```shell
~/venv/cync2mqtt/bin/get_cync_config_from_cloud ~/cync_mesh.yaml
```

You will be prompted for your username (email) - you'll then get a onetime passcode on the email you will enter as well as your password.

### Edit generated configuration
Edit the generated yaml file as necessary.  The only thing which should be necessary at a minimum is to make sure the mqtt_url definition matches your MQTT broker.  Also see: [cync_mesh_example.yaml](cync_mesh_example.yaml) 

### Test Run
Run the script with the config file:
```shell
~/venv/cync2mqtt/bin/cync2mqtt  ~/cync_mesh.yaml
```
If it works you should see an INFO message similar to this:
```shell
cync2mqtt - INFO - Connected to mesh mac: XX:XX:XX:XX:XX:XX
```

You can view MQTT messages on the topics: acyncmqtt/# and homeassistant/# ...i.e:
```shell
mosquitto_sub -h $meship  -I rx -v -t 'acyncmqtt/#' -t 'homeassistant/#'
``` 


### Install systemd service (optional example for Raspberry PI OS)

```shell
sudo nano /etc/systemd/system/cync2mqtt.service
```
```ini 
[Unit]
Description=cync2mqtt
After=network.target

[Service]
ExecStart=/home/pi/venv/cync2mqtt/bin/cync2mqtt /home/pi/cync_mesh.yaml
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

```shell
sudo systemctl enable cync2mqtt.service
```

## MQTT Topics
I recommend using a GUI like [mqqt-spy](https://github.com/eclipse/paho.mqtt-spy) to work with your MQTT broker.  Below are some basic mosquitto command line topic examples.  You need to also be subscribed with mosquitto command abvoe to see the responses.

Get list of devices - publish 'get' to topic acyncmqtt/devices, i.e: 
```shell
mosquitto_pub  -h $mqttip -t 'acyncmqtt/devices' -m get
```

You will receive a response on the topic ```homeassistant/devices/<meshid>/<deviceid>``` for every defined mesh and device.

Devices can be controlled by sending a message to the topic: ```acyncmqtt/set/<meshid>/<deviceid>```, i.e:

Turn on:
```shell
mosquitto_pub  -h $mqttip -I tx -t "acyncmqtt/set/$meshid/$deviceid" -m on
```

Turn off:
```shell
mosquitto_pub  -h $mqttip -I tx -t "acyncmqtt/set/$meshid/$deviceid" -m off
```

Set brightness:
```shell
mosquitto_pub  -h $mqttip -I tx -t "acyncmqtt/set/$meshid/$deviceid" -m '{"state": "on", "brightness" : 50}' 
```
## Issues
Certain direct connect devices (those with WIFI) have trouble connecting with the Linux Bluez-DBUS bluetooth-LE stack (can not connect/receive notiications).  If possible - the best workaround is to have at least one device in your mesh cync2mqtt can connect to that does not have these issues.  As a workaround, it is also possible to use [bluepy](https://github.com/IanHarvey/bluepy) which does not have these issues.  See the [cync_mesh_example.yaml](cync_mesh_example.yaml) for how to enable this.

## Notes
Outside of the initial setup of downloading the mesh credentials from your cloud account, this has no dependencies on the cloud.  If neccessary, in the future a standalone pairing script can also be written to remove all cloud depdendencies.  Generally though for my own setup - I find having the cloud connectivity good to have for Alexa/Google Home support and then having HomeAssistant support via this mqtt bridge to bluetooth.  Several other alternatives also exist out there depending on what your own needs may be:
- [cync_lights](https://github.com/nikshriv/cync_lights/tree/main) - Home assistant custom component that does all communication with the cloud server.
- [cbyge](https://github.com/unixpickle/cbyge/tree/main) - Standalone app to communicate with the cloud server.  I believe this also has a mqtt wrapper interface which has been developed.
- [cync-lan](https://github.com/iburistu/cync-lan) - A good proof of concept of direct wifi connection to cync devices.  This almost makes me want to block the official cloud access to my Cync devices :-).

## Acknowledgments
- Telink-Mesh python: https://github.com/google/python-laurel
- 2FA Cync login: https://github.com/unixpickle/cbyge/blob/main/login.go
- Async BLE python: https://pypi.org/project/bleak/
- Async MQTT: https://amqtt.readthedocs.io/en/latest/index.html
- [zimmra](https://github.com/zimmra) for docker container, debug, and testing.
