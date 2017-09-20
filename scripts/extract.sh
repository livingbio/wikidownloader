#!/bin/bash

cd $1
ls *.bz2 | xargs -i -t basename {} .bz2 | xargs -i -t ../WikiExtractor.py -b 50m --processes=8 {}.bz2 -o {} --lang $1
rm *.bz2
