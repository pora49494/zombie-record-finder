#! /bin/bash 

#docker build -t pora/bgpstream:record_finder .

YEAR_ENV="2019"
MONTH_ENV="08"
HEADER="${YEAR_ENV}_${MONTH_ENV}"

docker run -d -it \
    --name "${HEADER}_zombie_record_finder_tester" \
    --entrypoint "/bin/sh" \
    -e header="${HEADER}" \
    -v "${PWD}"/app/zombieRecordFinder.py:/app/zombieRecordFinder.py \
    -v "${PWD}"/data:/app/data \
    -v "${PWD}"/logs:/app/logs \
    -v "${PWD}"/result:/app/result \
    -v "${PWD}"/config.ini:/app/config.ini \
    pora/bgpstream:record_finder 

# python3 /app/zombieRecordFinder.py -c rrc00 -d 2019_08