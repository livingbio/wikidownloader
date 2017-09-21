#!/bin/bash

cat `find $1/*` | mongoimport -h 192.168.137.1 -d NLP -c "${1}wiki"
