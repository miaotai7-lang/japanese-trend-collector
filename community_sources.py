"""Bounded discovery of explicitly named slang from public community feeds.

Hatena Bookmark tag-search RSS and Mastodon public hashtag RSS are *signals*,
not dictionaries or independent confirmations of word meaning. Nothing here
may bypass the editor-reviewed publication gate in slang_only.py.
"""
from __future__ import annotations

import html
import ipaddress
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

MAX_BYTES = 450_000
MAX_ITEMS = 35
LOOKBACK_DAYS = 35
MAX_STATE_WORDS = 100
MAX_EVIDENCE_PER_WORD = 6
JST = timezone(timedelta(hours=9))
SOURCES = (
    ('hatena_slang', 'https://b.hatena.ne.jp/search/tag?q=%E3%83%8D%E3%83%83%E3%83%88%E3%82%B9%E3%83%A9%E3%83%B3%E3%82%B0&mode=rss'),
    ('hatena_title_slang', 'https://b.hatena.ne.jp/search/title?q=%E3%83%8D%E3%83%83%E3%83%88%E3%82%B9%E3%83%A9%E3%83%B3%E3%82%B0&mode=rss'),
    ('hatena_title_trends', 'https://b.hatena.ne.jp/search/title?q=%E6%B5%81%E8%A1%8C%E8%AA%9E&mode=rss'),
    ('mastodon_slang', 'https://mastodon.social/tags/%E3%83%8D%E3%83%83%E3%83%88%E3%82%B9%E3%83%A9%E3%83%B3%E3%82%B0.rss'),
    ('mastodon_trends', 'https://mastodon.social/tags/%E6%B5%81%E8%A1%8C%E8%AA%9E.rss'),
    ('mastodon_nihongo', 'https://mastodon.social/tags/%E6%97%A5%E6%9C%AC%E8%AA%9E.rss'),
)
TRIGGERS = re.compile(r'流行語|若者言葉|ネットスラング|ネットミーム|ネット用語|バズワード|新語|流行りの言葉|ミーム')
QUOTED = re.compile(r'「([^「」]{2,28})」|『([^『』]{2,28})』')
JAPANESE = re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')
NOISE = re.compile(r'https?://|@|#|[<>]|\n|\r')
GENERIC = {'SNS','X','AI','学校','情報','会社','ニュース','流行語','ネットスラング','ネットミーム',
           '若者言葉','商品','日本','東京','人気','動画','アプリ','コメント','サービス','ゲーム'}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.parts=[];self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'):self.skip+=1
    def handle_endtag(self, tag):
        if tag in ('script','style') and self.skip:self.skip-=1
    def handle_data(self, value):
        if not self.skip:self.parts.append(value)
    def text(self):return html.unescape(' '.join(self.parts))


def clean_text(value):
    parser=_Text();parser.feed(str(value)[:4000])
    return re.sub(r'\s+',' ',parser.text()).strip()[:550]


def safe_link(url):
    """Only store public HTTPS citation links; never fetch links inside posts."""
    try:
        p=urllib.parse.urlsplit(str(url).strip())
        host=(p.hostname or '').lower().rstrip('.')
        if p.scheme!='https' or not host or p.username or p.password or len(str(url))>500:
            return ''
        if p.port not in (None,443):return ''
        if host=='localhost' or host.endswith(('.local','.internal','.localhost')):return ''
        try:ipaddress.ip_address(host);return ''
        except ValueError:pass
        if '.' not in host:return ''
        return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,p.query,''))
    except ValueError:return ''


def fetch_feed(url):
    if url not in dict((u,n) for n,u in SOURCES):raise ValueError('unapproved feed')
    req=urllib.request.Request(url,headers={'User-Agent':'JapaneseTrendCollector/1.4 (public-RSS-research; twice daily)',
        'Accept':'application/rss+xml,application/atom+xml,application/xml'})
    with urllib.request.urlopen(req,timeout=9) as response:
        redirected=urllib.parse.urlsplit(response.geturl())
        if redirected.scheme!='https' or redirected.hostname not in ('b.hatena.ne.jp','mastodon.social'):
            raise ValueError('unapproved or insecure redirect')
        raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('feed too large')
        return raw


def _published(raw):
    if not raw:return None
    raw=str(raw).strip()
    try:
        d=datetime.fromisoformat(raw.replace('Z','+00:00'))
        if d.tzinfo is None:d=d.replace(tzinfo=JST)
        return d.astimezone(JST).date()
    except ValueError:
        try:
            d=parsedate_to_datetime(raw)
            if d.tzinfo is None:d=d.replace(tzinfo=JST)
            return d.astimezone(JST).date()
        except (ValueError,TypeError,IndexError):return None


def _child_text(node, local):
    for child in node:
        if child.tag.rsplit('}',1)[-1]==local:return ''.join(child.itertext()).strip()
    return ''


def read_feed(raw, source, now):
    """Parse RSS1/RSS2/Atom; keep only title, short contextual snippet, URL, date."""
    root=ET.fromstring(raw)
    nodes=[n for n in root.iter() if n.tag.rsplit('}',1)[-1] in ('item','entry')]
    results=[]
    for item in nodes[:MAX_ITEMS]:
        published=(_published(_child_text(item,'pubDate')) or _published(_child_text(item,'published'))
                   or _published(_child_text(item,'updated')) or _published(_child_text(item,'date')))
        if published is None or not (0 <= (now.date()-published).days <= LOOKBACK_DAYS):continue
        link=_child_text(item,'link')
        if not link:
            for sub in item:
                if sub.tag.rsplit('}',1)[-1]=='link' and sub.attrib.get('href'):
                    link=sub.attrib['href'];break
        link=safe_link(link)
        if not link:continue
        title=clean_text(_child_text(item,'title'))
        summary=clean_text(_child_text(item,'description') or _child_text(item,'summary') or _child_text(item,'content'))
        if not title and not summary:continue
        results.append({'title':title[:160], 'summary':summary[:450], 'url':link,
                        'date':published.isoformat(), 'platform':source})
    return results


def extract_claimed_slang(post, blacklist):
    """Take only explicitly described slang in quote marks, not arbitrary tokens."""
    # Community aggregators often quote unrelated snippets in descriptions.
    # For Hatena, examine the explicit article title only; for Mastodon, the
    # public RSS post body is supplied in its description without a title.
    title=post.get('title','').strip()
    text=(title if post.get('platform','').startswith('hatena_') and title
          else title+'。'+post.get('summary','')).strip()
    if not TRIGGERS.search(text):return []
    seen=set();names=[]
    for match in QUOTED.finditer(text):
        phrase=(match.group(1) or match.group(2)).strip()
        neighborhood=text[max(0,match.start()-75):match.end()+75]
        # The trigger must describe this expression locally, not the whole article.
        if not TRIGGERS.search(neighborhood):continue
        if not 2<=len(phrase)<=25 or len(phrase.encode('utf-8'))>100:continue
        if phrase in GENERIC or phrase in blacklist or not JAPANESE.search(phrase):continue
        if NOISE.search(phrase) or re.search(r'^\d|[。！?？、,，:：]',phrase):continue
        if len(phrase.split())>3:continue
        key=re.sub(r'\s+','',phrase).casefold()
        if key not in seen:
            seen.add(key);names.append(phrase)
    return names[:5]


def collect_community(now, prior, blacklist, known, fetcher=None, enabled=True):
    """Return candidate evidence, safely bounded state, per-source telemetry.

    The state contains no raw post bodies, display names, or personal IDs.
    """
    if fetcher is None:fetcher=fetch_feed
    today=now.date()
    norm=lambda s:re.sub(r'\s+','',s).casefold()
    states={}
    if isinstance(prior,dict):
        for old in prior.get('items',[]):
            if not isinstance(old,dict):continue
            name=str(old.get('jp',''))
            if not 2<=len(name)<=25 or name in blacklist or norm(name) in known:continue
            evidence=[]
            for e in old.get('evidence',[]):
                if not isinstance(e,dict) or not safe_link(e.get('url','')):continue
                try:
                    age=(today-date.fromisoformat(e['date'])).days
                except (KeyError,TypeError,ValueError):continue
                if 0<=age<=LOOKBACK_DAYS and e.get('platform') in dict(SOURCES):
                    evidence.append({'url':e['url'],'date':e['date'],'platform':e['platform']})
            if evidence:states[name]=evidence[:MAX_EVIDENCE_PER_WORD]
    telemetry=[]
    for source,url in (SOURCES if enabled else ()):
        try:
            posts=read_feed(fetcher(url),source,now)
            matches=0
            for post in posts:
                for word in extract_claimed_slang(post,blacklist):
                    if norm(word) in known:continue
                    ev={'url':post['url'],'date':post['date'],'platform':source}
                    bucket=states.setdefault(word,[])
                    if not any(x['url']==ev['url'] for x in bucket):
                        if len(bucket)<MAX_EVIDENCE_PER_WORD:bucket.append(ev)
                        matches+=1
            telemetry.append({'name':'社区RSS:'+source,'status':'ok' if posts else 'empty',
                              'articles':len(posts), 'candidateMentions':matches})
        except Exception as exc:
            telemetry.append({'name':'社区RSS:'+source,'status':'error',
                              'detail':(type(exc).__name__+': '+str(exc))[:140]})
    # Stable sorting by last source date, cap memory even on hostile feeds.
    rows=[]
    for word,evs in states.items():
        evs=sorted(evs,key=lambda x:(x['date'],x['url']),reverse=True)[:MAX_EVIDENCE_PER_WORD]
        if evs:rows.append({'jp':word,'evidence':evs})
    rows.sort(key=lambda r:(max(e['date'] for e in r['evidence']),r['jp']),reverse=True)
    rows=rows[:MAX_STATE_WORDS]
    return rows,{'schemaVersion':1,'items':rows},telemetry


def merge_pending(survey, community, known, norm):
    """Community evidence never gets a survey rank or publication approval."""
    byname={norm(x['jp']):dict(x) for x in survey}
    for row in community:
        key=norm(row['jp'])
        if key in known:continue
        # A single public post is an unverified lead. Keep it in the bounded
        # community state for later comparison but do not promote it into the
        # active translation/review queue unless independently repeated or
        # already supported by an actual official survey.
        independent_links={e.get('url') for e in row.get('evidence',[]) if isinstance(e,dict)}
        if key not in byname and len(independent_links)<2:continue
        rec=byname.setdefault(key,{'jp':row['jp'],'sources':[],'evidence':[],
             'status':'community_signal_needs_independent_meaning_review'})
        for ev in row['evidence']:
            if ev['url'] not in rec['sources']:rec['sources'].append(ev['url'])
            if not any(x.get('url')==ev['url'] for x in rec['evidence']):
                rec['evidence'].append({'url':ev['url'],'date':ev['date'],
                    'platform':ev['platform'],'rank':None})
        rec['communitySources']=sorted(set(e['platform'] for e in row['evidence']))
        rec['communityEvidenceCount']=len(row['evidence'])
    return sorted(byname.values(),key=lambda x:x['jp'])
