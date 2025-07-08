#ARG BUILD_FROM=alpine:3.18.2
FROM alpine:3.18.2
RUN mkdir -p home/cync2mqtt &&\
apk update && \
apk add python3 py3-pip py3-psutil py3-requests py3-yaml py3-pycryptodome py3-six py3-six-pyc py3-dbus py3-passlib py3-passlib-pyc py3-websockets py3-websockets-pyc py3-docopt py3-pydbus py3-pydbus-pyc git bluez build-base glib-dev && \
pip install amqtt@git+https://github.com/Yakifo/amqtt.git git+https://github.com/juanboro/cync2mqtt.git 
COPY run.sh /
RUN chmod a+x /run.sh
CMD [ "/run.sh" ]
