FROM alpine:3.22.0 AS build
RUN apk update && \
apk add python3 py3-pip py3-requests  gcc python3-dev py3-yaml py3-pycryptodome py3-six py3-six-pyc py3-dbus py3-passlib py3-passlib-pyc py3-websockets py3-websockets-pyc py3-docopt py3-pydbus py3-pydbus-pyc git bluez build-base glib-dev && \
pip install --break-system-packages git+https://github.com/juanboro/cync2mqtt.git
RUN cd /root && \
pip install --break-system-packages pyinstaller && \
/usr/bin/pyinstaller --collect-data bluepy --collect-all amqtt --onefile /usr/bin/cync2mqtt
FROM alpine:3.22.0
COPY --from=build /root/dist/cync2mqtt /usr/bin/cync2mqtt
COPY run.sh /
RUN apk update && \
apk add bluez && \
mkdir /config && \
chmod a+x /run.sh && \
ln -s cync2mqtt /usr/bin/get_cync_config_from_cloud
CMD [ "/run.sh" ]
