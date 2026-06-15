#!/bin/sh
set -e

echo "Running DB init + seed..."
python seed_data.py

echo "Starting app..."
exec "$@"
