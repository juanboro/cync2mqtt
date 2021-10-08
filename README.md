# cync2mqtt
Bridge Cync bluetooth mesh to mqtt. Includes auto-discovery for HomeAssistant.  Tested on Raspberry Pi3B+ and Pi-Zero-W
This is an alpha quality WIP

## Setup
### Create a python3 virtual env
```python3 -mvenv ~/venv/cync2mqtt```

### install into virtual environment
```~/venv/cync2mqtt/bin/pip3 install git+https://github.com/juanboro/cync2mqtt.git```

### Download Mesh Configuration from CYNC
```~/venv/cync2mqtt/bin/cync2mqtt fetchjson /home/pi/cync_mesh.json```
You will be prompted for your username (email) - you'll then get a onetime passcode on the email you will enter as well as your password.

### Test Run
Point the script at your MQTT broker:
```~/venv/cync2mqtt/bin/cync2mqtt  mqtt://192.168.74.1:1883/ ~/cync_mesh.json```
If it works you should see an INFO message similar to this:
```cync2mqtt - INFO - Connected to mesh mac: A4:C1:38:XX:XX:XX```

You can view MQTT messages on the topics: acyncmqtt/# and homeassistant/# ...i.e:
```mosquitto_sub -h 192.168.74.1 -v -t 'acyncmqtt/#' -t 'homeassistant/#'```


### Install systemd service (optional)

```shell
sudo nano /etc/systemd/system/cync2mqtt.service

[Unit]
Description=cync2mqtt
After=network.target

[Service]
ExecStart=/home/pi/venv/cync2mqtt/bin/cync2mqtt mqtt://192.168.1.1:1883/ /home/pi/cync_mesh.json
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

## MQTT Topics
Get list of devices - public 'get' to topic acyncmqtt/devices, i.e: 
```mosquitto_pub  -h 192.168.1.1 -t 'acyncmqtt/devices' -m get```

Devices can be controlled by sending a message to the topic: acyncmqtt/set/<meshid>/<deviceid>, i.e:
Turn on:
```mosquitto_pub  -h 192.168.1.1 -t 'acyncmqtt/set/D1284D352087/2' -m on```
Turn off:
```mosquitto_pub  -h 192.168.1.1 -t 'acyncmqtt/set/D1284D352087/2' -m off```
Set brightness:
```mosquitto_pub  -h 192.168.1.1 -t 'acyncmqtt/set/D1284D352087/2' -m '{"state": "on", "brightness" : 50}' ```


