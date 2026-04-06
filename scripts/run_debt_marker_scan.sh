#!/usr/bin/env bash
set -euo pipefail

rg -n "TODO|FIXME|XXX" backend frontend \
  -g '!**/package-lock.json' \
  -g '!**/pnpm-lock.yaml' \
  -g '!**/yarn.lock'
