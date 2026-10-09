#!/bin/sh
exec /opt/pi/node_modules/.bin/pi --no-extensions \
  -e /opt/pi/extensions/metering.ts -e /opt/pi/extensions/web-search.ts "$@"
