"""Publish only sourced, manually defined contemporary Japanese internet slang.

Do not confuse a daily trending *search* with a novel idiom.  No arbitrary
Janome tokens, RSS article frequency or machine-generated definitions can enter
the public feed. Unknown terms from targeted survey reports are queued for
review; no automatic inventions of bilingual meanings.
"""
from __future__ import annotations
import hashlib
import html
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

JST = timezone(timedelta(hours=9))
CURRENT_DAYS = 120
REVIEWED_AUTO_PATH = Path(__file__).resolve().parent / 'data' / 'reviewed_auto_publish.json'
VERIFIED_ONE_CHARACTER_SLANG = {'滅'}
SOURCE_FEED = 'https://shibuya-trendresearch.jp/monthlytrendsurvey/feed/'
SURVEY_INDEX = 'https://shibuya-trendresearch.jp/monthlytrendsurvey/'
CURRENT_REPORT = 'https://shibuya-trendresearch.jp/monthlytrendsurvey/4622/'
BLACKLIST = {'情報','会社','見る','食べる','アクセス','記事','ニュース','日本','東京','今日','動画','人気','商品','アプリ','学校','2026','仕事',
             'いい','れる','する','ある','発表','公開','価格','最新','サービス','問題','社会','企業','発売'}


def norm(s):
    return re.sub(r'[\s\u3000]', '', str(s)).casefold()


def trusted_url(raw):
    try:
        p=urllib.parse.urlsplit(str(raw))
        return str(raw) if p.scheme=='https' and p.hostname in {'shibuya-trendresearch.jp','www.watch.impress.co.jp','fomo-fomo.com','media.asahiconnect-o.com','prtimes.jp','news.mynavi.jp'} else ''
    except ValueError:
        return ''


class PlainText(HTMLParser):
    BLOCKS={'p','div','br','h1','h2','h3','h4','li','tr','td','section','article'}
    def __init__(self):
        super().__init__(convert_charrefs=True);self.chunks=[];self.ignore=0
    def handle_starttag(self,tag,attrs):
        if tag in {'style','script'}: self.ignore+=1
        if tag in self.BLOCKS:self.chunks.append('\n')
    def handle_endtag(self,tag):
        if tag in {'style','script'} and self.ignore:self.ignore-=1
        if tag in self.BLOCKS:self.chunks.append('\n')
    def handle_data(self,data):
        if not self.ignore:self.chunks.append(data)
    def text(self):
        return html.unescape(''.join(self.chunks))


def ranked_slang_from_report(page_html):
    """Find ranked slang in the report BODY, not in its table of contents.

    Reports repeat the exact '今流行っている言葉は？' heading in the
    navigation/TOC and again in the article. Only a block with actual
    ranking rows is accepted. The next category heading is the boundary.
    """
    parser=PlainText();parser.feed(page_html)
    text=parser.text()
    heads=list(re.finditer(r'今[^\S\n]*流行っている[^\S\n]*言葉[^\S\n]*は[^\S\n]*[？?]?', text))
    pattern=re.compile(r'(?:^|\s)(\d{1,2})\s*位\s*([^()（）\n]{1,45}?)\s*[（(]\s*\d+(?:[.．]\d+)?\s*[%％]\s*[)）]')
    for head in heads:
        section=text[head.end():]
        end=re.search(
            r'今\s*流行っている\s*(?:物事|食べ物|音楽|場所|芸能|アイドル)'
            r'|次に来る|ネクストトレンド|※複数回答', section)
        if end:section=section[:end.start()]
        out=[];seen=set()
        for line in section.splitlines():
            line=re.sub(r'[\s\u3000]+',' ',line).strip()
            m=pattern.search(line)
            if not m:continue
            term=m.group(2).strip(' 「」『』\u3000')
            if not (1<=len(term)<=32) or (len(term)==1 and term not in VERIFIED_ONE_CHARACTER_SLANG) or term in BLACKLIST or norm(term) in seen:continue
            seen.add(norm(term));out.append({'jp':term,'rank':int(m.group(1))})
        if out:
            return out[:25]
    return []


def report_published_date(page_html):
    """Only use publisher-declared dates. Never substitute current run date."""
    m=re.search(r'<meta\s+[^>]*(?:property|name)=["\'](?:article:published_time|datePublished|pubdate)["\'][^>]*content=["\'](20\d{2}-\d\d-\d\d)',page_html,re.I)
    if m:return m.group(1)
    p=PlainText();p.feed(page_html)
    text=p.text()
    candidates=re.findall(r'(20\d{2})[.\-/年](\d{1,2})[.\-/月](\d{1,2})',text[:7000])
    for y,m,d in candidates:
        try:return date(int(y),int(m),int(d)).isoformat()
        except ValueError:continue
    return None


def read_survey_rss(xml_bytes):
    """Discover official trend survey pages only; never ordinary news RSS."""
    root=ET.fromstring(xml_bytes)
    entries=root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
    urls=[]
    for e in entries[:35]:
        title=(e.findtext('title') or e.findtext('{http://www.w3.org/2005/Atom}title') or '').strip()
        if not any(t in title for t in ('トレンド','特大号','流行語','流行りの言葉','若者言葉')):continue
        url=(e.findtext('link') or '').strip()
        if url and trusted_url(url) and '/monthlytrendsurvey/' in url and url not in urls:urls.append(url)
    return urls[:8]


class SurveyLinks(HTMLParser):
    """Read links from an official survey archive, never unrelated search results."""
    def __init__(self):
        super().__init__(convert_charrefs=True);self.current=None;self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            href=dict(attrs).get('href','')
            self.current=[urllib.parse.urljoin(SURVEY_INDEX,href),[]]
    def handle_data(self,data):
        if self.current is not None:self.current[1].append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.current is not None:
            url,title=self.current[0],''.join(self.current[1])
            if trusted_url(url) and re.fullmatch(r'/monthlytrendsurvey/\d+/',urllib.parse.urlsplit(url).path) and any(x in title for x in ('特大号','流行語','言葉','トレンド')):
                if url not in self.links:self.links.append(url)
            self.current=None


def read_survey_index(page_html):
    reader=SurveyLinks();reader.feed(page_html)
    return reader.links[:10]

def fetch_public(url, maxbytes=1_800_000, timeout=12):
    if not trusted_url(url):raise ValueError('Untrusted public source')
    req=urllib.request.Request(url,headers={'User-Agent':'JapanSlangStudyBot/1.2 (public-trend-report-reader; twice-daily)', 'Accept':'text/html,application/rss+xml,application/xml'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        d=r.read(maxbytes+1)
        if len(d)>maxbytes:raise ValueError('source too large')
        return d


def load_catalog(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    seen=set();valid=[]
    for e in data['terms']:
        key=norm(e['jp']);url=trusted_url(e['source'])
        if not url or not key or key in seen or e['jp'] in BLACKLIST:raise ValueError('Invalid/duplicate/ordinary word in catalog: '+str(e['jp']))
        if not all(str(e.get(k,'')).strip() for k in ['jp','kana','zh','en','category','referenceDate']):raise ValueError('Missing required bilingual field')
        date.fromisoformat(e['referenceDate']);seen.add(key);valid.append(e)
    return valid


def reviewed_auto_terms(catalog, state, now, path=REVIEWED_AUTO_PATH):
    """Permit only editor-checked meanings that match a live, dated ranking.

    The independent glossary is a pre-reviewed language source, NOT an
    automated translation approval. Missing, stale or mismatching survey
    evidence fails closed and publishes nothing new.
    """
    if not Path(path).exists():
        return []
    approved=load_catalog(path)
    known={norm(t['jp']) for t in catalog}
    records=[]
    for item in approved:
        key=norm(item['jp'])
        if key in known:
            continue
        if item.get('reviewStatus')!='editor-reviewed':
            continue
        if not item.get('meaningReferences') or len(item['meaningReferences'])<2:
            continue
        if any(not str(url).startswith('https://') for url in item['meaningReferences']):
            continue
        try:
            original=date.fromisoformat(item['referenceDate'])
        except (ValueError,TypeError):
            continue
        if not (0 <= (now.date()-original).days <= CURRENT_DAYS):
            continue
        for report in state.get('reports',[]):
            if report.get('url')!=item['source'] or not trusted_url(report.get('url','')):
                continue
            try:
                published=date.fromisoformat(report.get('date',''))
            except (ValueError,TypeError):
                continue
            if published!=original or not (0 <= (now.date()-published).days <= CURRENT_DAYS):
                continue
            if not any(norm(row.get('jp',''))==key for row in report.get('ranked',[]) if isinstance(row,dict)):
                continue
            records.append(dict(item,autoPublished=True))
            known.add(key)
            break
    return records


def existing_rank(state, item):
    return next((x for x in state.get('reports',[]) if x.get('url')==item['source'] and any(y.get('jp')==item['jp'] for y in x.get('ranked',[]))),None)


def report_evidence(catalog,state,now):
    new_pending={}
    byname={norm(x['jp']):x for x in catalog}
    for report in state.get('reports',[]):
        if not isinstance(report,dict) or not trusted_url(report.get('url','')):continue
        try:when=date.fromisoformat(report.get('date',''))
        except ValueError:continue
        if (now.date()-when).days> CURRENT_DAYS:continue
        for term in report.get('ranked',[]):
            text=str(term.get('jp','')).strip();key=norm(text)
            if text in BLACKLIST or not 2<=len(text)<=35:continue
            if key in byname:continue
            rec=new_pending.setdefault(key,{'jp':text,'sources':[],'evidence':[],
                'status':'needs_human_definition_and_bilingual_review'})
            if report['url'] not in rec['sources']:rec['sources'].append(report['url'])
            if not any(e['url']==report['url'] for e in rec['evidence']):
                rec['evidence'].append({'url':report['url'],'date':report['date'],
                    'rank':term.get('rank')})
    return sorted(new_pending.values(),key=lambda x:x['jp'])


def build_slang_feed(catalog,state,now,source_status):
    rows=[]
    for e in catalog:
        when=date.fromisoformat(e['referenceDate'])
        reports=[]
        for report in state.get('reports',[]):
            for x in report.get('ranked',[]):
                if norm(x.get('jp',''))==norm(e['jp']):
                    try:rdate=date.fromisoformat(report.get('date',''))
                    except ValueError:continue
                    if rdate>when:when=rdate
                    reports.append({'title':'近期网络流行语调查排名', 'url':report['url'],'publisher':report.get('publisher','渋谷トレンドリサーチ'),'seenAt':report['date']})
        age=(now.date()-when).days
        if age<0 or age> CURRENT_DAYS:continue
        url=e['source']
        sources=[{'title':f'近期流行语报道／释义参考（{e["referenceDate"]}）','url':url,'publisher':e['publisher'],'seenAt':e['referenceDate']}]
        for r in reports:
            if all(x['url']!=r['url'] for x in sources):sources.append(r)
        score=max(0,121-max(0,age))*2+max(0,15-int(e.get('rank',99)))*4
        # Keep compatibility with existing Firebase front-end fields. In strict
        # slang mode score is recency + cited survey rank; NOT headline frequency.
        rows.append({'id':hashlib.sha256(norm(e['jp']).encode('utf8')).hexdigest()[:20],
            'jp':e['jp'],'kana':e['kana'],'zh':e['zh'],'en':e['en'],
            'verification':'事先独立核对日中英释义，自动匹配近期调查后发布' if e.get('autoPublished') else '来源有据；日中英学习释义待人工复核',
            'firstSeen':e['referenceDate'],'lastSeen':when.isoformat(),
            'kinds':['trend'],'categories':[e['category']],
            'sources':sources[:4],'last7':0,'previous7':0,'docCount':len(sources),'trendCount':len(reports),
            'score':score,'surveyRank':int(e['rank']) if e.get('rank') is not None else None})
    rows.sort(key=lambda x:(-x['score'],x['jp']))
    return {'schemaVersion':1,'feedType':'japanese-internet-slang-only','generatedAt':now.isoformat(timespec='seconds'),
        'sourceDescription':'仅展示有近期流行语调查或专题出处、并人工编写日中英释义的网络用语；不收录新闻高频词或搜索热点。新增候选暂不自动发布，须核对释义。',
        'counts':{'words':len(rows),'candidateWords':len(report_evidence(catalog,state,now)),'pendingReview':len(report_evidence(catalog,state,now)),
                  'sourceSucceeded':sum(s.get('status')=='ok' for s in source_status)},
        'sourceStatus':source_status,'items':rows}


def run(root, catalog_path, fixture=None, no_network=False, now=None,
        translate_pending=False, translator=None, translation_limit=8,
        community_enabled=True,blog_enabled=True):
    now=now or datetime.now(JST);root=Path(root)
    catalog=load_catalog(catalog_path)
    state_path=root/'slang_state.json';prior={}
    if state_path.exists():
        try:prior=json.loads(state_path.read_text(encoding='utf8'))
        except (ValueError,TypeError):prior={}
    state={'reports':prior.get('reports',[])}
    status=[]
    if fixture is not None:
        pages=[(CURRENT_REPORT,fixture)]
        status.append({'name':'权威流行语调查','status':'ok','articles':1})
    elif not no_network:
        pages=[];urls=[CURRENT_REPORT]
        # RSS and the official archive are independent discovery paths.
        # An unavailable RSS must not silently freeze the collector at one URL.
        try:
            archive_urls=read_survey_index(fetch_public(SURVEY_INDEX).decode('utf-8',errors='replace'))
            urls.extend(u for u in archive_urls if u not in urls)
        except Exception as e:
            status.append({'name':'流行语调查档案索引','status':'error','detail':str(e)[:120]})
        try:
            rss_urls=read_survey_rss(fetch_public(SOURCE_FEED))
            urls.extend(u for u in rss_urls if u not in urls)
        except Exception as e:
            status.append({'name':'流行语调查 RSS','status':'error','detail':str(e)[:120]})
        for url in urls[:10]:
            try:
                page=fetch_public(url).decode('utf-8',errors='replace')
                pages.append((url,page))
            except Exception as e:
                status.append({'name':'流行语调查网页','status':'error','detail':url+' '+str(e)[:90]})
        status.append({'name':'流行语调查页面读取','status':'fetched' if pages else 'error','articles':len(pages)})

    else:
        pages=[];status.append({'name':'离线质量检查','status':'skipped'})
    parsed_reports=0
    parsed_words=0
    for url,page in pages:
        ranked=ranked_slang_from_report(page)
        if not ranked:
            status.append({'name':'调查排名解析','status':'no_matches','detail':url[:115]})
            continue
        published=report_published_date(page)
        if not published and url==CURRENT_REPORT: published='2026-10-02'  # verified publisher record
        if not published:
            status.append({'name':'缺少来源发布日期','status':'skipped','detail':url[:110]})
            continue
        if date.fromisoformat(published)>now.date():continue
        parsed_reports+=1;parsed_words+=len(ranked)
        if url not in [v.get('url') for v in state['reports']]:
            state['reports'].append({'url':url,'ranked':ranked,'date':published,'publisher':'渋谷トレンドリサーチ'})
        else:
            for row in state['reports']:
                if row.get('url')==url:row['ranked']=ranked;row['date']=published
    if pages:
        status.append({'name':'有效流行语调查解析','status':'ok' if parsed_reports else 'error',
            'articles':parsed_reports,'rankedWords':parsed_words,
            'detail':'' if parsed_reports else '网页可读取，但未能解析出带名次和百分比的流行语表格'})

    state['reports']=state['reports'][-35:]
    eligible_auto=reviewed_auto_terms(catalog,state,now)
    effective_catalog=catalog+eligible_auto
    pending=report_evidence(effective_catalog,state,now)
    survey_succeeded=sum(s.get('status')=='ok' for s in status)

    # Community RSS is independent evidence for REVIEW ONLY. Never synthesize
    # survey rankings or append community candidates to effective_catalog.
    from community_sources import collect_community, merge_pending
    community_path=root/'community_state.json'
    old_community={}
    if community_path.exists():
        try:old_community=json.loads(community_path.read_text(encoding='utf8'))
        except (OSError,ValueError,TypeError):old_community={}
    community,community_state,community_status=collect_community(
        now,old_community,BLACKLIST,{norm(x['jp']) for x in effective_catalog},
        enabled=community_enabled and not no_network and fixture is None)
    # A curated creator RSS is a secondary language-context signal; it is
    # never a survey rank, nor a proof that a machine translation is right.
    from blog_sources import collect_blogs,combine_signals
    blogger_path=root/'blog_state.json'
    prior_blogs={}
    if blogger_path.exists():
        try:prior_blogs=json.loads(blogger_path.read_text(encoding='utf8'))
        except (OSError,ValueError,TypeError):prior_blogs={}
    bloggers,blogger_state,blogger_status=collect_blogs(
        now,prior_blogs,BLACKLIST,{norm(x['jp']) for x in effective_catalog},
        enabled=blog_enabled and not no_network and fixture is None)
    combined_signals=combine_signals(community,bloggers)
    pending=merge_pending(pending,combined_signals,
        {norm(x['jp']) for x in effective_catalog},norm)
    status.extend(community_status)
    status.extend(blogger_status)
    # Translation drafts belong ONLY to the pending-review file; the
    # public feed is always constructed from the manually curated catalog.
    from translation_review import enrich_review_queue
    prior_pending=[]
    review_path=root/'slang_pending.json'
    if review_path.exists():
        try:
            old=json.loads(review_path.read_text(encoding='utf8'))
            if isinstance(old.get('items'),list):prior_pending=old['items']
        except (ValueError, TypeError, OSError):
            pass
    pending=enrich_review_queue(pending,prior_pending,now,BLACKLIST,
        enable_translation=bool(translate_pending and not no_network),
        translator=translator,max_items=translation_limit)
    feed=build_slang_feed(effective_catalog,state,now,status)
    # The public list remains editor-curated; pending counts describe both
    # survey and community discovery without altering existing feed items.
    feed['counts']['sourceSucceeded']=survey_succeeded  # Historical survey-only meaning
    feed['counts']['candidateWords']=len(pending)
    feed['counts']['pendingReview']=len(pending)
    feed['counts']['communityCandidateWords']=sum(bool(x.get('communityEvidenceCount')) for x in pending)
    feed['counts']['communitySignals']=len(community)  # raw leads, not approved words
    feed['counts']['bloggerSignals']=len(bloggers)
    active={norm(p['jp']) for p in pending}
    feed['counts']['bloggerCandidateWords']=sum(norm(x['jp']) in active for x in bloggers)
    feed['counts']['bloggerHeldForCorroboration']=sum(norm(x['jp']) not in active for x in bloggers)
    feed['counts']['bloggerSourceSucceeded']=sum(s.get('status')=='ok' for s in blogger_status)
    feed['counts']['bloggerSourceReadable']=sum(s.get('status') in ('ok','empty') for s in blogger_status)
    feed['counts']['communityHeldForCorroboration']=sum(
        norm(x['jp']) not in {norm(p['jp']) for p in pending} for x in community)
    feed['counts']['communitySourceSucceeded']=sum(s.get('status')=='ok' for s in community_status)
    feed['counts']['communitySourceReadable']=sum(s.get('status') in ('ok','empty') for s in community_status)
    feed['counts']['autoPublishedReviewed']=len(eligible_auto)
    feed['counts']['reviewedCatalog']=len(catalog)
    feed['sourceDescription'] += ' 自动加入新条目仅限事先审校释义且再次匹配近期正式调查的词；机器翻译仍只存待审核队列。'
    # Never read or transfer old generic docs/state.json; replacing docs/feed.json
    # drops old meaningless news-frequency entries by design.
    root.mkdir(exist_ok=True,parents=True)
    (root/'slang_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    community_path.write_text(json.dumps(community_state,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    blogger_path.write_text(json.dumps(blogger_state,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (root/'slang_pending.json').write_text(json.dumps({'generatedAt':now.isoformat(timespec='seconds'),'items':pending},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (root/'feed.json').write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return feed
