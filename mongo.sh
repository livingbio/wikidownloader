#/bin/bash
database=test
lang=$1

aws s3 sync s3://gliacloud-nlp/rawdata/$lang $lang
cat `find $lang/*` | mongoimport -d $database -c $collection -j 4
