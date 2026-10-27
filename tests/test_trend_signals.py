import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trend_signals import load_reviewed,import_reviewed,extract_candidates,record_candidates,feed_topics
from collector import build_feed, normalize, ingest

NOW=datetime(2026,10,26,18,0,tzinfo=timezone(timedelta(hours=9)))

class TrendQualityTests(unittest.TestCase):
 def test_evidence_complete_and_recent(self):
  terms=load_reviewed(ROOT/'data/verified_slang.json',NOW.date())
  self.assertGreaterEqual(len(terms),7)
  self.assertIn('メロい',[t['jp'] for t in terms])
  self.assertTrue(all(t['zh'] and t['en'] and t['source'].startswith('https://') for t in terms))
 def test_hard_rank_sources_no_fake_sample_counts(self):
  s={'terms':{},'seenDocs':{}}
  found=import_reviewed(s,load_reviewed(ROOT/'data/verified_slang.json',NOW.date()),NOW,normalize)
  self.assertEqual(found,8)
  d=build_feed(s,NOW,[])
  self.assertEqual(d['counts']['verifiedSlang'],8)
  self.assertEqual(len(d['items']),8)
  self.assertTrue(all(w['trendVerified'] and 'trend' in w['kinds'] for w in d['items']))
  self.assertTrue(all(w['last7']==0 for w in d['items']))
  self.assertIn('2026-10-02',{w['evidenceDate'] for w in d['items']})
  self.assertEqual(import_reviewed(s,load_reviewed(ROOT/'data/verified_slang.json',NOW.date()),NOW,normalize),0)
  self.assertEqual(len(s['terms']),8)
 def test_generic_frequency_does_not_masquerade_as_slang(self):
  s={'terms':{'女性':{'id':'x','jp':'女性','kana':'じょせい','zh':'女性','en':'woman','qualityApproved':True,
    'kinds':['freq','trend'],'daily':{'2026-10-26':12},'trendCount':4,'sources':[]}},'seenDocs':{}}
  w=build_feed(s,NOW,[])['items'][0]
  self.assertEqual(w['jp'],'女性')
  self.assertNotIn('trend',w['kinds'])
  self.assertFalse(w['trendVerified'])
 def test_approved_slang_first_not_frequency_score(self):
  s={'terms':{'女性':{'id':'x','jp':'女性','kana':'じょせい','zh':'女性','en':'woman','qualityApproved':True,
   'kinds':['freq'],'daily':{'2026-10-26':40},'trendCount':0,'sources':[]}},'seenDocs':{}}
  import_reviewed(s,load_reviewed(ROOT/'data/verified_slang.json',NOW.date()),NOW,normalize)
  self.assertNotEqual(build_feed(s,NOW,[])['items'][0]['jp'],'女性')
 def test_cannot_publish_unverified_slang_candidates(self):
  s={'terms':{},'seenDocs':{}}
  a={'id':'a','title':'Z世代の流行語「テストカツ」が話題に','url':'https://news.google.com/x',
     'source':'Google News','category':'流行语候选','kind':'slang_signal'}
  class FakeTok:
   def tokenize(self,_):return []
  ingest([a],s,FakeTok(),NOW)
  self.assertIn('テストカツ',s['slangReviewQueue'])
  self.assertEqual(build_feed(s,NOW,[])['counts']['words'],0)
  self.assertEqual(build_feed(s,NOW,[])['counts']['reviewQueue'],1)
 def test_title_extraction_without_sloppiness(self):
  self.assertEqual(extract_candidates('新たな流行語「ニャルト」が高校生に人気'),['ニャルト'])
  self.assertEqual(extract_candidates('女子高校生向けの「学校」の校則ニュース'),[])
  self.assertEqual(extract_candidates('ネットスラング「流行語」が話題に'),[])
 def test_google_trends_search_topics_separate(self):
  s={'terms':{'示例':{'jp':'示例','kana':'しれい','qualityApproved':False,'kinds':['topic'],
   'trendCount':3,'sources':[{'url':'https://www.google.com'}]}},'seenDocs':{}}
  self.assertEqual(len(build_feed(s,NOW,[])['items']),0)
  self.assertEqual(feed_topics(s)[0]['label'],'搜索话题，不代表流行语')
 def test_invalid_curated_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'bad.json';f.write_text(json.dumps({'schemaVersion':1,'items':[{'jp':'偽物','kana':'にせもの','zh':'假的','en':''}]}),encoding='utf8')
   with self.assertRaises(ValueError):load_reviewed(f,NOW.date())

if __name__=='__main__':unittest.main()
