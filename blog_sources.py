"""Discovery of new slang leads from selected public Japanese knowledge creators.

Only RSS article titles/excerpts and original article URLs are read. A blog post
is useful context, NEVER an authoritative meaning or publication approval.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from community_sources import read_feed, safe_link, TRIGGERS, QUOTED, JAPANESE, GENERIC, NOISE

# Creators with identifiable Japanese-language explanations of contemporary slang.
# Candidate sources: publicly documented creator RSS, not the general note tag feed.
CREATORS = (
    ('nihon_5', 'Real Japanese Guide', 'https://note.com/nihon_5/rss'),
    ('open_fairy44', '月良アル', 'https://note.com/open_fairy44/rss'),
    ('50s_lab', '夏川 秋', 'https://note.com/50s_lab/rss'),
    ('hokeminomura', 'はるか', 'https://note.com/hokeminomura/rss'),
    ('weiden_haus_lab', '若者研究所', 'https://note.com/weiden_haus_lab/rss'),
    ('nizi_to_mangetsu', '虹と満月と株式会社', 'https://note.com/nizi_to_mangetsu/rss'),
)
LOOKBACK_DAYS = 90
MAX_RSS_BYTES = 500_000
MAX_BLOG_SIGNALS = 90
MAX_EVIDENCE = 6
TOPICAL = re.compile(r'若者言葉|ネットスラング|インターネットスラング|ネットミーム|ネット用語|流行語|流行り言葉|新語|今どきの言葉|SNS.{0,12}(?:言葉|用語)|TikTok.{0,8}トレンド|ミーム')
SKIP = {'紹介','まとめ','最新版','最新','流行','トレンド','言葉','使い方','意味',
        '知っておきたい','これ','それ','私','今日','あなた','話題','日本語'}

def _norm(word):
    return re.sub(r'[\s\u3000]','',str(word)).casefold()

def _creator_slug(raw):
    parts=urllib.parse.urlsplit(raw)
    if parts.scheme!='https' or parts.hostname!='note.com':return ''
    path=parts.path.split('/')
    return path[1] if len(path)>=4 and path[2]=='n' and path[3].startswith('n') else ''

def fetch_blogger(url):
    allowed={row[2] for row in CREATORS}
    if url not in allowed:raise ValueError('unapproved creator feed')
    req=urllib.request.Request(url,headers={'User-Agent':'JapaneseTrendCollector/1.5 (public creator RSS, twice daily)',
         'Accept':'application/rss+xml,application/atom+xml,application/xml'})
    with urllib.request.urlopen(req,timeout=9) as resp:
        new=urllib.parse.urlsplit(resp.geturl())
        if new.scheme!='https' or new.hostname!='note.com':raise ValueError('unexpected redirect')
        data=resp.read(MAX_RSS_BYTES+1)
        if len(data)>MAX_RSS_BYTES:raise ValueError('oversized creator feed')
        return data

def extract_blog_terms(article, blacklist):
    """Only explicit, short, quoted phrases in a slang-focused article.

    Never treat lists of ordinary 'recent popular topics' as language entries.
    We do not infer meaning or copy the article text.
    """
    title=article.get('title','')
    summary=article.get('summary','')
    # Topic should be about *language*, not just viral videos or popular songs.
    if not TOPICAL.search(title):return []
    text=(title+'。'+summary[:420]).strip()
    results=[];seen=set()
    for match in QUOTED.finditer(text):
        word=(match.group(1) or match.group(2)).strip()
        if not 2<=len(word)<=25 or len(word.encode('utf-8'))>110:continue
        if not JAPANESE.search(word) or NOISE.search(word):continue
        if word in blacklist or word in GENERIC or word in SKIP:continue
        if re.search(r'[、。，,：:？?!！]|^\d',word):continue
        if len(word.split())>2:continue
        # Blog post may quote ordinary conversation. Accept primarily terms in
        # the title; excerpt terms need a nearby explicit slang context.
        if match.start()>=len(title) and not TRIGGERS.search(
                text[max(len(title),match.start()-75):match.end()+65]):
            continue
        key=_norm(word)
        if key not in seen:
            seen.add(key);results.append(word)
    return results[:7]

def collect_blogs(now, previous, blacklist, known, *, fetcher=None, enabled=True):
    """Read selected creator RSS, keep bounded citation-only leads and status."""
    if fetcher is None:fetcher=fetch_blogger
    evidence={}
    for old in (previous.get('items',[]) if isinstance(previous,dict) else []):
        if not isinstance(old,dict):continue
        term=str(old.get('jp','')).strip()
        if len(term)<2 or _norm(term) in known or term in blacklist:continue
        for src in old.get('evidence',[]):
            if not isinstance(src,dict):continue
            platform=src.get('platform','')
            if platform not in {'blogger:'+c[0] for c in CREATORS}:continue
            link=safe_link(src.get('url',''))
            if not link or _creator_slug(link)!=platform.split(':',1)[-1]:continue
            try:age=(now.date()-date.fromisoformat(src.get('date',''))).days
            except (ValueError,TypeError):continue
            if 0<=age<=LOOKBACK_DAYS:
                evidence.setdefault(_norm(term),{'jp':term,'evidence':[]})['evidence'].append(
                    {'url':link,'date':src['date'],'platform':platform})
    status=[]
    for slug,creator,url in (CREATORS if enabled else ()):
        try:
            all_posts=read_feed(fetcher(url),'blogger:'+slug,now,lookback_days=LOOKBACK_DAYS)
            recent=[p for p in all_posts if 0<=(now.date()-date.fromisoformat(p['date'])).days<=LOOKBACK_DAYS]
            matches=0
            for post in recent:
                if _creator_slug(post['url'])!=slug:continue
                for term in extract_blog_terms(post,blacklist):
                    key=_norm(term)
                    if key in known:continue
                    item=evidence.setdefault(key,{'jp':term,'evidence':[]})
                    ev={'url':post['url'],'date':post['date'],'platform':'blogger:'+slug}
                    if all(existing['url']!=ev['url'] for existing in item['evidence']):
                        item['evidence'].append(ev);matches+=1
            status.append({'name':'知识博主RSS:'+slug,'status':'ok' if recent else 'empty',
                'articles':len(recent),'candidateMentions':matches})
        except Exception as exc:
            status.append({'name':'知识博主RSS:'+slug,'status':'error',
                'detail':(type(exc).__name__+': '+str(exc))[:130]})
    rows=[]
    for item in evidence.values():
        distinct={e['url']:e for e in item['evidence']}
        recent=sorted(distinct.values(),key=lambda e:(e['date'],e['url']),reverse=True)[:MAX_EVIDENCE]
        if recent:rows.append({'jp':item['jp'],'evidence':recent})
    rows.sort(key=lambda x:(max(e['date'] for e in x['evidence']),x['jp']),reverse=True)
    rows=rows[:MAX_BLOG_SIGNALS]
    return rows,{'schemaVersion':1,'items':rows},status

def combine_signals(community, bloggers):
    """Combine by normalized expression, not by RSS source or author name."""
    found={}
    for group in (community,bloggers):
        for entry in group:
            key=_norm(entry.get('jp',''))
            if not key:continue
            item=found.setdefault(key,{'jp':entry['jp'],'evidence':[]})
            links={e['url'] for e in item['evidence']}
            for e in entry.get('evidence',[]):
                if e['url'] not in links:
                    item['evidence'].append(e);links.add(e['url'])
    return list(found.values())
