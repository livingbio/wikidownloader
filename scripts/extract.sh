#!/bin/bash

for file in "$1"/*.bz2
do
    python WikiExtractor.py -b 50m --processes=8 "${file}" -o "${file%.bz2}" --lang $1
done
