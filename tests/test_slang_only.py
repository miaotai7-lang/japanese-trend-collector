"""Offline regression suite for slang-only public feed. Run with stdlib unittest."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sys import path
path.insert(0,str(Path(__file__).resolve().parents[1]))
import slang_only as s
NOW=datetime(2026,10,27,12,0,tzinfo=timezone(timedelta(hours=9)))
CATALOG=Path(__file__).resolve().parents[1]/'slang_terms.json'
TEST_HTML='''<html><head><meta property="article:published_time" content="2026-10-02T12:00:00"></head>
<body><h3>❚ 今流行っている言葉は？</h3>
<p>1位 メロい (20.3%)</p><p>2位 ドパガキ (14.0%)</p><p>3位 フレネミー (7.7%)</p><p>4位 情報 (5.0%)</p><p>5位 未知の新ミーム (3.0%)</p>
<h3>❚ 今流行っている物事は？</h3><p>1位 会社 (10.0%)</p>
</body></html>'''

class SlangOnlyTest(unittest.TestCase):
    def test_current_research_catalog_has_real_bilingual_definitions(self):
        rows=s.load_catalog(CATALOG)
        self.assertGreaterEqual(len(rows),9)
        self.assertTrue(all(x['kana'] and x['zh'] and x['en'] and x['source'].startswith('https://') for x in rows))
    def test_excluded_everyday_news_words(self):
        with tempfile.TemporaryDirectory() as d:
            f=s.run(d,CATALOG,fixture=TEST_HTML,now=NOW)
            published={x['jp'] for x in f['items']}
            for w in ['情報','会社','見る','食べる','アクセス','いい','れる']:
                self.assertNotIn(w,published)
            self.assertIn('メロい',published)
            self.assertEqual(f['feedType'],'japanese-internet-slang-only')
    def test_official_ranking_section_only(self):
        names=[x['jp'] for x in s.ranked_slang_from_report(TEST_HTML)]
        self.assertEqual(names,['メロい','ドパガキ','フレネミー','未知の新ミーム'])
    def test_official_report_real_date_not_updated_to_today(self):
        self.assertEqual(s.report_published_date(TEST_HTML),'2026-10-02')
        with tempfile.TemporaryDirectory() as d:
            s.run(d,CATALOG,fixture=TEST_HTML,now=NOW)
            state=json.loads((Path(d)/'slang_state.json').read_text())
            self.assertEqual(state['reports'][0]['date'],'2026-10-02')
    def test_unreviewed_new_slang_only_in_pending(self):
        with tempfile.TemporaryDirectory() as d:
            f=s.run(d,CATALOG,fixture=TEST_HTML,now=NOW)
            pending=json.loads((Path(d)/'slang_pending.json').read_text())['items']
            self.assertIn('未知の新ミーム',[x['jp'] for x in pending])
            self.assertNotIn('未知の新ミーム',[x['jp'] for x in f['items']])
    def test_no_ordinary_state_data_leak(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'state.json').write_text(json.dumps({'terms':{'情報':{'jp':'情報','zh':'info','en':'information'}}},ensure_ascii=False))
            f=s.run(d,CATALOG,no_network=True,now=NOW)
            self.assertFalse(any(x['jp']=='情報' for x in f['items']))
    def test_stale_sources_expire_and_do_not_renew(self):
        future=NOW+timedelta(days=180)
        with tempfile.TemporaryDirectory() as d:
            f=s.run(d,CATALOG,fixture=TEST_HTML,now=future)
            self.assertEqual(len(f['items']),0)
    def test_sources_and_word_ids_stable(self):
        with tempfile.TemporaryDirectory() as d:
            a=s.run(d,CATALOG,no_network=True,now=NOW)
            b=s.run(d,CATALOG,no_network=True,now=NOW)
            self.assertEqual([w['id'] for w in a['items']],[w['id'] for w in b['items']])
            self.assertTrue(all(w['sources'] and w['sources'][0]['url'].startswith('https://') for w in a['items']))
    def test_rss_only_discovers_trend_survey_pages(self):
        feed='''<?xml version="1.0"?><rss><channel>
        <item><title>2026 秋のトレンド調査</title><link>https://shibuya-trendresearch.jp/monthlytrendsurvey/4622/</link></item>
        <item><title>2026 会社決算ニュース</title><link>https://shibuya-trendresearch.jp/monthlytrendsurvey/abc/</link></item>
        <item><title>別のトレンド調査</title><link>https://evil.example.net/monthlytrendsurvey/1</link></item>
        </channel></rss>'''.encode('utf8')
        self.assertEqual(s.read_survey_rss(feed),[s.CURRENT_REPORT])

if __name__=='__main__':unittest.main()
