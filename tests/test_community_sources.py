"""Regression suite for public community discovery: no personal content, no auto-publication."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from sys import path
from unittest.mock import patch

path.insert(0,str(Path(__file__).resolve().parents[1]))
import community_sources as c
import slang_only as s

NOW=datetime(2026,10,30,9,0,tzinfo=c.JST)
CATALOG=Path(__file__).resolve().parents[1]/'slang_terms.json'

HATENA_RDF='''<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:dc="http://purl.org/dc/elements/1.1/">
 <item>
  <title>若者言葉「新ドパ構文」の意味とは？ネットスラングの新表現</title>
  <link>https://example.net/blog/1</link>
  <dc:date>2026-10-29T12:00:00+09:00</dc:date>
  <description><![CDATA[ネットで話題の表現「新ドパ構文」。]]></description>
 </item>
 <item>
  <title>人気の記事「学校」の話題</title>
  <link>https://example.net/blog/2</link>
  <dc:date>2026-10-29T12:00:00+09:00</dc:date>
 </item>
</rdf:RDF>'''.encode('utf-8')
MASTODON_RSS='''<rss><channel>
  <item><title>ネットスラング「新ドパ構文」が流行語になったらしい</title>
  <link>https://mastodon.social/@anon/1234</link>
  <pubDate>Thu, 29 Oct 2026 12:00:00 +0900</pubDate></item>
  <item><title>普通の記事「情報」 ネットスラング？</title>
  <link>https://mastodon.social/@anon/1235</link>
  <pubDate>Thu, 29 Oct 2026 12:00:00 +0900</pubDate></item>
</channel></rss>'''.encode()
ATOM='''<feed xmlns="http://www.w3.org/2005/Atom">
 <entry><title>若者言葉『メロ新語』の話題</title>
 <link href="https://example.org/article/3"/><updated>2026-10-29T15:00:00+09:00</updated>
 <summary>『メロ新語』とは？</summary></entry>
</feed>'''.encode()

def fake_feed(url):
    if 'hatena' in url:return HATENA_RDF
    if 'mastodon' in url:return MASTODON_RSS
    raise AssertionError('unexpected URL')

class CommunitySourceTests(unittest.TestCase):
    def test_configured_urls_are_bounded_and_known(self):
        self.assertEqual(len(c.SOURCES),4)
        self.assertTrue(all(u.startswith('https://') for _,u in c.SOURCES))
        self.assertEqual(len(set(u for _,u in c.SOURCES)),4)

    def test_rdf_rss_and_atom_parser(self):
        self.assertEqual(len(c.read_feed(HATENA_RDF,'hatena_slang',NOW)),2)
        self.assertEqual(len(c.read_feed(MASTODON_RSS,'mastodon_trends',NOW)),2)
        rows=c.read_feed(ATOM,'atom_sample',NOW)
        self.assertEqual(rows[0]['url'],'https://example.org/article/3')
        self.assertEqual(rows[0]['date'],'2026-10-29')

    def test_extract_only_quoted_explicit_slang(self):
        post=c.read_feed(HATENA_RDF,'hatena_slang',NOW)[0]
        self.assertEqual(c.extract_claimed_slang(post,s.BLACKLIST),['新ドパ構文'])
        self.assertEqual(c.extract_claimed_slang({'title':'日本で「映画」が人気','summary':''},s.BLACKLIST),[])
        self.assertEqual(c.extract_claimed_slang({'title':'流行語「会社」と「情報」','summary':''},s.BLACKLIST),[])

    def test_source_state_does_not_store_body_or_username(self):
        rows,state,status=c.collect_community(NOW,{},s.BLACKLIST,set(),fetcher=fake_feed)
        self.assertEqual({r['jp'] for r in rows},{'新ドパ構文'})
        self.assertEqual(len(rows[0]['evidence']),2)
        self.assertEqual(len(status),4)
        data=json.dumps(state,ensure_ascii=False)
        self.assertNotIn('description',data)
        self.assertNotIn('summary',data)
        self.assertNotIn('title',data)
        self.assertNotIn('若者言葉',data)
        self.assertNotIn('ネットスラング',data)

    def test_repeat_scan_does_not_duplicate_evidence(self):
        rows,state,status=c.collect_community(NOW,{},s.BLACKLIST,set(),fetcher=fake_feed)
        rows2,state2,status2=c.collect_community(NOW,state,s.BLACKLIST,set(),fetcher=fake_feed)
        self.assertEqual(rows2,rows)
        self.assertEqual(len(rows2[0]['evidence']),2)

    def test_rss_errors_do_not_break_survey_collector(self):
        def broken(_):raise TimeoutError('test')
        rows,state,status=c.collect_community(NOW,{},s.BLACKLIST,set(),fetcher=broken)
        self.assertEqual(rows,[])
        self.assertEqual(sum(x['status']=='error' for x in status),4)

    def test_stale_dates_and_unsafe_links_are_excluded(self):
        old=HATENA_RDF.replace(b'2026-10-29',b'2026-08-01')
        self.assertEqual(c.read_feed(old,'hatena_slang',NOW),[])
        for link in ('http://evil.test','https://127.0.0.1/test','https://localhost/','https://user:pass@site.jp/a'):
            self.assertEqual(c.safe_link(link),'')
        self.assertEqual(c.safe_link('https://example.jp/post#reply'),'https://example.jp/post')

    def test_known_curated_words_not_queued(self):
        known={s.norm('新ドパ構文')}
        rows,_,_=c.collect_community(NOW,{},s.BLACKLIST,known,fetcher=fake_feed)
        self.assertEqual(rows,[])

    def test_single_social_mention_stays_untranslated(self):
        from translation_review import enrich_review_queue
        item={'jp':'ネット新語','sources':['https://example.org/a'],
          'evidence':[{'url':'https://example.org/a','date':'2026-10-29','rank':None}],
          'status':'community_signal_needs_independent_meaning_review',
          'communityEvidenceCount':1}
        class NoTranslation:
            def translate(self,*args):raise AssertionError('should not call translation')
        row=enrich_review_queue([item],[],NOW,s.BLACKLIST,
            enable_translation=True,translator=NoTranslation())[0]
        self.assertEqual(row['translationStatus'],'awaiting_independent_community_evidence')
        self.assertFalse(row['approvedForPublication'])

    def test_end_to_end_community_pending_cannot_change_public_feed(self):
        with tempfile.TemporaryDirectory() as d, patch.object(c,'fetch_feed',side_effect=fake_feed):
            # Fake survey input guarantees stable baseline and never makes
            # external requests. With fixture, community is offline, so insert
            # bounded community evidence as if found in a prior scheduled run.
            community,prior,_=c.collect_community(NOW,{},s.BLACKLIST,set(),fetcher=fake_feed)
            Path(d,'community_state.json').write_text(json.dumps(prior,ensure_ascii=False),encoding='utf8')
            html='''<meta property="article:published_time" content="2026-10-02">
              <h3>今流行っている言葉は？</h3><p>1位 メロい (23%)</p>
              <h3>今流行っている物事は？</h3>'''
            feed=s.run(d,CATALOG,fixture=html,now=NOW)
            self.assertEqual(feed['counts']['words'],11)
            self.assertEqual(feed['counts']['communityCandidateWords'],1)
            pending=json.loads(Path(d,'slang_pending.json').read_text(encoding='utf-8'))['items']
            self.assertEqual(len(pending),1)
            self.assertEqual(pending[0]['jp'],'新ドパ構文')
            self.assertFalse(pending[0]['approvedForPublication'])
            self.assertEqual(len(s.load_catalog(CATALOG)),11)

    def test_community_merge_with_survey_deduplicates(self):
        a=[{'jp':'新ドパ構文','sources':['https://example.org/r'],
            'evidence':[{'url':'https://example.org/r','date':'2026-10-29','rank':1}],
            'status':'needs_human_definition_and_bilingual_review'}]
        comm=[{'jp':'新ドパ構文','evidence':[{'url':'https://example.org/c',
             'date':'2026-10-29','platform':'mastodon_slang'}]}]
        res=c.merge_pending(a,comm,set(),s.norm)
        self.assertEqual(len(res),1)
        self.assertEqual(len(res[0]['sources']),2)
        self.assertEqual(res[0]['evidence'][0]['rank'],1)

if __name__=='__main__':unittest.main()
