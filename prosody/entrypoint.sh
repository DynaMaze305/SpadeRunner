#!/bin/sh
set -e

# ------------------------------------------------------------------------------
# Prosody Docker Entrypoint Script
#
# This script is executed when the container starts. It performs any necessary
# initialization (e.g., environment variable substitution in configuration files
# or running custom scripts) and finally executes the main command.
# ------------------------------------------------------------------------------

mkdir -p /var/lib/prosody
chown -R prosody:prosody /var/lib/prosody
mkdir -p /var/run/prosody
chown -R prosody:prosody /var/run/prosody

mkdir -p /etc/prosody/certs
if [ ! -f /etc/prosody/certs/localhost.key ]; then
    echo "Generating SSL certificates for localhost..."
    openssl genrsa -out /etc/prosody/certs/localhost.key 2048
    openssl req -new -key /etc/prosody/certs/localhost.key -out /etc/prosody/certs/localhost.csr -subj "/CN=localhost"
    openssl x509 -req -days 365 -in /etc/prosody/certs/localhost.csr -signkey /etc/prosody/certs/localhost.key -out /etc/prosody/certs/localhost.crt
    rm -f /etc/prosody/certs/localhost.csr
fi

# Generate certificates for prosody domain
if [ ! -f /etc/prosody/certs/prosody.key ]; then
    echo "Generating SSL certificates for prosody domain..."
    openssl genrsa -out /etc/prosody/certs/prosody.key 2048
    openssl req -new -key /etc/prosody/certs/prosody.key -out /etc/prosody/certs/prosody.csr -subj "/CN=prosody"
    openssl x509 -req -days 365 -in /etc/prosody/certs/prosody.csr -signkey /etc/prosody/certs/prosody.key -out /etc/prosody/certs/prosody.crt
    rm -f /etc/prosody/certs/prosody.csr
fi

chown -R prosody:prosody /etc/prosody
chmod 777 /etc/prosody
chmod -R 777 /etc/prosody/*.cfg.lua 2>/dev/null || true
chmod -R 777 /etc/prosody/conf.d/*.cfg.lua 2>/dev/null || true
chmod 777 /etc/prosody/certs
chmod 777 /etc/prosody/certs/* 2>/dev/null || true
chmod 777 /etc/prosody/certs/localhost.key 2>/dev/null || true

echo "Prosody version:"
prosodyctl about

echo "Checking Prosody configuration:"
prosodyctl check config

echo "Final Prosody configuration:"
cat /etc/prosody/prosody.cfg.lua

data_dir_owner="$(stat -c %u "/var/lib/prosody/")"
if [ "$(id -u prosody)" != "$data_dir_owner" ]; then
    # FIXME this fails if owned by root
    usermod -u "$data_dir_owner" prosody
fi
if [ "$(stat -c %u /var/run/prosody/)" != "$data_dir_owner" ]; then
    chown "$data_dir_owner" /var/run/prosody/
fi

if [ "$1" != "prosody" ]; then
    exec prosodyctl "$@"
    exit 0;
fi

if [ "$LOCAL" ] && [ "$PASSWORD" ] && [ "$DOMAIN" ]; then
    prosodyctl register "$LOCAL" "$DOMAIN" "$PASSWORD"
fi

# Use su-exec instead of runuser for Alpine
exec su-exec prosody "$@"