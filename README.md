# cync2mqtt
Bridge Cync bluetooth mesh to mqtt. Includes auto-discovery for HomeAssistant.  Tested on Raspberry Pi3B+,Pi-Zero-W and [x86-64 linux docker](https://github.com/zimmra/cync2mqtt-docker)
This is an alpha quality WIP.  This does not currently support Direct Connect bulbs but (time permitting) I will look into it.

## Features
- Supports home assistant [MQTT Discovery](https://www.home-assistant.io/docs/mqtt/discovery/)
- Supports mesh notifications (bulb status updates published to mqtt regardless of what set them).
- Cleanly recovers from communication errors both with the BLE mesh as well as MQTT broker.

## Setup
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
Make sure your devies are all configured in the Cync app, then:
```shell
~/venv/cync2mqtt/bin/get_cync_config_from_cloud ~/cync_mesh.yaml
```

You will be prompted for your username (email) - you'll then get a onetime passcode on the email you will enter as well as your password.

### Edit generated configuration
Edit the generated yaml file as necessary.  The only thing which should be necessary at a minimum is to make sure the mqtt_url definition matches your MQTT broker.

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
mosquitto_sub -h $meship -v -t 'acyncmqtt/#' -t 'homeassistant/#'
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
Get list of devices - public 'get' to topic acyncmqtt/devices, i.e: 
```shell
mosquitto_pub  -h $meship -t 'acyncmqtt/devices' -m get
```

You will receive a response on the topic homeassistant/devices/<meshid>/<deviceid> for every defined mesh and device.

Devices can be controlled by sending a message to the topic: acyncmqtt/set/<meshid>/<deviceid>, i.e:

Turn on:
```shell
mosquitto_pub  -h $meship -t "acyncmqtt/set/$meshid/$deviceid" -m on
```

Turn off:
```shell
mosquitto_pub  -h $meship -t "acyncmqtt/set/$meshid/$deviceid" -m off
```

Set brightness:
```shell
mosquitto_pub  -h $meship -t "acyncmqtt/set/$meshid/$deviceid" -m '{"state": "on", "brightness" : 50}' 
```

## Acknowledgments
- Telink-Mesh python: https://github.com/google/python-laurel
- 2FA Cync login: https://github.com/unixpickle/cbyge/blob/main/login.go
- Async BLE python: https://pypi.org/project/bleak/
- Async MQTT: https://amqtt.readthedocs.io/en/latest/index.html
- [zimmra](https://github.com/zimmra) for docker container, debug, and testing.
