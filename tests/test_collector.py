"""Offline collector regression tests (no RSS network needed)."""
import importlib.util
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

p=Path(__file__).resolve().parents[1]/'collector.py'
spec=importlib.util.spec_from_file_location('collector',p)
c=importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

class FakeToken:
 def __init__(self,surface):
  self.surface=surface;self.base_form=surface;self.reading={'生成':'セイセイ','学校':'ガッコウ','教育':'キョウイク','学習':'ガクシュウ','未来':'ミライ','導入':'ドウニュウ','広がる':'ヒロガル','話題':'ワダイ','新しい':'アタラシイ','AI':'エーアイ'}.get(surface,surface)
  self.part_of_speech='形容詞,自立,*,*' if surface=='新しい' else '名詞,一般,*,*'
class FakeTokenizer:
 def tokenize(self,text):
  for word in ['生成','AI','学校','教育','学習','未来','導入','話題','新しい','広がる']:
   text=text.replace(word,' '+word+' ')
  return [FakeToken(v) for v in text.split()]

class CollectorTest(unittest.TestCase):
 def setUp(self):
  self.t=FakeTokenizer()
  self.now=datetime(2026,10,24,tzinfo=timezone(timedelta(hours=9)))
 def test_rss_atom_rdf(self):
  src=c.SOURCE_FEEDS[1]
  body=(Path(__file__).parent/'fixtures/hatena_general.xml').read_bytes()
  items=c.parse_feed(src,body)
  self.assertEqual(len(items),2)
  rdf=(Path(__file__).parent/'fixtures/hatena_tech.xml').read_bytes()
  self.assertEqual(len(c.parse_feed(src,rdf)),1)
 def test_dedup_incremental(self):
  src=c.SOURCE_FEEDS[1]
  body=(Path(__file__).parent/'fixtures/hatena_general.xml').read_bytes()
  docs=c.parse_feed(src,body)
  state={'terms':{},'seenDocs':{}}
  self.assertEqual(c.ingest(docs,state,self.t,self.now),2)
  self.assertEqual(c.ingest(docs,state,self.t,self.now),0)
  feed=c.build_feed(state,self.now,[])
  self.assertGreater(feed['counts']['words'],0)
  self.assertEqual(len({v['id'] for v in feed['items']}),len(feed['items']))
  self.assertTrue(all(v['docCount']>=1 for v in feed['items']))
 def test_no_cross_source_duplication(self):
  s=c.SOURCE_FEEDS[1]
  title='生成AI 学校'
  a=[{'id':'x','title':title,'url':'https://example.org/1','source':'A','category':'科技','kind':'freq'},
     {'id':'y','title':title,'url':'https://example.org/2','source':'B','category':'娱乐','kind':'trend'}]
  state={'terms':{},'seenDocs':{}}
  c.ingest(a,state,self.t,self.now)
  self.assertIn('生成',state['terms'])
  self.assertEqual(state['terms']['生成']['docCount'],2)
  self.assertEqual(set(state['terms']['生成']['kinds']),{'freq','trend'})
 def test_hiragana_safety_and_link(self):
  self.assertEqual(c.hiragana('ショウガッコウ'),'しょうがっこう')
  self.assertFalse(c.japanese_surface('hello'))
  self.assertEqual(c.safe_url('javascript:alert(1)'),'')
  self.assertFalse(c.japanese_surface('あ'))
 def test_failure_data_does_not_clear(self):
  state={'terms':{},'seenDocs':{}}
  c.ingest([{'id':'z','title':'学校の教育','url':'https://example.org/a','source':'A','category':'学习','kind':'freq'}],state,self.t,self.now)
  count=len(state['terms']);c.ingest([],state,self.t,self.now)
  self.assertEqual(len(state['terms']),count)

if __name__=='__main__':unittest.main()
