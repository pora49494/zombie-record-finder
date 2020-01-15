import configparser
import datetime
import logging
import json
import copy
import argparse
from collections import defaultdict
from _pybgpstream import BGPStream, BGPRecord

def dt2ts(dt):
    return int((dt - datetime.datetime(1970, 1, 1)).total_seconds())

def ts2dt(ts):
    return datetime.datetime.fromtimestamp(ts + datetime.datetime(1970, 1, 1).timestamp())

class ZombieRecordFinder : 
    def __init__ (self, date, collector) :
        self.config = configparser.ConfigParser()
        self.config.read('/app/config.ini')

        self.start = datetime.datetime(date.year, date.month, 10)
        self.end = datetime.datetime(date.year, date.month, 20)
        self.collector = collector

        FORMAT = '%(asctime)s ZombieRecordFinder %(message)s'
        logging.basicConfig(
            format=FORMAT, filename=f"{self.config['DEFAULT']['LogLocation']}/{date.year}-{date.month}-ZombieRecordFinder-{collector}.log",
            level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S'
        )

        self.zombies = self.read_zombies()[::-1]

    def read_zombies (self) :
        logging.debug(f"[ZombieRecordFinder-{self.collector}] start reading zombie data")

        partitions = int(self.config['DEFAULT']['PartitionNumber'])
        zombies = []
        
        for i in range(partitions) : 
            f = open(f"{self.config['DEFAULT']['Data']}/{self.start.year}-{self.start.month}-zombieDetector-{i}-filtered.txt", "r")
            lines = f.readlines()
            for l in lines :
                _, prefix, time, _, _ = map(lambda x: x.strip(), l.split("|") ) 
                date_time_obj = datetime.datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
                zombies.append( ( dt2ts(date_time_obj), prefix ) )
            f.close()
        return sorted(zombies) 

    def get_stream(self) :
        logging.debug(f"[ZombieRecordFinder-{self.collector}] try to create BGPstream")
         
        stream = BGPStream()
        stream.add_interval_filter( dt2ts(self.start), dt2ts(self.end) )
        stream.add_filter('collector', self.collector)
        for _, p in self.zombies :
            stream.add_filter('prefix-exact', p)
        return stream

    def analyze_element (self, path, belong_to_asn, elem, ts) :
        
        elem_type = elem.type
        if elem_type not in {'R', 'A', 'W'} :
            return 
        
        prefix = elem.fields['prefix']
        peer_asn = elem.peer_asn
        peer_address = elem.peer_address    
        
        if prefix in path :
            path[prefix][peer_address]["status"] = elem_type
            
            if peer_asn not in belong_to_asn[peer_address] :
                if "peer_asn" not in path[prefix][peer_address] : 
                    path[prefix][peer_address]["peer_asn"] = peer_asn
                else :
                    path[prefix][peer_address]["peer_asn"] = path[prefix][peer_address]["peer_asn"] + " " + peer_asn
                belong_to_asn[peer_address].add(peer_asn)

            path[prefix][peer_address]["ts"] = ts

            if elem_type == "R" or elem_type == "A" :
                path[prefix][peer_address]["as_path"] = elem.fields['as-path']
            elif elem_type == "W" :
                path[prefix][peer_address]["as_path"] = ""


        return    
    
    def prep_path (self) :
        path = dict()
        for _, p in self.zombies :
            path[p] =  defaultdict(dict)
        return path

    def path_finder (self) :
        logging.info(f"[ZombieRecordFinder-{self.collector}] starting path_finder()")

        path = self.prep_path()
        belong_to_asn = defaultdict(set)
        dump_path = dict()

        stream = self.get_stream()
        stream.start()
        rec = BGPRecord()
        try:
            while stream and stream.get_next_record(rec):
                if rec.status != "valid":
                    continue
                if rec.type == "unknown" :
                    continue
                
                recordTimeStamp = int(rec.time)
                while self.zombies and self.zombies[-1][0] < recordTimeStamp :
                    ts, prefix = self.zombies.pop()
                    dump_path[ f"{prefix}|{ts}" ] = copy.deepcopy(path[prefix])
                    
                elem = rec.get_next_elem()
                while(elem):
                    self.analyze_element(path, belong_to_asn, elem, recordTimeStamp)
                    elem = rec.get_next_elem()

        except Exception as e :
            logging.error(f"[ZombieRecordFinder-{self.collector}] exit with error : {e}")
        
        finally :
            with open(f"{self.config['DEFAULT']['Result']}/{self.start.year}-{self.start.month}-zombie-record-finder-{self.collector}.json", 'w') as fp:
                json.dump(dump_path, fp)
        
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("--collector", "-c", help="Choose a collector to push data for")
    parser.add_argument("--date", "-d", help="Choose analyzing date (Format: Y_m; Example: 2017_11")
    args = parser.parse_args()
    
    y, m = map(int, args.date.split("_") )
    date = datetime.datetime(y,m,1)

    z = ZombieRecordFinder(date, args.collector)
    z.path_finder() 
