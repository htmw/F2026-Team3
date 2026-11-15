import unittest
from risk_mvp.main_assessment_cache import AssessmentCache,REFRESH_SECONDS

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.now=0;self.cache=AssessmentCache(clock=lambda:self.now,limit=2);self.calls=0
    def build(self):
        self.calls+=1
        return {'status':'scored_research_demo','research_risk_probability':.4,'computed':self.calls}
    def test_reuse_and_twelve_hour_expiry(self):
        first=self.cache.resolve(1,{'features':[1]},self.build)
        first['computed']=999
        self.now=REFRESH_SECONDS-1
        self.assertEqual(self.cache.resolve(1,{'features':[1]},self.build)['computed'],1)
        self.now=REFRESH_SECONDS
        self.assertEqual(self.cache.resolve(1,{'features':[1]},self.build)['computed'],2)
    def test_source_change_and_manual_refresh(self):
        self.cache.resolve(1,{'coverage':True},self.build)
        self.cache.resolve(1,{'coverage':False},self.build)
        self.cache.resolve(1,{'coverage':False},self.build,force=True)
        self.assertEqual(self.calls,3)
    def test_expired_failure_never_returns_previous_score(self):
        self.cache.resolve(1,{},self.build);self.now=REFRESH_SECONDS
        def fail():raise RuntimeError('Unavailable')
        with self.assertRaises(RuntimeError):self.cache.resolve(1,{},fail)
        self.assertNotIn(1,self.cache.entries)
    def test_unavailable_not_cached_and_keys_are_separate(self):
        self.cache.resolve(1,{},lambda:{'status':'unavailable'})
        self.assertNotIn(1,self.cache.entries)
        self.cache.resolve((1,'date1'),{},self.build)
        self.cache.resolve((1,'date2'),{},self.build)
        self.cache.resolve((2,'date1'),{},self.build)
        self.assertEqual(self.calls,3);self.assertEqual(len(self.cache.entries),2)
