"""Bounded, process-local 12-hour demo cache. Authorization happens in the router.
Revalidate source inputs on every request; never serve expired or invalidated fallback.
"""
from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
import threading
import time

REFRESH_SECONDS = 12 * 60 * 60

class AssessmentCache:
    def __init__(self, clock=time.monotonic, limit=256):
        self.clock=clock; self.limit=limit; self.entries=OrderedDict(); self.lock=threading.RLock()

    def resolve(self, key, source, build, force=False):
        signature=hashlib.sha256(json.dumps(source,sort_keys=True,default=str,allow_nan=False).encode()).hexdigest()
        with self.lock:
            entry=self.entries.get(key)
            if not force and entry and entry[0]==signature and self.clock()-entry[1]<REFRESH_SECONDS:
                self.entries.move_to_end(key)
                return deepcopy(entry[2])
            self.entries.pop(key,None)
            # Any exception propagates; there is no stale-on-error fallback.
            result=build()
            if result.get('status')=='scored_research_demo' and result.get('explanation',{}).get('status','available')=='available':
                self.entries[key]=(signature,self.clock(),deepcopy(result))
                while len(self.entries)>self.limit:self.entries.popitem(last=False)
            return result

CACHE=AssessmentCache()

def assessment(db,enrollment_id,cutoff,include_explanation=False,force=False):
    from . import service
    cutoff=service.normalize(cutoff)
    # Same read-only repeatable-read transaction as identity/assignment checks.
    source=service.extract(db,enrollment_id,cutoff)
    def build():
        result=service.assessment(db,enrollment_id,cutoff)
        if include_explanation:
            from .main_explanations import attach
            result=attach(result,db,enrollment_id,cutoff)
        return result
    key=(enrollment_id,cutoff.isoformat(),include_explanation)
    return CACHE.resolve(key,source,build,force=force)
