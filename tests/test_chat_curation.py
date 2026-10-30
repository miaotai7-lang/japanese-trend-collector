"""Editorial checks for slang discovered through the chat search (no API key)."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from sys import path
path.insert(0,str(Path(__file__).resolve().parents[1]))
import slang_only as s

ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/'slang_terms.json'
NOW=datetime(2026,10,30,12,0,tzinfo=s.JST)
BASELINE={'メロい','ドパガキ','フレネミー','シャバい','ワッサー','ドパい',
          'ドパおじ','ドパおば','冷笑系','冷笑界隈','〇〇すぎて滅！'}
NEW={'ワホー','冷笑','良かったこの距離で'}

class ChatCurationTests(unittest.TestCase):
    def test_existing_eleven_preserved_plus_three_researched(self):
        terms=s.load_catalog(CATALOG)
        self.assertEqual(len(terms),14)
        names={t['jp'] for t in terms}
        self.assertTrue(BASELINE.issubset(names))
        self.assertEqual(names-BASELINE,NEW)

    def test_new_words_have_contextually_checked_bilingual_defs_and_sources(self):
        terms={r['jp']:r for r in s.load_catalog(CATALOG)}
        for word in NEW:
            e=terms[word]
            self.assertTrue(all(e.get(k) for k in ('jp','kana','zh','en','source','publisher','referenceDate')))
            self.assertTrue(s.trusted_url(e['source']))
            self.assertEqual(e['reviewStatus'],'editor-reviewed')
            self.assertGreaterEqual(len(set(e['meaningReferences'])),2)
            self.assertLessEqual((NOW.date()-__import__('datetime').date.fromisoformat(e['referenceDate'])).days,120)

    def test_reviewed_meaning_distinctions_are_not_literal_machine_drafts(self):
        terms={r['jp']:r for r in s.load_catalog(CATALOG)}
        self.assertIn('兴奋',terms['ワホー']['zh'])
        self.assertIn('认真',terms['冷笑']['zh'])
        self.assertIn('网络梗',terms['良かったこの距離で']['zh'])
        self.assertNotEqual(terms['冷笑']['zh'],'嘲笑')

    def test_kana_comparison_dedup_without_breaking_original_word_ids(self):
        self.assertEqual(s.kana_equivalent('ワホー'),s.kana_equivalent('わほー'))
        self.assertEqual(s.kana_equivalent('メロい'),s.kana_equivalent('めろい'))
        self.assertNotEqual(s.norm('メロい'),s.norm('めろい'))
        with tempfile.TemporaryDirectory() as d:
            f=s.run(d,CATALOG,no_network=True,now=NOW)
        byname={x['jp']:x for x in f['items']}
        self.assertEqual(byname['メロい']['id'],hashlib.sha256(s.norm('メロい').encode('utf8')).hexdigest()[:20])
        self.assertEqual(f['counts']['reviewedCatalog'],14)
        self.assertEqual(len(f['items']),14)

    def test_source_rank_with_hiragana_variant_not_a_duplicate_pending(self):
        # Publisher sometimes spells ワホー as わほー and vice versa.
        report='''<meta property="article:published_time" content="2026-10-02">
            <h3>今流行っている言葉は？</h3>
            <p>1位 わほー (23.0%)</p><p>2位 メロい (14.0%)</p>
            <h3>今流行っている物事は？</h3>'''
        with tempfile.TemporaryDirectory() as d:
            f=s.run(d,CATALOG,fixture=report,now=NOW)
            pending=json.loads((Path(d)/'slang_pending.json').read_text(encoding='utf8'))['items']
        self.assertNotIn('わほー',{x['jp'] for x in pending})
        self.assertEqual(len(f['items']),16) # 14 curated + 2 previously reviewed
        self.assertEqual(f['counts']['pendingReview'],0)

    def test_no_unapproved_translation_leaks_into_feed(self):
        with tempfile.TemporaryDirectory() as d:
            f=s.run(d,CATALOG,no_network=True,now=NOW)
        published={e['jp'] for e in f['items']}
        self.assertNotIn('アツい',published)
        self.assertNotIn('ショートスリーパー',published)
        self.assertEqual(len(published),14)

if __name__=='__main__':unittest.main()
