#!/bin/sh

set -eu

python3 generate_uswgi_config.py
exec uwsgi /tmp/uwsgi.ini

