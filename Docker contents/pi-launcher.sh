#!/bin/sh
PI_MODAL_FEA_STATE=$(mktemp /tmp/pi-modal-fea.XXXXXX) || exit 1
export PI_MODAL_FEA_STATE
printf 0 > "$PI_MODAL_FEA_STATE"
/opt/pi/node_modules/.bin/pi --no-extensions \
  -e /opt/pi/extensions/metering.ts -e /opt/pi/extensions/web-search.ts \
  -e /opt/pi/extensions/redact.ts "$@"
status=$?
rm -f "$PI_MODAL_FEA_STATE"
exit "$status"
