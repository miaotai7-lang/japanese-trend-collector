"""Offline regression tests for slang source evidence and translation drafts."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from sys import path
path.insert(0,str(Path(__file__).resolve().parents[1]))
import slang_only as s
import translation_review as q

NOW=datetime(2026,10,28,12,0,tzinfo=timezone(timedelta(hours=9)))
CATALOG=Path(__file__).resolve().parents[1]/'slang_terms.json'
EVIDENCE=[{'url':s.CURRENT_REPORT,'date':'2026-10-20','rank':3}]

class FakeTranslator:
    def __init__(self, mapping=None, fail=False):
        self.mapping=mapping or {'zh-CN':'网络热门说法','en':'trending internet slang'}
        self.calls=[]; self.fail=fail
    def translate(self,jp,target):
        self.calls.append((jp,target))
        if self.fail:raise TimeoutError('offline simulated failure')
        return self.mapping.get(target,'')

class QualityReviewTest(unittest.TestCase):
    def test_unambiguous_kana_only(self):
        self.assertEqual(q.suggested_kana('ドパおじ'),'どぱおじ')
        self.assertEqual(q.suggested_kana('ﾒﾛｲ'),'めろい')
        self.assertEqual(q.suggested_kana('メロい'),'めろい')
        self.assertEqual(q.suggested_kana('冷笑界隈'),'')
        self.assertEqual(q.suggested_kana('未読'),'')

    def test_evidence_priority_not_translation_confidence(self):
        result=q.assess_candidate('謎のミーム',EVIDENCE,NOW,s.BLACKLIST)
        self.assertEqual(result['status'],'needs_human_review')
        self.assertIn('不是词义或翻译准确率',result['priorityMeaning'])
        self.assertGreater(result['reviewPriority'],0)

    def test_reject_plain_or_invalid_terms(self):
        for word in ('情報','会社','https://abc.example','abc','単語\n偽装','a'):
            result=q.assess_candidate(word,EVIDENCE,NOW,s.BLACKLIST)
            self.assertEqual(result['status'],'reject_candidate',word)
            self.assertEqual(result['reviewPriority'],0)

    def test_expired_future_sources_rejected(self):
        for dt in ('2026-01-01','2026-11-01'):
            evidence=[{'url':s.CURRENT_REPORT,'date':dt,'rank':1}]
            self.assertEqual(q.assess_candidate('新しいミーム',evidence,NOW,s.BLACKLIST)['status'],'reject_candidate')

    def test_unverified_drafts_never_auto_approve(self):
        provider=FakeTranslator()
        result=q.enrich_review_queue([{'jp':'ネットミーム','evidence':EVIDENCE}],[],NOW,s.BLACKLIST,enable_translation=True,translator=provider)
        self.assertEqual(len(provider.calls),2)
        self.assertEqual(result[0]['translationDraft']['zh'],'网络热门说法')
        self.assertEqual(result[0]['translationDraft']['en'],'trending internet slang')
        self.assertFalse(result[0]['translationDraft']['verified'])
        self.assertFalse(result[0]['approvedForPublication'])

    def test_cached_drafts_not_retranslated(self):
        provider=FakeTranslator()
        item=[{'jp':'ネットミーム','evidence':EVIDENCE}]
        first=q.enrich_review_queue(item,[],NOW,s.BLACKLIST,enable_translation=True,translator=provider)
        second=q.enrich_review_queue(item,first,NOW,s.BLACKLIST,enable_translation=True,translator=provider)
        self.assertEqual(len(provider.calls),2)
        self.assertEqual(second[0]['translationStatus'],'cached_unverified')

    def test_budget_limits_requests(self):
        provider=FakeTranslator()
        rows=q.enrich_review_queue([{'jp':'ネットミーム','evidence':EVIDENCE},
             {'jp':'ドパおば','evidence':EVIDENCE}],[],NOW,s.BLACKLIST,
             enable_translation=True,translator=provider,max_items=1)
        self.assertEqual(len(provider.calls),2)
        self.assertEqual(rows[1]['translationStatus'],'not_requested')

    def test_bad_translation_results_rejected(self):
        for zh,en in [('MYMEMORY WARNING: quota','trending'),('hello','trending'),
                      ('ネットミーム','ネットミーム'),('', '')]:
            provider=FakeTranslator({'zh-CN':zh,'en':en})
            result=q.enrich_review_queue([{'jp':'ネットミーム','evidence':EVIDENCE}],[],NOW,s.BLACKLIST,
                 enable_translation=True,translator=provider)
            self.assertNotEqual(result[0]['translationStatus'],'draft_unverified')
            self.assertFalse(result[0]['approvedForPublication'])

    def test_provider_failure_does_not_interrupt(self):
        provider=FakeTranslator(fail=True)
        result=q.enrich_review_queue([{'jp':'ネットミーム','evidence':EVIDENCE}],[],NOW,s.BLACKLIST,
             enable_translation=True,translator=provider)
        self.assertEqual(result[0]['translationStatus'],'provider_failed')
        self.assertFalse(result[0]['approvedForPublication'])

    def test_offline_mode_never_calls_provider(self):
        provider=FakeTranslator()
        fixture='''<meta property="article:published_time" content="2026-10-20">
          <h3>今流行っている言葉は？</h3><p>1位 謎のミーム (30.0%)</p>
          <h3>今流行っている物事は？</h3>'''
        with tempfile.TemporaryDirectory() as d:
            feed=s.run(d,CATALOG,fixture=fixture,no_network=True,now=NOW,
                translate_pending=True,translator=provider)
            self.assertEqual(provider.calls,[])
            self.assertFalse(any(i['jp']=='謎のミーム' for i in feed['items']))

    def test_integration_candidate_never_in_public_feed(self):
        provider=FakeTranslator()
        fixture='''<meta property="article:published_time" content="2026-10-20">
          <h3>今流行っている言葉は？</h3>
          <p>1位 ネットミーム (22.3%)</p><p>2位 情報 (8.0%)</p>
          <h3>今流行っている物事は？</h3>'''
        with tempfile.TemporaryDirectory() as d:
            feed=s.run(d,CATALOG,fixture=fixture,now=NOW,
                translate_pending=True,translator=provider)
            pending=json.loads((Path(d)/'slang_pending.json').read_text(encoding='utf8'))['items']
            self.assertEqual(len(pending),1)
            self.assertEqual(pending[0]['jp'],'ネットミーム')
            self.assertEqual(pending[0]['evidence'][0]['date'],'2026-10-20')
            self.assertEqual(pending[0]['translationDraft']['en'],'trending internet slang')
            self.assertFalse(pending[0]['approvedForPublication'])
            self.assertFalse(any(i['jp']=='ネットミーム' for i in feed['items']))
            self.assertEqual(feed['counts']['pendingReview'],1)
            self.assertEqual(len(s.load_catalog(CATALOG)),14)
            s.run(d,CATALOG,fixture=fixture,now=NOW,translate_pending=True,translator=provider)
            self.assertEqual(len(provider.calls),2)

    def test_public_provider_request_has_no_secret(self):
        class FakeResponse:
            def __enter__(self):return self
            def __exit__(self,*args):return None
            def read(self,n):return json.dumps({'responseStatus':200,
                'responseData':{'translatedText':'网络热词'}}).encode()
        with patch.object(q.urllib.request,'urlopen',return_value=FakeResponse()) as mocked:
            self.assertEqual(q.MyMemoryDraftProvider().translate('ネットミーム','zh-CN'),'网络热词')
            request=mocked.call_args.args[0]
            self.assertTrue(request.full_url.startswith('https://api.mymemory.translated.net/get?'))
            self.assertIn('langpair=ja%7Czh-CN',request.full_url)
            self.assertNotIn('key=',request.full_url)

    def test_approved_catalog_unchanged(self):
        before=CATALOG.read_bytes()
        q.enrich_review_queue([{'jp':'ネットミーム','evidence':EVIDENCE}],[],NOW,s.BLACKLIST,
           enable_translation=True,translator=FakeTranslator())
        self.assertEqual(before,CATALOG.read_bytes())

if __name__=='__main__':unittest.main()
