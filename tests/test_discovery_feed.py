"""Offline regression tests: automatic candidates vs verified learning words."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from sys import path

path.insert(0,str(Path(__file__).resolve().parents[1]))
import discovery_feed as d
import slang_only as s

NOW=datetime(2026,11,2,9,0,tzinfo=s.JST)
CATALOG=Path(__file__).resolve().parents[1]/'slang_terms.json'
ORIGIN='https://shibuya-trendresearch.jp/monthlytrendsurvey/4622/'

def pending(jp='新しい語',source=ORIGIN,date='2026-10-02'):
    return [{'jp':jp,'kanaSuggestion':'',
        'translationDraft':{'zh':'不可信机器翻译','en':'bad AI text','verified':False},
        'approvedForPublication':False,
        'evidence':[{'url':source,'date':date,'rank':3}]}]

def feed():
    return {'generatedAt':'2026-11-01T02:00:00+09:00','counts':{'words':1},
        'items':[{'id':'known','jp':'既存','kana':'きそん','zh':'已有','en':'existing'}]}

class DiscoveryFeedTests(unittest.TestCase):
    def test_candidate_is_public_without_fake_translation(self):
        now=NOW
        verified=feed()
        output=d.snapshot(verified,pending(),feed(),{},now)
        self.assertEqual(output['candidateCount'],1)
        self.assertEqual(output['items'][0]['jp'],'新しい語')
        self.assertFalse(any(k in str(output) for k in ('不可信机器翻译','bad AI text','translationDraft')))
        self.assertEqual(output['items'][0]['status'],'未核实候选（不可作为准确学习释义）')
        self.assertEqual(verified['counts']['verifiedAddedThisRun'],0)
        self.assertEqual(verified['counts']['verifiedChangedThisRun'],False)

    def test_initial_snapshot_does_not_call_old_candidates_new(self):
        out=d.snapshot(feed(),pending(),feed(),{},NOW)
        self.assertTrue(out['firstSnapshot'])
        self.assertEqual(out['newCandidatesThisRun'],[])
        self.assertIsNone(out['items'][0]['firstObservedAt'])

    def test_repeated_crawl_does_not_invent_changes(self):
        f=feed()
        a=d.snapshot(f,pending(),feed(),{},NOW)
        next_time=NOW+timedelta(hours=12)
        nf=feed()
        b=d.snapshot(nf,pending(),f,a,next_time)
        self.assertFalse(nf['counts']['verifiedChangedThisRun'])
        self.assertEqual(nf['counts']['verifiedAddedThisRun'],0)
        self.assertEqual(b['newCandidatesThisRun'],[])
        self.assertIsNone(b['lastVerifiedChangeAt'])
        self.assertIsNone(b['items'][0]['firstObservedAt'],
                          'Second scan cannot invent a historical first discovery timestamp')

    def test_second_snapshot_with_new_candidate_is_explicit(self):
        initial=d.snapshot(feed(),pending(),feed(),{},NOW)
        again=d.snapshot(feed(),pending()+pending('新的网络词'),feed(),initial,NOW+timedelta(hours=2))
        self.assertEqual(again['newCandidatesThisRun'],['新的网络词'])
        self.assertEqual(again['candidateCount'],2)
        self.assertEqual(next(x for x in again['items'] if x['jp']=='新的网络词')['firstObservedAt'],
                         (NOW+timedelta(hours=2)).isoformat(timespec='seconds'))

    def test_actual_verified_word_add_sets_real_change(self):
        previous=feed()
        current=feed()
        current['items'].append({'id':'n2','jp':'新词','kana':'しんご','zh':'新词','en':'new word'})
        current['counts']['words']=2
        snap=d.snapshot(current,pending(),previous,{},NOW)
        self.assertTrue(current['counts']['verifiedChangedThisRun'])
        self.assertEqual(current['counts']['verifiedAddedThisRun'],1)
        self.assertEqual(snap['verifiedAddedThisRun'],['新词'])
        self.assertEqual(current['lastVerifiedChangeAt'],NOW.isoformat(timespec='seconds'))

    def test_expired_or_http_evidence_rejected(self):
        rows=pending('过时的词',date='2026-01-03')+pending('不安全链接',source='http://bad.example/')
        out=d.snapshot(feed(),rows,feed(),{},NOW)
        self.assertEqual(out['candidateCount'],0)

    def test_malformed_candidate_cannot_publish_a_dictionary_item(self):
        verified=feed()
        old=json.dumps(verified['items'],sort_keys=True,ensure_ascii=False)
        rows=pending('"><script>alert(1)</script>')
        snapshot=d.snapshot(verified,rows,feed(),{},NOW)
        self.assertEqual(snapshot['candidateCount'],0)
        self.assertEqual(json.dumps(verified['items'],sort_keys=True,ensure_ascii=False),old)

    def test_only_public_source_links_and_evidence_dates(self):
        data=pending()
        data[0]['evidence'].extend([
            {'url':'https://user:pass@example.jp/secret','date':'2026-10-29'},
            {'url':'https://localhost/private','date':'2026-10-29'},
            {'url':'https://example.jp/post#fragment','date':'2026-10-29'}])
        out=d.snapshot(feed(),data,feed(),{},NOW)
        urls=[x['url'] for x in out['items'][0]['sources']]
        self.assertNotIn('https://localhost/private',urls)
        self.assertFalse(any('#' in u or 'user:pass' in u for u in urls))
        self.assertIn('https://example.jp/post',urls)

    def test_repeated_source_dedupes_by_url(self):
        data=pending()
        data[0]['evidence'].append(data[0]['evidence'][0].copy())
        out=d.snapshot(feed(),data,feed(),{},NOW)
        self.assertEqual(out['items'][0]['sourceCount'],1)

    def test_real_collector_creates_both_lanes_with_same_pub_count(self):
        with tempfile.TemporaryDirectory() as temp:
            html='''<meta property="article:published_time" content="2026-10-02">
               <h3>今流行っている言葉は？</h3><p>1位 新しいネット語 (23.0%)</p>
               <h3>今流行っている物事は？</h3>'''
            verified=s.run(temp,CATALOG,fixture=html,now=NOW)
            public=json.loads(Path(temp,'discovery_feed.json').read_text(encoding='utf8'))
            self.assertEqual(public['candidateCount'],1)
            self.assertEqual(public['items'][0]['jp'],'新しいネット語')
            self.assertEqual(public['verifiedWordCount'],verified['counts']['words'])
            self.assertFalse(any(w['jp']=='新しいネット語' for w in verified['items']))
            self.assertTrue(Path(temp,'feed.json').exists())
            self.assertEqual(len(s.load_catalog(CATALOG)),14)

    def test_dashboard_never_injects_source_markup(self):
        dashboard=(Path(__file__).resolve().parents[1]/'docs'/'discovery.html').read_text(encoding='utf8')
        self.assertIn("textContent",dashboard)
        self.assertNotIn('innerHTML',dashboard)
        self.assertIn('cache:',dashboard)
        self.assertIn('未经核实',dashboard)
        self.assertIn('discovery_feed.json',dashboard)

if __name__=='__main__':unittest.main()
