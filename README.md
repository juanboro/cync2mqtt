# cync2mqtt
Bridge Cync bluetooth mesh to mqtt. Includes auto-discovery for HomeAssistant.  Tested on Raspberry Pi3B+ and Pi-Zero-W
This is an alpha quality WIP

zimmra test version

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
~/venv/cync2mqtt/bin/pip3 install git+https://github.com/zimmra/cync2mqtt.git
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
