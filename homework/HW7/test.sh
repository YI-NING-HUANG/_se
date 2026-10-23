#!/usr/bin/env bash
set -u
exec bash "$(dirname "$0")/tests/run_tests.sh" "$@"
