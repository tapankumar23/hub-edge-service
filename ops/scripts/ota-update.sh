#!/usr/bin/env bash
set -e
MODEL_URL=$1
DEST=/opt/edgehub/models/current.onnx
mkdir -p /opt/edgehub/models
curl -L "$MODEL_URL" -o "$DEST"
