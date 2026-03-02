#!/usr/bin/env bash
set -e
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin openssl
sudo systemctl enable docker
sudo systemctl start docker
mkdir -p /opt/edgehub
cp /Users/tapansabat/hub-edge-service-trae/.env.example /opt/edgehub/.env
openssl req -x509 -newkey rsa:4096 -nodes -keyout /opt/edgehub/device.key -out /opt/edgehub/device.crt -days 365 -subj "/CN=edgehub"
