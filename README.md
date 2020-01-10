# zombie-record-finder
Script for finding the latest AS_PATH of each router before the zombie outbreak.

### How to use 
There are 2 requirements neccessary to run the script.
1. Adding zombie event from `zombie-hunter` to data 
2. set the year and month of your zombie outbreak in the _server/1 (FOMMAT `YYYY MM` ex 2019 08)

### Run
```terminal 
$ docker build -t pora/bgpstream:record_finder .
$ ./start.sh 1 
```