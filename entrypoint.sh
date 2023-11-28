#!/bin/sh

set -eu

python3 generate_uswgi_config.py
exec uwsgi -c /tmp/uwsgi.ini

