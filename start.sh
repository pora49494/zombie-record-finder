#! /bin/bash 

#docker build -t pora/bgpstream:record_finder .

cat "./_server/${1}" | \
while read CMD 
do 
    YEAR_ENV="${CMD:0:4}"
    MONTH_ENV="${CMD:5:7}"
    HEADER="${YEAR_ENV}_${MONTH_ENV}"

    for i in $(seq -w 0 21) ; do
        if [[ $i == "02" ]] || [[ $i == "08" ]] || [[ $i == "09" ]] || [[ $i == "17" ]] ; then 
            continue
        fi 
    
    docker run -d --rm -it \
        --name "${HEADER}_zombie_record_finder_rrc${i}" \
        -v "${PWD}"/app/zombieRecordFinder.py:/app/zombieRecordFinder.py \
        -v "${PWD}"/data:/app/data \
        -v "${PWD}"/logs:/app/logs \
        -v "${PWD}"/result:/app/result \
        -v "${PWD}"/config.ini:/app/config.ini \
        pora/bgpstream:record_finder \
        /app/zombieRecordFinder.py -c "rrc${i}" -d "${HEADER}"
    
    month=$(echo $MONTH_ENV | sed 's/^0*//')
    CUR=$(pwd)

    cd /${CUR}/result
    tar -czf ${YEAR_ENV}-${month}-record.tar.bz ${YEAR_ENV}-${month}-*
    mv ${YEAR_ENV}-${month}-record.tar.bz ${CUR}/archive/
    rm ${YEAR_ENV}-${month}-zombie-record-finder-*.json

    cd ${CUR}

done

# python3 /app/zombieRecordFinder.py -c rrc00 -d 2019_08