import unittest
from datetime import date
from auto_discovery import discover_from_rss
class T(unittest.TestCase):
    def test_from_articles_no_manual_terms(self):
        state={'slangReviewQueue':{'x':{'jp':'サンプル語','lastSeen':'2026-10-27','mentions':2,'sources':[{'url':'https://news.example.com/x','title':'今年の若者言葉「サンプル語」の意味','publisher':'A'},{'url':'https://news2.example.com/x','title':'SNSの流行語「サンプル語」を調査','publisher':'B'}]}}}
        rows=discover_from_rss(state,today=date(2026,10,27))
        self.assertEqual(len(rows),1)
        self.assertIn('多篇',rows[0]['verification'])
        self.assertFalse(rows[0]['translationComplete'])
        self.assertEqual(rows[0]['jp'],'サンプル語')
    def test_no_news_source(self):
        state={'slangReviewQueue':{'x':{'jp':'サンプル語','lastSeen':'2026-10-27','sources':[{'url':'https://example.com/a','title':'普通の話題'}]}}}
        self.assertEqual(discover_from_rss(state,today=date(2026,10,27)),[])
    def test_not_confound_google_trends_with_word(self):
        self.assertEqual(discover_from_rss({'terms':{'流行':{}}},today=date(2026,10,27)),[])
    def test_outdated_source(self):
        state={'slangReviewQueue':{'x':{'jp':'サンプル語','lastSeen':'2026-08-01','sources':[{'url':'https://example.com/x','title':'流行語「サンプル語」'}]}}}
        self.assertEqual(discover_from_rss(state,today=date(2026,10,27)),[])
    def test_reject_non_https(self):
        s={'slangReviewQueue':{'x':{'jp':'サンプル語','lastSeen':'2026-10-27','sources':[{'url':'http://example.com/x','title':'流行語「サンプル語」'}]}}}
        self.assertFalse(discover_from_rss(s,today=date(2026,10,27)))
    def test_literal_bilingual_only(self):
        s={'slangReviewQueue':{'x':{'jp':'サンプル語','lastSeen':'2026-10-27','sources':[{'url':'https://example.com/x','title':'流行語「サンプル語」'}]}}}
        x=discover_from_rss(s,today=date(2026,10,27),jp_zh={'サンプル語':'示例词'},jp_en={})[0]
        self.assertEqual(x['zh'],'示例词');self.assertEqual(x['en'],'')
        self.assertFalse(x['translationComplete'])
if __name__=='__main__':unittest.main()
