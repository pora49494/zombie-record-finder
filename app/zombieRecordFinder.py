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

        self.year = date.year
        self.month = date.month

        self.collector = collector

        FORMAT = '%(asctime)s ZombieRecordFinder %(message)s'
        logging.basicConfig(
            format=FORMAT, filename=f"{self.config['DEFAULT']['LogLocation']}/{date.year}-{date.month}-ZombieRecordFinder-{collector}.log",
            level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S'
        )

        self.zombies, self.changing = self.read_zombies()
        self.watching_prefix = set()

        self.path = self.prep_path()
        self.record = defaultdict(list)

    def read_zombies (self) :
        logging.debug(f"[ZombieRecordFinder-{self.collector}] start reading zombie data")

        quarantine = int(self.config['DEFAULT']['Quarantine'])
        
        zombies = []
        changing = []
        
        f = open(f"{self.config['DEFAULT']['Data']}/{self.year}-{self.month}-zombies-proof.txt", "r")
        lines = f.readlines()
        for l in lines :
            ts, prefix, _, _ = map(lambda x: x.strip(), l.split("|") ) 
            zombies.append( ( int(ts), prefix ) )
        f.close()
    
        zombies.sort(reverse=True)
        for ts, prefix in zombies :
            changing.append( (ts-quarantine, prefix) )
        
        return zombies, changing

    def get_stream(self) :
        logging.debug(f"[ZombieRecordFinder-{self.collector}] try to create BGPstream")
        
        _start = datetime.datetime(self.year, self.month, 10)
        _end = datetime.datetime(self.year, self.month, 20)

        stream = BGPStream()
        stream.add_interval_filter( dt2ts(_start), dt2ts(_end) )
        stream.add_filter('collector', self.collector)
        for _, p in self.zombies :
            stream.add_filter('prefix-exact', p)
        return stream

    def analyze_element (self, elem, ts) :
        
        elem_type = elem.type
        if elem_type not in {'R', 'A', 'W'} :
            return 
        
        prefix = elem.fields['prefix']
        peer_asn = elem.peer_asn
        peer_address = elem.peer_address    
        
        if prefix in self.watching_prefix : 
            self.record[prefix].append( f"{ts}|{elem_type}|{peer_address}|{peer_asn}" )

        if prefix in self.path :
            self.path[prefix][peer_address]["status"] = elem_type
            self.path[prefix][peer_address]["peer_asn"] = peer_asn
            self.path[prefix][peer_address]["ts"] = ts

            if elem_type == "R" or elem_type == "A" :
                self.path[prefix][peer_address]["as_path"] = elem.fields['as-path']

        return    
    
    def prep_path (self) :
        path = dict()
        for _, p in self.zombies :
            path[p] =  defaultdict(dict)
        return path

    def path_finder (self) :
        logging.info(f"[ZombieRecordFinder-{self.collector}] starting path_finder()")
        
        result_path = self.config['DEFAULT']['Result']
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
                while self.changing and self.changing[-1][0] < recordTimeStamp :
                    _, prefix = self.changing.pop()
                    self.watching_prefix.add(prefix)
                
                while self.zombies and self.zombies[-1][0] < recordTimeStamp :
                    ts, prefix = self.zombies.pop()
                    dump_path[ f"{prefix}|{ts}" ] = copy.deepcopy(self.path[prefix])
                    
                    if prefix in self.watching_prefix :
                        self.watching_prefix.remove(prefix)
                        f = open(f"{result_path}/{self.year}-{self.month}-changing-{self.collector}.txt", "a+")
                        data = ",".join(self.record[prefix]) 
                        f.write( f"{prefix} {ts} ? {data} \n" )
                        f.close()
                        del data 
                        del self.record[prefix]
                    else :
                        logging.warning(f"[ZombieRecordFinder-{self.collector}] trying to remove unwatched prefix {prefix}")

                elem = rec.get_next_elem()
                while(elem):
                    self.analyze_element( elem, recordTimeStamp)
                    elem = rec.get_next_elem()

        except Exception as e :
            logging.error(f"[ZombieRecordFinder-{self.collector}] exit with error : {e}")
        
        finally :
            with open(f"{result_path}/{self.year}-{self.month}-zombie-record-finder-{self.collector}.json", 'w') as fp:
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
