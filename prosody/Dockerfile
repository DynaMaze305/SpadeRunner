FROM alpine:latest

RUN apk update && \
    apk add --no-cache prosody openssl su-exec && \
    mkdir -p /etc/prosody/certs

COPY ./entrypoint.sh /tmp/entrypoint.sh
RUN tr -d '\r' < /tmp/entrypoint.sh > /usr/local/bin/entrypoint.sh && \
    chmod +x /usr/local/bin/entrypoint.sh && \
    rm /tmp/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

CMD ["prosody"]