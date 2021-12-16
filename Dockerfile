FROM sourcepole/qwc-uwsgi-base:alpine-v2021.12.16

# Required build dependencies for pillow
RUN apk add --virtual build-deps build-base linux-headers python3-dev

# Required libs for pillow
RUN apk add --no-cache --update jpeg-dev zlib-dev libjpeg

ADD . /srv/qwc_service
RUN pip3 install --no-cache-dir -r /srv/qwc_service/requirements.txt

# Remove build dependencies
RUN apk del build-deps
