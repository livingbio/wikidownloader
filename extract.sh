#!/bin/bash

for lang in en ja zh
do
    for file in $lang/*.bz2
    do
        python WikiExtractor.py -b 50m --processes=32 $file -o ${file/.bz2/} --lang $lang
    done
done
