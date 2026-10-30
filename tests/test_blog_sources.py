"""No-network regression checks for creator-RSS slang discovery."""
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from sys import path
from unittest.mock import patch

path.insert(0,str(Path(__file__).resolve().parents[1]))
import blog_sources as b
import slang_only as s
import community_sources as c

NOW=datetime(2026,10,30,10,0,tzinfo=timezone(timedelta(hours=9)))
CATALOG=Path(__file__).resolve().parents[1]/'slang_terms.json'
XML=b'''<rss><channel>
<item><title>2026 latest internet slang</title></item></channel></rss>'''

def note_feed(slug, term='チルる', date='2026-10-20'):
    return (f'''<?xml version="1.0" encoding="UTF-8"?>
    <rss><channel><item>
    <title>2026年のネットスラング「{term}」の意味や使い方を紹介</title>
    <link>https://note.com/{slug}/n/nabcdef012345</link>
    <pubDate>{date}T09:00:00+09:00</pubDate>
    <description><![CDATA[今年の若者言葉「{term}」について詳しく解説。]]></description>
    </item></channel></rss>''').encode('utf-8')

def fake_rss(url):
    slug=url.split('/')[3]
    if slug in ('nihon_5','open_fairy44'):
        return note_feed(slug)
    return b'<rss><channel></channel></rss>'

class BloggerTests(unittest.TestCase):
    def test_creator_feeds_are_explicitly_allowlisted(self):
        self.assertGreaterEqual(len(b.CREATORS),4)
        self.assertEqual(len({u for _,_,u in b.CREATORS}),len(b.CREATORS))
        self.assertTrue(all(u.startswith('https://note.com/') and u.endswith('/rss') for _,_,u in b.CREATORS))

    def test_article_title_has_clear_slang_context(self):
        article={'title':'2026年のネットスラング「チルる」の意味や使い方を紹介',
                 'summary':'若者言葉「チルる」について詳しく解説。'}
        self.assertEqual(b.extract_blog_terms(article,s.BLACKLIST),['チルる'])
        self.assertEqual(b.extract_blog_terms({'title':'最近の学校の「授業」','summary':'流行語の紹介'},s.BLACKLIST),[])
        self.assertEqual(b.extract_blog_terms({'title':'2026ネットスラング「情報」','summary':''},s.BLACKLIST),[])

    def test_article_body_not_copied_into_state(self):
        rows,state,status=b.collect_blogs(NOW,{},s.BLACKLIST,set(),fetcher=fake_rss)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['jp'],'チルる')
        self.assertEqual(len(rows[0]['evidence']),2)
        self.assertEqual(len(status),len(b.CREATORS))
        serialized=json.dumps(state,ensure_ascii=False)
        self.assertNotIn('summary',serialized)
        self.assertNotIn('2026年の',serialized)
        self.assertNotIn('description',serialized)
        self.assertNotIn('creator',serialized)

    def test_two_different_creators_become_review_lead_not_auto_pub(self):
        rows,_,_=b.collect_blogs(NOW,{},s.BLACKLIST,set(),fetcher=fake_rss)
        merged=b.combine_signals([],rows)
        pending=c.merge_pending([],merged,set(),s.norm)
        self.assertEqual(len(pending),1)
        self.assertEqual(pending[0]['jp'],'チルる')
        self.assertEqual(pending[0]['communityEvidenceCount'],2)
        self.assertEqual(pending[0]['status'],'community_signal_needs_independent_meaning_review')
        self.assertEqual({e['rank'] for e in pending[0]['evidence']},{None})

    def test_single_creator_is_a_lead_not_an_approved_term(self):
        one={'jp':'チルる','evidence':[{'url':'https://note.com/nihon_5/n/nabcdef012345',
                    'date':'2026-10-20','platform':'blogger:nihon_5'}]}
        self.assertEqual(c.merge_pending([],b.combine_signals([],[one]),set(),s.norm),[])

    def test_no_promotion_to_public_feed_even_with_two_creators(self):
        rows,prior,_=b.collect_blogs(NOW,{},s.BLACKLIST,set(),fetcher=fake_rss)
        with tempfile.TemporaryDirectory() as d:
            Path(d,'blog_state.json').write_text(json.dumps(prior,ensure_ascii=False),encoding='utf8')
            feed=s.run(d,CATALOG,no_network=True,now=NOW)
            pending=json.loads(Path(d,'slang_pending.json').read_text(encoding='utf8'))['items']
            self.assertEqual(feed['counts']['words'],11)
            self.assertEqual(feed['counts']['bloggerSignals'],1)
            self.assertEqual(feed['counts']['bloggerCandidateWords'],1)
            self.assertEqual(pending[0]['jp'],'チルる')
            self.assertFalse(pending[0]['approvedForPublication'])
            self.assertNotIn('チルる',{x['jp'] for x in feed['items']})

    def test_old_posts_expire_and_do_not_count_as_new(self):
        rows,_,_=b.collect_blogs(NOW,{},s.BLACKLIST,set(),
            fetcher=lambda url:note_feed('nihon_5',date='2026-02-01'))
        self.assertEqual(rows,[])
        rows,_,_=b.collect_blogs(NOW,{},s.BLACKLIST,set(),
            fetcher=lambda url:note_feed('nihon_5',date='2026-09-23'))
        self.assertEqual(len(rows),1)

    def test_known_words_or_wrong_creator_link_ignored(self):
        rows,_,_=b.collect_blogs(NOW,{},s.BLACKLIST,{s.norm('チルる')},fetcher=fake_rss)
        self.assertEqual(rows,[])
        bad=lambda url:note_feed('someone_else')
        rows,_,_=b.collect_blogs(NOW,{},s.BLACKLIST,set(),fetcher=bad)
        self.assertEqual(rows,[])

    def test_failure_of_one_feed_does_not_break_other_bloggers(self):
        def partial(url):
            if '/50s_lab/' in url:raise TimeoutError('test blocked')
            return fake_rss(url)
        rows,_,status=b.collect_blogs(NOW,{},s.BLACKLIST,set(),fetcher=partial)
        self.assertEqual(len(rows),1)
        self.assertEqual(sum(x['status']=='error' for x in status),1)

    def test_duplicate_rss_runs_retain_citations_once(self):
        rows,state,_=b.collect_blogs(NOW,{},s.BLACKLIST,set(),fetcher=fake_rss)
        newer,_,_=b.collect_blogs(NOW,state,s.BLACKLIST,set(),fetcher=fake_rss)
        self.assertEqual(newer,rows)

    def test_blog_aggregation_merges_with_community_without_duplicate_urls(self):
        blog=[{'jp':'チルる','evidence':[{'url':'https://note.com/nihon_5/n/nabcdef012345',
                    'date':'2026-10-20','platform':'blogger:nihon_5'}]}]
        community=[{'jp':'チルる','evidence':[{'url':'https://note.com/nihon_5/n/nabcdef012345',
                    'date':'2026-10-20','platform':'hatena_title_trends'}]}]
        rows=b.combine_signals(community,blog)
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['evidence']),1)
        self.assertEqual(c.merge_pending([],rows,set(),s.norm),[])

    def test_bad_source_url_rejected_without_outbound_request(self):
        class Redirect:
            def geturl(self):return 'http://example.net/private.xml'
            def read(self, n):return b'<rss/>'
            def __enter__(self):return self
            def __exit__(self,*a):return None
        with patch.object(b.urllib.request,'urlopen',return_value=Redirect()):
            with self.assertRaises(ValueError):
                b.fetch_blogger(b.CREATORS[0][2])
        with self.assertRaises(ValueError):
            b.fetch_blogger('https://internal.example/rss')

if __name__=='__main__':unittest.main()
