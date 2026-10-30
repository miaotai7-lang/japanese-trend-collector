"""Evidence-gated public updates never trust machine translation drafts."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sys import path
path.insert(0,str(Path(__file__).resolve().parents[1]))
from slang_only import (load_catalog, reviewed_auto_terms, ranked_slang_from_report,
                        run, CURRENT_REPORT, JST, REVIEWED_AUTO_PATH)

CATALOG=Path(__file__).resolve().parents[1]/'slang_terms.json'
NOW=datetime(2026,10,30,9,0,tzinfo=JST)
REPORT='''<meta property="article:published_time" content="2026-10-02T11:00:00">
<nav><p>目次</p><p>2 今流行っている言葉は？</p><p>3 今流行っている物事は？</p></nav>
<h3>今流行っている言葉は？</h3>
<p>1位 メロい (20.3%)</p>
<p>4位 滅 (6.8%)</p>
<p>5位 ネ申 (2.7%)</p>
<p>8位 ショートスリーパー (1.8%)</p>
<p>9位 アツい (1.4%)</p>
<h3>今流行っている物事は？</h3>
<p>1位 商品 (33.0%)</p>'''


class AutoPublishTests(unittest.TestCase):
    def test_editorial_file_has_independent_references(self):
        data=json.loads(REVIEWED_AUTO_PATH.read_text(encoding='utf8'))
        names={x['jp'] for x in data['terms']}
        self.assertEqual(names,{'ネ申','滅'})
        self.assertTrue(all(x['reviewStatus']=='editor-reviewed'
            and x['kana'] and x['zh'] and x['en'] and len(x['meaningReferences'])>=2
            for x in data['terms']))

    def test_single_character_only_exact_reviewed_slang(self):
        found=ranked_slang_from_report(REPORT)
        self.assertIn('滅',[x['jp'] for x in found])
        self.assertNotIn('商品',[x['jp'] for x in found])

    def test_end_to_end_real_ranking_fixture_publication(self):
        with tempfile.TemporaryDirectory() as d:
            feed=run(d,CATALOG,fixture=REPORT,now=NOW)
            terms={x['jp']:x for x in feed['items']}
            self.assertEqual(feed['counts']['autoPublishedReviewed'],2)
            self.assertEqual(feed['counts']['reviewedCatalog'],11)
            self.assertEqual(len(terms),13)
            self.assertEqual(terms['滅']['kana'],'めつ')
            self.assertEqual(terms['ネ申']['kana'],'かみ')
            self.assertIn('独立核对',terms['ネ申']['verification'])
            self.assertNotIn('ショートスリーパー',terms)
            self.assertNotIn('アツい',terms)
            pending=json.loads((Path(d)/'slang_pending.json').read_text(encoding='utf8'))['items']
            self.assertEqual({p['jp'] for p in pending},{'ショートスリーパー','アツい'})
            self.assertTrue(all(not p['approvedForPublication'] for p in pending))

    def test_no_stale_auto_publication(self):
        future=NOW+timedelta(days=135)
        with tempfile.TemporaryDirectory() as d:
            feed=run(d,CATALOG,fixture=REPORT,now=future)
            self.assertEqual(feed['counts']['autoPublishedReviewed'],0)
            self.assertEqual(len(feed['items']),0)

    def test_no_report_means_no_auto_publication(self):
        with tempfile.TemporaryDirectory() as d:
            feed=run(d,CATALOG,no_network=True,now=NOW)
            self.assertEqual(feed['counts']['autoPublishedReviewed'],0)
            self.assertEqual(feed['counts']['words'],11)

    def test_wrong_report_url_cannot_authorize_word(self):
        catalog=load_catalog(CATALOG)
        state={'reports':[{'url':'https://shibuya-trendresearch.jp/monthlytrendsurvey/9999/',
                            'date':'2026-10-02','ranked':[{'jp':'ネ申','rank':1}]}]}
        self.assertEqual(reviewed_auto_terms(catalog,state,NOW),[])

    def test_bad_report_date_cannot_authorize_word(self):
        catalog=load_catalog(CATALOG)
        state={'reports':[{'url':CURRENT_REPORT,'date':'2026-10-29',
                           'ranked':[{'jp':'ネ申','rank':1}]}]}
        self.assertEqual(reviewed_auto_terms(catalog,state,NOW),[])

    def test_editorial_entries_never_mutate_original_catalog(self):
        before=CATALOG.read_bytes()
        with tempfile.TemporaryDirectory() as d:
            run(d,CATALOG,fixture=REPORT,now=NOW)
        self.assertEqual(before,CATALOG.read_bytes())
        self.assertEqual(len(load_catalog(CATALOG)),11)

    def test_previous_feed_item_ids_stable(self):
        with tempfile.TemporaryDirectory() as d:
            plain=run(d,CATALOG,no_network=True,now=NOW)
            enriched=run(d,CATALOG,fixture=REPORT,now=NOW)
            a={x['jp']:x['id'] for x in plain['items']}
            b={x['jp']:x['id'] for x in enriched['items']}
            self.assertEqual({k:b[k] for k in a},a)

if __name__=='__main__':unittest.main()
