FROM sourcepole/qwc-uwsgi-base:alpine-v2025.01.24

WORKDIR /srv/qwc_service
ADD pyproject.toml uv.lock ./

# git: Required for pip with git repos
# postgresql-dev g++ python3-dev: Required for psycopg2
# zlib-dev jpeg-dev: Required for pillow
RUN \
    apk add --no-cache --update --virtual runtime-deps postgresql-libs libjpeg zlib && \
    apk add --no-cache --update --virtual build-deps git postgresql-dev g++ python3-dev jpeg-dev zlib-dev && \
    uv sync --frozen && \
    apk del build-deps

ADD src /srv/qwc_service/

ENV SERVICE_MOUNTPOINT=/api/v1/legend
