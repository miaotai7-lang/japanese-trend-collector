"""Conservative Japanese slang candidate translation drafts and evidence checks.

Machine translations NEVER become published entries here. Only explicitly
reviewed entries in slang_terms.json can enter the public feed.
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime

MYMEMORY_ENDPOINT = 'https://api.mymemory.translated.net/get'
DRAFT_TTL_DAYS = 14
MAX_DRAFTS_PER_RUN = 8
MAX_TERM_BYTES = 180
MAX_TRANSLATION_LENGTH = 280
_JP_SCRIPT = re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')
_ZH_SCRIPT = re.compile(r'[\u3400-\u9fff]')
_BAD_TEXT = re.compile(r'(?:MYMEMORY\s*(?:WARNING|ERROR)|PLEASE\s+TRY\s+AGAIN|QUERY\s+LENGTH\s+LIMIT|RATE\s+LIMIT|(?:https?://)|<[^>]+>)', re.I)


def suggested_kana(jp: str) -> str:
    """Only convert unambiguous kana. Never invent readings for kanji."""
    original = unicodedata.normalize('NFKC', jp).strip()
    if not original or not all('\u3040' <= ch <= '\u309f' or '\u30a1' <= ch <= '\u30f6' or ch in 'ー・！!？?〜～〇○ ' for ch in original):
        return ''
    return ''.join(chr(ord(ch)-96) if '\u30a1' <= ch <= '\u30f6' else ch for ch in original)


def assess_candidate(jp: str, evidence: list, now: datetime, blacklist: set) -> dict:
    """Score source evidence for review order, NOT translation accuracy."""
    problems = []
    name = jp.strip()
    if len(name) < 2 or len(name) > 35 or len(name.encode('utf8')) > MAX_TERM_BYTES:
        problems.append('词形长度异常')
    if name in blacklist:
        problems.append('命中普通词黑名单')
    if not _JP_SCRIPT.search(name):
        problems.append('缺少日语文字')
    if '\n' in name or '\r' in name or '<' in name or '>' in name or '://' in name:
        problems.append('包含不允许的格式或链接')
    dates = []
    ranks = []
    sources = set()
    for item in evidence:
        if not isinstance(item, dict):
            continue
        try:
            day = date.fromisoformat(item.get('date', ''))
            if 0 <= (now.date()-day).days <= 120:
                dates.append(day)
        except (ValueError, TypeError):
            pass
        try:
            rank = int(item.get('rank'))
            if 1 <= rank <= 30:
                ranks.append(rank)
        except (ValueError, TypeError):
            pass
        url = item.get('url')
        if isinstance(url, str) and url.startswith('https://'):
            sources.add(url)
    if not dates or not sources:
        problems.append('缺少有效的近期来源')
    if problems:
        priority = 0
    else:
        age = (now.date()-max(dates)).days
        priority = min(100, 35 + (25 if age<=30 else 12 if age<=90 else 0)
                       + (20 if ranks and min(ranks)<=10 else 8 if ranks else 0)
                       + (20 if len(sources)>=2 else 0))
    return {'status':'reject_candidate' if problems else 'needs_human_review',
            'reviewPriority':priority,
            'priorityMeaning':'仅用于安排审核次序，不是词义或翻译准确率',
            'reasons':problems or ['流行语调查中的候选；网络语义、实际用法与翻译仍需核验'],
            'evidenceSources':len(sources)}


def _validate_translation(text: object, original: str, target: str) -> str:
    if not isinstance(text, str):
        return ''
    value = html.unescape(text).strip()
    if not value or len(value) > MAX_TRANSLATION_LENGTH or _BAD_TEXT.search(value):
        return ''
    if value.casefold() == original.casefold():
        return ''
    if target == 'zh-CN' and not _ZH_SCRIPT.search(value):
        return ''
    if target == 'en' and _JP_SCRIPT.search(value):
        return ''
    if not any(ch.isalnum() for ch in value):
        return ''
    return value


class MyMemoryDraftProvider:
    """Anonymous MyMemory lookup for PUBLIC terms only; no private user data."""
    def translate(self, jp: str, target: str) -> str:
        if target not in ('zh-CN', 'en'):
            raise ValueError('unsupported target')
        if not jp.strip() or len(jp.encode('utf8')) > MAX_TERM_BYTES:
            raise ValueError('invalid public term')
        query = urllib.parse.urlencode({'q':jp, 'langpair':'ja|'+target, 'mt':'1'})
        req = urllib.request.Request(MYMEMORY_ENDPOINT+'?'+query,
            headers={'Accept':'application/json','User-Agent':'JapaneseTrendCollector/1.3 (public-slang-study)'})
        with urllib.request.urlopen(req, timeout=8) as response:
            payload = response.read(16_385)
        if len(payload) > 16_384:
            raise ValueError('oversized translation result')
        data = json.loads(payload.decode('utf-8'))
        if data.get('responseStatus') != 200:
            raise ValueError('translation provider returned error')
        return _validate_translation(data.get('responseData',{}).get('translatedText'),jp,target)


def _draft_age_ok(item: dict, now: datetime) -> bool:
    try:
        duration = (now.date()-date.fromisoformat(item['draftGeneratedAt'])).days
        draft = item.get('translationDraft',{})
        ttl = DRAFT_TTL_DAYS if draft.get('zh') and draft.get('en') else 1
        return 0 <= duration <= ttl
    except (KeyError, ValueError, TypeError):
        return False


def enrich_review_queue(pending: list, previous: list, now: datetime, blacklist: set,
                        *, enable_translation: bool = False, translator=None, max_items: int = MAX_DRAFTS_PER_RUN) -> list:
    """Attach machine drafts to queue only; never edit curated vocabulary.

    Existing valid drafts are reused to avoid repeating network calls at each
    scheduled run. No failures are allowed to break feed generation.
    """
    prior = {p.get('jp'):p for p in previous if isinstance(p,dict) and isinstance(p.get('jp'),str)}
    provider = translator if translator is not None else MyMemoryDraftProvider()
    budget = max(0, min(int(max_items),MAX_DRAFTS_PER_RUN)) if enable_translation else 0
    out=[]
    for item in pending:
        rec = dict(item)
        term=rec.get('jp','')
        rec['quality']=assess_candidate(term,rec.get('evidence',[]),now,blacklist)
        rec['kanaSuggestion']=suggested_kana(term)
        rec['translationStatus']='not_requested'
        old=prior.get(term,{})
        if _draft_age_ok(old,now) and isinstance(old.get('translationDraft'),dict):
            rec['translationDraft']=old['translationDraft']
            rec['draftGeneratedAt']=old['draftGeneratedAt']
            rec['translationStatus']='cached_unverified'
        elif rec.get('status')=='community_signal_needs_independent_meaning_review' and rec.get('communityEvidenceCount',0)<2:
            # A single social mention is a lead, not a meaning signal.
            rec['translationStatus']='awaiting_independent_community_evidence'
        elif budget and rec['quality']['status']=='needs_human_review':
            budget-=1
            suggestions={}
            failed=[]
            for key,target in (('zh','zh-CN'),('en','en')):
                try:
                    raw=provider.translate(term,target)
                    result=_validate_translation(raw,term,target)
                except Exception:
                    result=''
                if result:
                    suggestions[key]=result
                else:
                    failed.append(target)
            if suggestions:
                rec['translationDraft']={'zh':suggestions.get('zh',''), 'en':suggestions.get('en',''),
                    'provider':'MyMemory / machine translation', 'verified':False,
                    'warning':'机器翻译未核对网络语义，禁止未经审核直接发布'}
                rec['draftGeneratedAt']=now.date().isoformat()
            rec['translationStatus']='draft_unverified' if len(suggestions)==2 else 'partial_unverified' if suggestions else 'provider_failed'
            if failed:
                rec['translationWarnings']=['未取得有效的 '+', '.join(failed)+' 机器翻译；候选继续待审核']
        rec['approvedForPublication']=False
        out.append(rec)
    return out
