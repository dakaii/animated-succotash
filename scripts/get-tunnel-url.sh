#!/usr/bin/env bash
exec "$(dirname "$0")/hermes" tunnel-url "$@"
