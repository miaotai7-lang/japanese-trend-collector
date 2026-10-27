"""Evidence-gated Japanese internet slang feed integration.

Evidence must be intentionally entered from a named study/report with date and URL.
RSS candidate extraction is ONLY for a review queue, never automatically translated
or mislabeled as a confirmed trend. The existing general RSS frequency feed remains.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

QUOTE = re.compile(r'[「『“"]([^」』”"]{2,24})[」』”"]')
CONTEXT = re.compile(r'流行語|若者言葉|ネットスラング|ミーム|バズワード|Z世代|新語|スラング|高校生.*トレンド')
SKIP = {'流行語','若者言葉','ネットスラング','ミーム','話題','ニュース','人気','最新','トレンド'}


def load_reviewed(path: str | Path, today: date | None = None) -> list[dict]:
    today = today or date.today()
    doc=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if doc.get('schemaVersion') != 1 or not isinstance(doc.get('items'),list):
        raise ValueError('reviewed slang version/format invalid')
    words=set();result=[]
    for x in doc['items']:
        w=x.get('jp','').strip();rd=x.get('kana','').strip();zh=x.get('zh','').strip();en=x.get('en','').strip()
        if not w or len(w)>35 or not rd or not zh or not en:
            raise ValueError('reviewed slang must provide exact Japanese + reading + zh + en')
        if w.casefold() in words: raise ValueError('duplicate reviewed slang: '+w)
        words.add(w.casefold())
        observed=date.fromisoformat(x['date'])
        if observed > today + timedelta(days=1): raise ValueError('trend evidence is dated in the future: '+w)
        u=urlsplit(x['source'])
        if u.scheme!='https' or not u.hostname or u.username or u.password:
            raise ValueError('invalid evidence source for '+w)
        if len(x.get('note',''))>400: raise ValueError('slang note too long: '+w)
        result.append(x)
    return result


def import_reviewed(state:dict, records:list[dict], now, normalizer) -> int:
    """Merge strictly reviewed slang into same word identity without fabricated RSS counts."""
    terms=state.setdefault('terms',{})
    n=0
    for x in records:
        w=x['jp'];key=normalizer(w)
        e=terms.get(key)
        if e is None:
            n+=1
            e=terms[key]={
              'id':hashlib.sha256(key.encode('utf8')).hexdigest()[:20],
              'jp':w,'firstSeen':now.date().isoformat(),'daily':{},'docCount':0,
              'trendCount':0,'kinds':[],'categories':[],'sources':[],
            }
        e.update({'jp':w,'kana':x['kana'],'zh':x['zh'],'en':x['en'],
                  'qualityApproved':True,'trendVerified':True,
                  'evidenceDate':x['date'],'evidenceRank':int(x.get('rank') or 0),
                  'evidencePublisher':x['publisher'],'contextNote':x.get('note',''),
                  'verification':'有近期流行语调查／研究出处；中英文为核对后的学习意译',
                  'translationSources':['报道释义人工整理（非官方译文）'],
                  'lastSeen':e.get('lastSeen') or now.date().isoformat()})
        e['kinds']=list(dict.fromkeys(['trend']+[kind for kind in e.get('kinds',[]) if kind in ('freq','topic')]))
        e['categories']=list(dict.fromkeys([x['category']]+[c for c in e.get('categories',[]) if c!='热点搜索']))
        report={'title':f"{x['date']} · {x['publisher']} · 近期流行语调查／趋势研究",
                'url':x['source'],'publisher':x['publisher'],'seenAt':x['date']}
        e['sources']=[report]+[s for s in e.get('sources',[]) if s.get('url')!=x['source']][:3]
    return n


def extract_candidates(title:str) -> list[str]:
    """Very conservative headline-only candidate discovery; NEVER auto-publish."""
    if not CONTEXT.search(title):return []
    words=[]
    for match in QUOTE.findall(title):
        w=match.strip()
        if (w in SKIP or len(w)<2 or len(w)>18
            or re.search(r'https?://|[<>\\/|@#]|(?:年|月|日)\d',w)
            or not re.search(r'[\u3040-\u30ff\u3400-\u9fff]',w)):
            continue
        if w not in words:words.append(w)
    return words[:8]


def record_candidates(state:dict, article:dict, now, normalizer):
    pending=state.setdefault('slangReviewQueue',{})
    date_str=now.date().isoformat()
    for w in extract_candidates(article['title']):
        key=normalizer(w)
        e=pending.setdefault(key,{'jp':w,'firstSeen':date_str,'mentions':0,'sources':[],'status':'候选未核对（禁止自动发布）'})
        e['lastSeen']=date_str;e['mentions']+=1
        url=article['url']
        if url and not any(s.get('url')==url for s in e['sources']):
            e['sources']=[{'publisher':article['source'],'title':article['title'][:130],'url':url}]+e['sources'][:3]
    if len(pending)>600:
        kept=sorted(pending.values(),key=lambda x:(x.get('lastSeen',''),x.get('mentions',0)),reverse=True)[:500]
        state['slangReviewQueue']={normalizer(x['jp']):x for x in kept}


def feed_topics(state:dict, max_items:int=35) -> list[dict]:
    """Google Trends queries are topical interest, not inherently internet slang."""
    terms=state.get('terms',{})
    topics=[]
    for e in terms.values():
        if 'topic' not in e.get('kinds',[]):continue
        if e.get('trendVerified'):continue
        topics.append({'jp':e.get('jp',''), 'lastSeen':e.get('lastSeen',''),
                       'trendCount':e.get('trendCount',0),'sources':e.get('sources',[])[:2],
                       'label':'搜索话题，不代表流行语'})
    topics.sort(key=lambda x:(-x['trendCount'],x['jp']))
    return topics[:max_items]
