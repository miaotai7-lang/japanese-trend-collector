#!/usr/bin/env python3
"""Japanese public RSS word frequency/trend aggregator. Does not scrape pages.

Schedule this on a *separate* GitHub repository: its Docs feed is published via
GitHub Pages. It never mutates the personal Firebase dictionary or hosting site.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

VERSION = '1.0'
JST = timezone(timedelta(hours=9))
MAX_ITEMS = 800
MAX_FEED_BYTES = 2_000_000
SOURCE_FEEDS = [
    ('google_jp', 'Google Trends 日本', 'https://trends.google.com/trending/rss?geo=JP', '热点搜索', 'trend'),
    ('hatena_general', 'はてな・综合', 'https://b.hatena.ne.jp/hotentry.rss', '社会・生活', 'freq'),
    ('hatena_tech', 'はてな・科技', 'https://b.hatena.ne.jp/hotentry/it.rss', '科技・互联网', 'freq'),
    ('hatena_life', 'はてな・生活', 'https://b.hatena.ne.jp/hotentry/life.rss', '生活・健康', 'freq'),
    ('hatena_entertainment', 'はてな・娱乐', 'https://b.hatena.ne.jp/hotentry/entertainment.rss', '娱乐・文化', 'freq'),
    ('yahoo_business', 'Yahoo!新闻・经济', 'https://news.yahoo.co.jp/rss/topics/business.xml', '经济・商业', 'freq'),
]
STOPWORDS = set('これ それ あれ こちら こと もの ため よう とき さん そこ ここ ところ うち など そして つまり また さらに しかし でも です ます ある いる する なる ない した された する のは から まで この その 今回 本日 最近 今日 明日 昨日 全部 今後 日本 人間 人気 動画 記事 紹介 お知らせ テレビ ニュース 発表 発生 新た 世界 社会 未来 全体 一部 のち 一覧 話題 内容 開催 来月 本当 理由 問題 実際 例年 大量 大きい 小さい 多い ものすごい さまざま 多く 一つ について として よる それぞれ による きょう ほか ほぼ すべて 引き続き ともに なか 一方 あと 記録 動き 続く 今月 発売 無料 公式 確認 更新 重要 可能 必要 対応 おすすめ まとめ 知らせ どう なぜ いま 人々 以上 以下'.split())
BAD_SUFFIXES = ('する','した','です','ます')


def normalize(word: str) -> str:
    return re.sub(r'\s+', '', str(word).strip().translate(str.maketrans('ｦｧｨｩｪｫｬｭｮｯｰ', 'ヲァィゥェォャュョッー'))).casefold()


def hiragana(s: str) -> str:
    return ''.join(chr(ord(c)-96) if '\u30a1' <= c <= '\u30f6' else c for c in str(s))


def japanese_surface(word: str) -> bool:
    word = str(word).strip()
    if not 2 <= len(word) <= 30 or word in STOPWORDS:
        return False
    if re.search(r'[0-9０-９@#:/\\\[\]{}<>]', word):
        return False
    return bool(re.fullmatch(r'[\u3041-\u309f\u30a0-\u30ff\u3400-\u9fffー]+', word))


def safe_url(raw: str) -> str:
    try:
        x = urllib.parse.urlsplit(raw)
        return raw[:650] if x.scheme == 'https' and x.hostname else ''
    except ValueError:
        return ''


def get_first(node, tags):
    for tag in tags:
        e = node.find(tag)
        if e is not None and e.text:
            return e.text.strip()
    return ''


def parse_feed(source, body: bytes):
    """RSS 2.0, Atom and RDF; only title, link, date (no article scraping)."""
    root = ET.fromstring(body)
    result = []
    ns = {'a':'http://www.w3.org/2005/Atom', 'r':'http://purl.org/rss/1.0/'}
    items = (root.findall('.//item') or root.findall('.//{http://purl.org/rss/1.0/}item') or root.findall('.//{http://www.w3.org/2005/Atom}entry'))
    for node in items[:100]:
        title = html.unescape(re.sub(r'<[^>]+>', '', get_first(node, ['title','{http://www.w3.org/2005/Atom}title', '{http://purl.org/rss/1.0/}title'])))
        link = get_first(node, ['link','{http://purl.org/rss/1.0/}link'])
        if not link:
            link_el = node.find('a:link', ns)
            if link_el is not None:link = link_el.get('href','')
        if not title or len(title) > 270:continue
        link = safe_url(link)
        if not link:continue
        identity = hashlib.sha256((source[0]+'|'+link).encode('utf8')).hexdigest()[:22]
        result.append({'id': identity,'title': title,'url':link,'source':source[1],'category':source[3],'kind':source[4]})
    return result


def fetch_feed(url: str, timeout=18) -> bytes:
    req = urllib.request.Request(url, headers={
        'User-Agent':'JapaneseVocabularyStudyBot/1.0 (periodic public RSS reader; twice daily)',
        'Accept':'application/rss+xml,application/xml,text/xml,*/*',
    })
    with urllib.request.urlopen(req, timeout=timeout) as res:
        length = res.headers.get('Content-Length')
        if length and int(length) > MAX_FEED_BYTES:raise ValueError('RSS too large')
        data = res.read(MAX_FEED_BYTES+1)
        if len(data) > MAX_FEED_BYTES:raise ValueError('RSS too large')
        return data


def load_json(path, default):
    try:
        with open(path,encoding='utf8') as f:return json.load(f)
    except (FileNotFoundError,ValueError,TypeError):return default


def dump_json(path,data):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    tmp=Path(str(path)+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    tmp.replace(path)


def tokenize_title(title,tokenizer):
    seen={}
    for tok in tokenizer.tokenize(title):
        cols=tok.part_of_speech.split(',')
        if cols[0] not in ('名詞','形容詞','動詞'):continue
        if cols[0]=='名詞' and (cols[1] in ('数','非自立','代名詞','接尾') or cols[1]=='固有名詞'):continue
        if cols[0]=='動詞' and cols[1]=='非自立':continue
        surface = tok.base_form if tok.base_form!='*' else tok.surface
        if not japanese_surface(surface):continue
        if surface in STOPWORDS or surface.endswith(BAD_SUFFIXES):continue
        if normalize(surface) in seen:continue
        # janome dictionary's token reading is for inflected surface. Retokenize the base form if needed.
        reading=''
        try:
            ts=list(tokenizer.tokenize(surface))
            pieces=[t.reading for t in ts]
            if all(r != '*' for r in pieces):reading=hiragana(''.join(pieces))
        except Exception:pass
        if not reading and re.fullmatch(r'[\u3041-\u309f\u30a0-\u30ffー]+',surface):reading=hiragana(surface)
        if not reading or not re.fullmatch(r'[\u3041-\u309fー]+',reading):continue
        seen[normalize(surface)]=(surface,reading)
    return list(seen.values())


def trend_query(title,tokenizer):
    # Trending *search queries* are not necessarily lexical words: keep full
    # Japanese/ASCII topics, including proper names; show them as search topics.
    title=re.sub(r'[「」『』【】\[\]]','',title).strip()
    if len(title)<2 or len(title)>48 or title in STOPWORDS:return None
    if not re.fullmatch(r'[\u3041-\u309f\u30a0-\u30ff\u3400-\u9fffー A-Za-z0-9＋+・.&-]+',title):return None
    toks=list(tokenizer.tokenize(title))
    reading = ''.join(t.reading if t.reading!='*' else '' for t in toks)
    reading=hiragana(reading)
    if not re.fullmatch(r'[\u3041-\u309fー]+',reading):reading=''
    return title,reading


def ingest(articles, state, tokenizer, now):
    terms=state.setdefault('terms',{})
    seen_docs=state.setdefault('seenDocs',{})
    cutoff=(now-timedelta(days=45)).date().isoformat()
    seen_docs={k:v for k,v in seen_docs.items() if isinstance(v,str) and v>=cutoff}
    state['seenDocs']=seen_docs
    date=now.date().isoformat()
    unique_new=0
    for a in articles:
        if a['id'] in seen_docs:continue
        seen_docs[a['id']]=date
        unique_new += 1
        values=tokenize_title(a['title'],tokenizer)
        if a['kind']=='trend':
            q=trend_query(a['title'],tokenizer)
            if q:values=[q]+values
        # Prevent same term being counted twice within a document.
        for word,reading in {normalize(w):(w,k) for w,k in values}.values():
            key=normalize(word)
            entry=terms.get(key)
            if not entry:
                entry=terms[key]={
                    'id':hashlib.sha256(key.encode('utf8')).hexdigest()[:20],
                    'jp':word,'kana':reading,'zh':'','en':'','verification':'未核对',
                    'firstSeen':date,'lastSeen':date,'docCount':0,'trendCount':0,
                    'daily':{},'categories':[], 'kinds':[], 'sources':[],
                }
            entry['lastSeen']=date
            entry['docCount']=int(entry.get('docCount') or 0)+1
            entry['daily'][date]=entry['daily'].get(date,0)+1
            if a['category'] not in entry['categories']:entry['categories'].append(a['category'])
            if a['kind'] not in entry['kinds']:entry['kinds'].append(a['kind'])
            if a['kind']=='trend':entry['trendCount']=int(entry.get('trendCount') or 0)+1
            if not entry.get('kana'):entry['kana']=reading
            if not any(s.get('url')==a['url'] for s in entry['sources']):
                entry['sources']=[{'title':a['title'][:120],'url':a['url'],'publisher':a['source'],'seenAt':date}]+entry['sources'][:3]
    # Keep a bounded rolling archive; 45 days of daily occurrence counts.
    for key, entry in list(terms.items()):
        entry['daily']={k:v for k,v in entry.get('daily',{}).items() if k>=cutoff}
        if not entry['daily'] and entry.get('lastSeen','')<cutoff:del terms[key]
    return unique_new


def build_feed(state, now, results):
    terms=state.get('terms',{})
    words=[]
    today=now.date()
    for e in terms.values():
        daily=e.get('daily',{})
        last7=sum(int(v) for d,v in daily.items() if d >= (today-timedelta(days=6)).isoformat())
        prev7=sum(int(v) for d,v in daily.items() if (today-timedelta(days=13)).isoformat()<=d < (today-timedelta(days=6)).isoformat())
        # Activity score measured in sampled headline occurrence counts, NOT Japan-wide language frequency.
        delta=max(0,last7-prev7)
        score=last7*2+min(delta,20)*3+min(e.get('trendCount',0),20)*2
        word={k:e.get(k) for k in ['id','jp','kana','zh','en','verification','translationSources','firstSeen','lastSeen','docCount','trendCount','kinds','categories','sources']}
        word.update({'last7':last7,'previous7':prev7,'score':score})
        words.append(word)
    words.sort(key=lambda x:(-x['score'],-x['last7'],x['jp']))
    words=words[:MAX_ITEMS]
    return {
        'schemaVersion':1,'generatedAt':now.isoformat(timespec='seconds'),
        'sourceDescription':'仅统计公开RSS标题和日本Google Trends搜索词；数字为采样出现次数，不代表全日本词频',
        'counts':{'words':len(words),'seenDocuments':len(state.get('seenDocs',{})),'sourceSucceeded':sum(r['status']=='ok' for r in results)},
        'sourceStatus':results,'items':words,
    }


def translated_candidate(jp: str, lang: str) -> str:
    """Best-effort candidate; always marked machine/unverified; failure leaves field empty."""
    qs = urllib.parse.urlencode({'q':jp, 'langpair':'ja|'+lang})
    url='https://api.mymemory.translated.net/get?'+qs
    req=urllib.request.Request(url,headers={'User-Agent':'JapaneseVocabularyStudyBot/1.0'})
    with urllib.request.urlopen(req,timeout=12) as res:
        data=json.load(res)
    raw=html.unescape(str((data.get('responseData') or {}).get('translatedText') or '')).strip()
    if data.get('responseStatus')!=200 or not raw or len(raw)>180 or re.search(r'MYMEMORY|WARNING|QUOTA',raw,re.I):return ''
    if normalize(raw)==normalize(jp):return ''
    return raw


def enrich_candidates(state, now, count=8, enabled=True):
    """Only public corpus words are transmitted. Never replace existing translations."""
    if not enabled or count<1:return 0
    date=now.date().isoformat()
    existing=list(state.get('terms',{}).values())
    existing.sort(key=lambda e:(-sum(e.get('daily',{}).values()),e.get('lastTranslationAttempt','')))
    worked=0
    for entry in existing:
        if worked>=count:break
        if entry.get('zh') and entry.get('en'):continue
        try:
            previous=datetime.fromisoformat(entry.get('lastTranslationAttempt','1900-01-01')).date()
            if (now.date()-previous).days<3:continue
        except ValueError:pass
        entry['lastTranslationAttempt']=date
        worked+=1
        for lang,field in [('zh-CN','zh'),('en','en')]:
            if entry.get(field):continue
            try:
                candidate=translated_candidate(entry['jp'],lang)
                if candidate:
                    entry[field]=candidate
                    entry['verification']='机器候选待核对'
                    entry.setdefault('translationSources',[]).append('MyMemory '+lang)
            except (urllib.error.URLError,TimeoutError,ValueError,OSError) as err:
                print('INFO translation '+field+' skipped: '+str(err)[:120],file=sys.stderr)
            time.sleep(0.4)
    return worked


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--root',default='docs')
    p.add_argument('--fixture-dir',default='',help='Read fixture RSS instead of internet; only for isolated tests')
    p.add_argument('--no-translation',action='store_true',help='Disable third-party translation candidates')
    p.add_argument('--translations-per-run',type=int,default=8,help='Max public words submitted for translation each run (default 8)')
    args=p.parse_args(argv)
    now=datetime.now(JST)
    root=Path(args.root)
    state=load_json(root/'state.json', {'terms':{},'seenDocs':{}})
    # Import lazily so CI tests can use a tokenizer stub without Janome.
    try:
        from janome.tokenizer import Tokenizer
    except ImportError:
        print('Please install requirements.txt (janome)',file=sys.stderr)
        return 2
    tokenizer=Tokenizer()
    sources=[];articles=[]
    for source in SOURCE_FEEDS:
        try:
            if args.fixture_dir:
                data=(Path(args.fixture_dir)/(source[0]+'.xml')).read_bytes()
            else:
                data=fetch_feed(source[2])
            parsed=parse_feed(source,data)
            if not parsed:raise ValueError('empty or incompatible RSS feed')
            articles.extend(parsed)
            sources.append({'name':source[1],'status':'ok','articles':len(parsed)})
        except Exception as err:
            sources.append({'name':source[1],'status':'error','detail':str(err)[:150]})
            print(f'WARN {source[1]}: {err}',file=sys.stderr)
    if not articles:
        print('ERROR: All public RSS feeds unavailable; preserving previous published feed.',file=sys.stderr)
        return 1
    processed=ingest(articles,state,tokenizer,now)
    enrich_candidates(state,now,min(12,max(0,args.translations_per_run)),not args.no_translation)
    generated=build_feed(state,now,sources)
    dump_json(root/'state.json',state)
    dump_json(root/'feed.json',generated)
    print(f'Parsed {len(articles)} RSS entries; {processed} new documents; published {len(generated["items"])} sampled words.')
    return 0

if __name__=='__main__':sys.exit(main())
