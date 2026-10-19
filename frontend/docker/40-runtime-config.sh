#!/bin/sh
# Writes /tmp/config.js at container start, from the environment, so one image serves every environment:
# the API URL is set with `frontend.env.API_BASE_URL` in the Helm values, not at build time.
# /tmp is the only writable path (read-only root filesystem); nginx serves it as /config.js.
# Unset or empty = same origin (the ingress routes /api to the backend).
set -eu

# Keep the value inert in a JS string: no quote, backslash or newline.
api_base_url=$(printf '%s' "${API_BASE_URL:-}" | tr -d '"\\\n\r')

printf 'window.__APP_CONFIG__ = { API_BASE_URL: "%s" };\n' "$api_base_url" > /tmp/config.js
