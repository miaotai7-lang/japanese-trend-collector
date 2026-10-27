"""V8.5.3: surfacing *automatically observed* Japanese slang candidates.

Input: news RSS candidate queue created by trend_signals.record_candidates.
Output: evidence-labelled candidate records. No hand-written slang whitelist,
no invented translation, no claim that a single headline proves popularity.
"""
from __future__ import annotations
import hashlib
import re
from datetime import date, timedelta
from urllib.parse import urlsplit

JAPANESE = re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')
HIRAGANA = re.compile(r'[\u3041-\u309fー]+')
SLANG_CONTEXT = re.compile(r'流行語|若者言葉|ネットスラング|ミーム|バズワード|新語|スラング|Z世代|トレンド')


def reading_of(word, tokenizer):
    if not tokenizer:
        return ''
    try:
        tokens=list(tokenizer.tokenize(word))
        if len(tokens)>8 or not tokens:
            return ''
        readings=[tok.reading for tok in tokens]
        if any(r=='*' or not r for r in readings):
            return ''
        text=''.join(readings)
        text=''.join(chr(ord(ch)-96) if '\u30a1' <= ch <= '\u30f6' else ch for ch in text)
        return text if HIRAGANA.fullmatch(text) else ''
    except Exception:
        return ''


def discover_from_rss(state, tokenizer=None, jp_zh=None, jp_en=None, today=None, limit=120):
    """Produce a labelled stream from actual RSS headlines, never seeded words.

    A candidate can be displayed without a gloss, distinctly labelled *unverified*;
    it must never be treated as a confirmed slang term or added to the study lexicon.
    """
    today=today or date.today()
    jp_zh=jp_zh or {}
    jp_en=jp_en or {}
    candidates=[]
    queue=state.get('slangReviewQueue',{})
    if not isinstance(queue,dict):return []
    for entry in queue.values():
        if not isinstance(entry,dict):continue
        term=str(entry.get('jp','')).strip()
        if not (2<=len(term)<=24 and JAPANESE.search(term)):
            continue
        try:
            observed=date.fromisoformat(str(entry.get('lastSeen','')))
        except ValueError:
            continue
        age=(today-observed).days
        if not (0<=age<=45):continue
        sources=[];identities=set()
        for s in entry.get('sources',[]):
            if not isinstance(s,dict):continue
            url=str(s.get('url',''))
            u=urlsplit(url)
            title=str(s.get('title',''))
            if u.scheme!='https' or not u.hostname or not SLANG_CONTEXT.search(title):continue
            if url in identities:continue
            identities.add(url)
            sources.append({'url':url[:650], 'title':title[:150], 'publisher':str(s.get('publisher',''))[:60]})
        if not sources:continue
        reading=reading_of(term,tokenizer)
        zh=str(jp_zh.get(term,'')).strip()[:150]
        en=str(jp_en.get(term,'')).strip()[:150]
        complete=bool(reading and zh and en)
        mentions=max(len(sources),int(entry.get('mentions') or 0))
        # Source count is *evidence of reporting*, not a nationwide slang frequency.
        # A phrase observed by independent URLs ranks higher than a one-off quote.
        confidence='多篇报道候选（尚未核实）' if len(sources)>=2 else '单篇报道线索（尚未核实）'
        candidates.append({
          'id':'rss-'+hashlib.sha256(term.encode('utf8')).hexdigest()[:18],
          'jp':term,'kana':reading,'zh':zh,'en':en,
          'verification':confidence,'translationComplete':complete,
          'firstSeen':str(entry.get('firstSeen','')),'lastSeen':observed.isoformat(),
          'mentions':mentions,'sources':sources[:4],
          'score':len(sources)*8+min(mentions,20)+max(0,45-age)//3,
          'label':'自动从近期日本公开报道标题提取；是否真是流行语及释义仍需核对',
        })
    candidates.sort(key=lambda x:(-x['score'],-x['mentions'],x['jp']))
    return candidates[:limit]
