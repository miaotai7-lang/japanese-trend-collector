"""Offline collector regression tests (no RSS network needed)."""
import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

p=Path(__file__).resolve().parents[1]/'collector.py'
sys.path.insert(0,str(p.parent))
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
  import quality
  quality.improve_entries(state,{'生成':'生成','学校':'学校','教育':'教育'},
                          {'生成':'generation','学校':'school','教育':'education'})
  feed=c.build_feed(state,self.now,[])
  self.assertGreater(feed['counts']['words'],0)
  self.assertTrue(all(x.get('zh') and x.get('en') for x in feed['items']))
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

 def test_quality_filters_fake_translations(self):
  import quality
  state={'terms':{
     'いい':{'jp':'いい','kana':'いい','zh':'你问','en':'Good',
             'verification':'机器候选待核对','daily':{'2026-10-24':8}},
     'れる':{'jp':'れる','kana':'れる','zh':'','en':'a cable',
             'verification':'机器候选待核对','daily':{'2026-10-24':8}},
     '学校':{'jp':'学校','kana':'がっこう','zh':'怪错误','en':'school!',
             'verification':'机器候选待核对','daily':{'2026-10-24':4}},
     '生成':{'jp':'生成','kana':'せいせい','zh':'','en':'',
             'verification':'未核对','daily':{'2026-10-24':5}},
  },'seenDocs':{}}
  result=quality.improve_entries(state,{'学校':'学校','生成':'生成'},
                                     {'学校':'school','生成':'generation'})
  feed=c.build_feed(state,self.now,[])
  self.assertEqual({x['jp'] for x in feed['items']},{'学校','生成'})
  self.assertEqual(state['terms']['学校']['en'],'school')
  self.assertEqual(state['terms']['いい']['zh'],'')
  self.assertEqual(state['terms']['れる']['en'],'')
  self.assertEqual(result['bilingual'],2)

 def test_strict_dictionary_parsers(self):
  import quality,gzip
  zh=quality.parse_chinese_json('{"学校":"学校","生成":"生成","れる":"语法片段","bad":"[名1]复杂的语法注释"}'.encode())
  self.assertEqual(zh['学校'],'学校')
  self.assertNotIn('bad',zh)
  sample=''.join(f'学校{i} [がっこう] /(n) school {i}/\n' for i in range(1100))
  sample+='生成 [せいせい] /(n) generation/(P)/\n'
  sample+='学校 [がっこう] /(n) school/(P)/\n'
  en=quality.parse_edict2u(gzip.compress(sample.encode('utf8')),min_entries=2)
  self.assertEqual(en['学校'],'school')
  self.assertEqual(en['生成'],'generation')

 def test_bilingual_gate_and_manual_override(self):
  import quality
  state={'terms':{'学校':{'jp':'学校','kana':'がっこう','zh':'学校','en':'school',
                        'verification':'人工已核对','daily':{'2026-10-24':2}}},'seenDocs':{}}
  quality.improve_entries(state,{},{});f=c.build_feed(state,self.now,[])
  self.assertEqual(len(f['items']),1)

if __name__=='__main__':unittest.main()
