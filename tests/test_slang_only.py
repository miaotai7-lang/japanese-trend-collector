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
    def test_publisher_html_without_spaces_and_fullwidth_percent(self):
        page = """<h3>❚ 今流行っている言葉は？</h3>
        <p>1位<span>メロい</span><span>(20.3%)</span></p>
        <p>2位<strong>ドパガキ</strong>（14.0％）</p>
        <h3>❚ 今流行っている物事は？</h3><p>1位商品（99.0%）</p>"""
        self.assertEqual([x['jp'] for x in s.ranked_slang_from_report(page)],['メロい','ドパガキ'])

    def test_contents_heading_does_not_hide_real_ranking(self):
        """The publisher repeats the same heading in its TOC and article."""
        page = """<nav><p>目次</p>
        <p>2 ❚ 今流行っている言葉は？</p>
        <p>3 ❚ 今流行っている物事は？</p>
        </nav><article>
        <h3>❚ 今流行っている言葉は？</h3>
        <p>1位 メロい (20.3%)</p>
        <p>2位 ドパガキ (14.0%)</p>
        <p>4位 滅 (6.8%)</p>
        <p>5位 ネ申 (2.7%)</p>
        <h3>❚ 今流行っている物事は？</h3>
        <p>1位 商品 (99.9%)</p>
        </article>"""
        names=[x['jp'] for x in s.ranked_slang_from_report(page)]
        self.assertEqual(names,['メロい','ドパガキ','滅','ネ申'])
        self.assertNotIn('商品',names)

    def test_contents_only_cannot_generate_fake_slang(self):
        page="""<div>目次</div>
        <p>2 ❚ 今流行っている言葉は？</p>
        <p>3 ❚ 今流行っている物事は？</p>
        <p>1位 商品 (33.9%)</p>"""
        self.assertEqual(s.ranked_slang_from_report(page),[])

    def test_archive_discovers_new_surveys_without_ordinary_articles(self):
        page = """<a href="/monthlytrendsurvey/4800/">2026 冬の特大号 最新トレンド</a>
        <a href="/monthlytrendsurvey/4700/">若者言葉ランキング</a>
        <a href="/monthlytrendsurvey/4600/">父の日の調査</a>
        <a href="https://evil.example.com/monthlytrendsurvey/6000/">最新トレンド</a>"""
        self.assertEqual(s.read_survey_index(page),[
            'https://shibuya-trendresearch.jp/monthlytrendsurvey/4800/',
            'https://shibuya-trendresearch.jp/monthlytrendsurvey/4700/'])

    def test_source_success_requires_parsed_rankings_not_just_http_200(self):
        from unittest.mock import patch
        bogus='<h3>今流行っている言葉は？</h3><p>不是榜单</p>'.encode('utf-8')
        with tempfile.TemporaryDirectory() as d, patch.object(s,'fetch_public',return_value=bogus):
            feed=s.run(d,CATALOG,now=NOW,community_enabled=False)
            self.assertEqual(feed['counts']['sourceSucceeded'],0)
            self.assertTrue(any(x['name']=='有效流行语调查解析' and x['status']=='error' for x in feed['sourceStatus']))

    def test_new_ranking_from_archive_enters_pending_without_publication(self):
        from unittest.mock import patch
        archive='<a href="/monthlytrendsurvey/4800/">2026 冬の特大号 最新トレンド</a>'.encode('utf-8')
        official='''<meta property="article:published_time" content="2026-10-10"><h3>今流行っている言葉は？</h3>
        <p>1位<span>新しいネット梗</span>(20.0%)</p><h3>今流行っている物事は？</h3>'''.encode('utf-8')
        def fake_fetch(url,*args,**kw):
            if url==s.SURVEY_INDEX:return archive
            if url==s.SOURCE_FEED:raise TimeoutError('RSS unavailable')
            if url.endswith('/4800/'):return official
            raise TimeoutError('old report failed')
        with tempfile.TemporaryDirectory() as d, patch.object(s,'fetch_public',side_effect=fake_fetch):
            feed=s.run(d,CATALOG,now=NOW,community_enabled=False)
            pending=json.loads((Path(d)/'slang_pending.json').read_text(encoding='utf-8'))['items']
            self.assertIn('新しいネット梗',[x['jp'] for x in pending])
            self.assertEqual(feed['counts']['pendingReview'],1)
            self.assertEqual(feed['counts']['sourceSucceeded'],1)
            self.assertNotIn('新しいネット梗',[x['jp'] for x in feed['items']])

    def test_rss_only_discovers_trend_survey_pages(self):
        feed='''<?xml version="1.0"?><rss><channel>
        <item><title>2026 秋のトレンド調査</title><link>https://shibuya-trendresearch.jp/monthlytrendsurvey/4622/</link></item>
        <item><title>2026 会社決算ニュース</title><link>https://shibuya-trendresearch.jp/monthlytrendsurvey/abc/</link></item>
        <item><title>別のトレンド調査</title><link>https://evil.example.net/monthlytrendsurvey/1</link></item>
        </channel></rss>'''.encode('utf8')
        self.assertEqual(s.read_survey_rss(feed),[s.CURRENT_REPORT])

if __name__=='__main__':unittest.main()
