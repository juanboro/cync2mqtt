FROM alpine:3.18.2
RUN apk update
RUN apk add python3 py3-pip py3-requests py3-yaml py3-pycryptodome py3-six py3-six-pyc py3-dbus py3-passlib py3-passlib-pyc py3-websockets py3-websockets-pyc py3-docopt py3-pydbus py3-pydbus-pyc git
RUN pip install amqtt@git+https://github.com/Yakifo/amqtt.git git+https://github.com/juanboro/cync2mqtt.git 
RUN mkdir -p home/cync2mqtt
CMD cync2mqtt /home/cync2mqtt/cync.yaml
