#!/usr/bin/env bash
URL=${1:-http://127.0.0.1:10000/upload}
IMG=${2:-/Users/petemcdade/vinted_ai/images/converted/IMG_8005.jpg}
curl -X POST -F "file=@${IMG}" "$URL"