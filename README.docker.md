# cync2mqtt Dockerfile Build
Running in a docker container is a good alternative to running the systemd virtual env setup.  Here are instructions for one possible way to setup using docker.

## Setup

```
### Download Mesh Configuration from CYNC using 2FA
Create a directory on the host to store the mesh configuration file:
```shell
mkdir ~/.cync2mqtt
cd ~/.cyncqmqtt
```

Make sure your devices are all configured in the Cync app, then:
```shell
docker run --rm -it -v $PWD:/home/cync2mqtt juanboro/cync2mqtt get_cync_config_from_cloud /home/cync2mqtt/cync_mesh.yaml
```

You will be prompted for your username (email you setup Cync with) - you'll then get a onetime passcode on the email you will enter as well as your password you use with the app.

### Edit generated configuration
Edit the generated yaml file as necessary.  The only thing which should be necessary at a minimum is to make sure the mqtt_url definition matches your MQTT broker.

### Create Docker Container
This will create a docker container for cync2mqtt which shares access to the host Bluez bluetooth controller:
```shell
docker create --name cync2mqtt --restart=unless-stopped  -v $PWD:/home/cync2mqtt \
-v /var/run/dbus/:/var/run/dbus/:z --privileged juanboro/cync2mqtt  cync2mqtt /home/cync2mqtt/cync_mesh.yaml
```

If you need to use bluepy, create docker container like this (per stackoverflow guidance):
```shell
docker create --name cync2mqtt --restart=unless-stopped  -v ~/.cync2mqtt:/home/cync2mqtt \
 --cap-add=SYS_ADMIN --cap-add=NET_ADMIN --net=host cync2mqtt:latest  cync2mqtt /home/cync2mqtt/cync_mesh.yaml
```

### Test Run
Run the container interactively:
```shell
docker start -ai cync2mqtt
```
If it works you should see an INFO message similar to this:
```shell
cync2mqtt - INFO - Connected to mesh mac: XX:XX:XX:XX:XX:XX
```

You can view MQTT messages on the topics: acyncmqtt/# and homeassistant/# ...i.e, from the host:
```shell
mosquitto_sub -h $mqttip -v -t 'acyncmqtt/#' -t 'homeassistant/#'
```

Control-C will exit the test run.
### Run as container service
Once things seem correctly running - you can run detached like this:
```shell
docker start cync2mqtt
```
(see also docker documentation)

