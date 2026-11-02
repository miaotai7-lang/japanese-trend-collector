"""Public, unverified slang discovery lane and truthful update telemetry.

This module must never promote drafts into the verified learning feed.
A discovery record is evidence to inspect, not a definition to memorize.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

MAX_PUBLIC_CANDIDATES = 100
MAX_LINKS_PER_CANDIDATE = 4
MAX_EVIDENCE_AGE_DAYS = 120

def _safe_link(raw):
    if not isinstance(raw,str) or len(raw)>500:return ''
    try:
        p=urlsplit(raw.strip())
        host=p.hostname or ''
        if p.scheme!='https' or not host or p.username or p.password:return ''
        if p.port not in (None,443) or host=='localhost' or host.endswith(('.local','.internal')):return ''
        if re.match(r'^(?:\d+\.){3}\d+$',host):return ''
        if '.' not in host:return ''
        return p._replace(fragment='').geturl()
    except ValueError:return ''

def _fresh_date(value,now):
    if not isinstance(value,str):return False
    try:days=(now.date()-date.fromisoformat(value)).days
    except ValueError:return False
    return 0<=days<=MAX_EVIDENCE_AGE_DAYS

def _digest(items):
    """Only verified learning content matters; generatedAt and source status do not."""
    stable=sorted((str(r.get('id','')),str(r.get('jp','')),
                   str(r.get('kana','')),str(r.get('zh','')),
                   str(r.get('en',''))) for r in items if isinstance(r,dict))
    return hashlib.sha256(json.dumps(stable,ensure_ascii=False,
                                    separators=(',',':')).encode('utf-8')).hexdigest()

def snapshot(verified_feed, pending, old_feed, old_discovery, now):
    """Create independent public candidates and update-status metadata.

    An old source's publication date is not made "today" merely because the
    crawler ran today. First snapshot never claims all existing leads are new.
    """
    old_feed=old_feed if isinstance(old_feed,dict) else {}
    old_discovery=old_discovery if isinstance(old_discovery,dict) else {}
    previous_items=old_feed.get('items',[])
    previous_items=previous_items if isinstance(previous_items,list) else []
    prior_items=old_discovery.get('items',[])
    prior_items=prior_items if isinstance(prior_items,list) else []
    previous_by_id={str(x.get('id')):x for x in prior_items if isinstance(x,dict)}
    now_stamp=now.isoformat(timespec='seconds')
    unique=set()
    candidates=[]
    for r in pending:
        if not isinstance(r,dict):continue
        jp=str(r.get('jp','')).strip()
        if not 2<=len(jp)<=50 or any(ch in jp for ch in '<>\r\n'):continue
        key=re.sub(r'[\s\u3000]+','',jp).casefold()
        if key in unique:continue
        evidence=[]
        for item in r.get('evidence',[]):
            if not isinstance(item,dict):continue
            url=_safe_link(item.get('url',''))
            when=item.get('date','')
            if not url or not _fresh_date(when,now):continue
            e={'url':url,'date':when,'origin':(
                '知识博主' if str(item.get('platform','')).startswith('blogger:')
                else '公开社区' if item.get('platform') else '流行语调查')}
            if isinstance(item.get('rank'),int) and 1<=item['rank']<=50:
                e['rank']=item['rank']
            if not any(old['url']==url for old in evidence):evidence.append(e)
        if not evidence:continue
        unique.add(key)
        identifier=hashlib.sha256(key.encode('utf-8')).hexdigest()[:20]
        prior=previous_by_id.get(identifier,{})
        # Existing evidence publication date is not equivalent to first
        # discovery in this collector. Expose firstObservedAt only if known.
        first_observed=prior.get('firstObservedAt')
        if not old_discovery:
            first_observed=None
        elif not isinstance(first_observed,str):
            first_observed=now_stamp
        entries=sorted(evidence,key=lambda e:(e['date'],e['url']),reverse=True)[:MAX_LINKS_PER_CANDIDATE]
        candidate={'id':identifier,'jp':jp,
                   'kanaSuggestion':str(r.get('kanaSuggestion',''))[:75],
                   'status':'未核实候选（不可作为准确学习释义）',
                   'firstObservedAt':first_observed,
                   'latestEvidenceDate':entries[0]['date'],
                   'sourceCount':len({e['url'] for e in entries}),
                   'sources':entries}
        candidates.append(candidate)
    candidates.sort(key=lambda x:(x['latestEvidenceDate'],x['jp']),reverse=True)
    candidates=candidates[:MAX_PUBLIC_CANDIDATES]
    old_candidate_ids={x['id'] for x in prior_items if isinstance(x,dict) and isinstance(x.get('id'),str)}
    added_candidates=([x['jp'] for x in candidates if x['id'] not in old_candidate_ids]
                      if old_discovery else [])
    new_fp=_digest(verified_feed.get('items',[]))
    old_fp=(_digest(previous_items) if old_feed.get('generatedAt') else '')
    verified_changed=bool(old_fp and old_fp!=new_fp)
    previous_ids={str(x.get('id')) for x in previous_items if isinstance(x,dict)}
    added_verified=([x['jp'] for x in verified_feed.get('items',[])
                    if isinstance(x,dict) and x.get('id') not in previous_ids] if old_fp else [])
    old_change=old_feed.get('lastVerifiedChangeAt')
    # Do not invent an initial last-change timestamp when first introducing this feature.
    last_change=now_stamp if verified_changed else old_change if isinstance(old_change,str) else None
    verified_feed['lastVerifiedChangeAt']=last_change
    verified_feed['counts']['verifiedChangedThisRun']=verified_changed
    verified_feed['counts']['verifiedAddedThisRun']=len(added_verified)
    verified_feed['counts']['discoveryAddedThisRun']=len(added_candidates)
    verified_feed['counts']['discoverySnapshotInitialized']=not bool(old_discovery)
    return {'schemaVersion':1,'feedType':'japanese-slang-discovery-unverified',
        'generatedAt':now_stamp,'verifiedWordCount':len(verified_feed.get('items',[])),
        'verifiedChangedThisRun':verified_changed,
        'verifiedAddedThisRun':added_verified,
        'lastVerifiedChangeAt':last_change,
        'candidateCount':len(candidates),
        'newCandidatesThisRun':added_candidates,
        'firstSnapshot':not bool(old_discovery),
        'notice':'此页仅为自动发现的候选与出处，不保证词义或流行程度，不能直接收入正式学习词典。',
        'items':candidates}
