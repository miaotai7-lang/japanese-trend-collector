"""Evidence-based bilingual lookup for the PUBLIC trending vocabulary feed.

No LLM, user-data transfer or private API key. Only publish entries matched in
both publicly licensed Japanese->Chinese and Japanese->English dictionaries.
This is an *unreviewed dictionary candidate*, never a certified contextual translation.
"""
from __future__ import annotations

import gzip
import json
import re
import urllib.request
from pathlib import Path

CN_SOURCE = 'https://raw.githubusercontent.com/lxl66566/Japanese-Chinese-thesaurus/main/final.json'
EN_SOURCE = 'https://www.edrdg.org/pub/Nihongo/edict2u.gz'
MAX_CN_BYTES = 5_000_000
MAX_EDICT_BYTES = 35_000_000
AGENT = 'JapanWordsLearningFeed/1.1 (read-only CC-licensed dictionaries)'

# Janome can return standalone pieces of grammar, generic predicates or news boilerplate.
# Exclude them from the lexicon even if another dictionary has an entry.
GARBAGE = set('れる られる せる させる てる ちゃう しまう いる ある なる ない たい です ます いい よい する した された こと もの ところ よう のに うち ため これ それ あれ どれ みんな ほか より だけ ほど でも なら また など ですか という そんな こんな あんな'.split())


def eligible_word(word: str, reading: str) -> bool:
    if word in GARBAGE or not reading:
        return False
    if not re.fullmatch(r'[\u3041-\u309f\u30a0-\u30ff\u3400-\u9fffー・]+', word):
        return False
    if not re.fullmatch(r'[\u3041-\u309fー]+', reading):
        return False
    if len(word) < 2 or len(word) > 30:
        return False
    # Isolated kana endings and many filler expressions are not useful standalone terms.
    if re.fullmatch(r'[\u3041-\u309fー]+', word) and len(word) < 3:
        return False
    return True


def safe_chinese(raw: object) -> str:
    if not isinstance(raw, str):
        return ''
    s = ' '.join(raw.strip().split())
    # Unlicensed mixed dictionaries sometimes include grammar markup instead of an entry gloss.
    if (not 1 <= len(s) <= 100 or not re.search(r'[\u3400-\u9fff]', s)
            or re.search(r'\[名|\[动|\[形|\[场所|https?://|\\n|①.*②.*③', s)):
        return ''
    return s


def safe_english(raw: str) -> str:
    if not isinstance(raw, str):
        return ''
    s = re.sub(r'^(?:\([^)]{1,60}\)\s*)+', '', raw.strip())
    s = re.sub(r'^\(\d+\)\s*', '', s).strip()
    s = re.sub(r'\s*\{[^}]+\}', '', s)
    if (not 2 <= len(s) <= 125 or not re.search(r'[A-Za-z]{2}', s)
            or re.search(r'(?i)\b(?:see also|usage note|see entry|see under|dictionary|JMdict entry)\b', s)):
        return ''
    return s


def parse_chinese_json(body: bytes) -> dict[str, str]:
    mapping = json.loads(body.decode('utf-8-sig'))
    if not isinstance(mapping, dict):
        raise ValueError('invalid Japanese-Chinese JSON root')
    return {k:v2 for k,v in mapping.items() if isinstance(k,str) and (v2:=safe_chinese(v))}


def parse_edict2u(body: bytes, min_entries=1000) -> dict[str, str]:
    """Parse EDICT2u UTF-8 into exact Japanese spelling -> English sense candidates.

    Conservative: only the first standalone English gloss is returned. Do not
    conflate related Japanese homographs from different dictionary entries.
    """
    text = gzip.decompress(body).decode('utf-8-sig')
    out = {}
    for line in text.splitlines():
        if ' /' not in line:
            continue
        left,right=line.split(' /', 1)
        defs=right.split('/')
        english=''
        for part in defs:
            candidate=safe_english(part)
            if candidate:
                english=candidate
                break
        if not english:
            continue
        # EDICT2 contains alternative spellings separated by ; and kana after [reading].
        surface=left.split(' [', 1)[0].strip()
        for raw_form in surface.split(';'):
            form=re.sub(r'\([^)]*\)', '', raw_form).strip()
            if form and re.fullmatch(r'[\u3041-\u309f\u30a0-\u30ff\u3400-\u9fffー・]+', form):
                out.setdefault(form, english)
    if len(out) < min_entries:
        raise ValueError('EDICT2u dictionary unexpectedly small or wrong encoding')
    return out


def fetch_bounded(url: str, size: int, timeout: int=55) -> bytes:
    req=urllib.request.Request(url,headers={'User-Agent':AGENT})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        data=response.read(size+1)
    if not data or len(data)>size:
        raise ValueError('dictionary download empty or exceeds limit')
    return data


def load_reference_dictionaries(cache_dir: str | Path, *, allow_network=True):
    """Cache raw sources; network failures cannot substitute machine translation.

    A caller MUST stop publication if either source is unavailable; publishing
    unverified empty fields would reintroduce the original reported defect.
    """
    cache=Path(cache_dir);cache.mkdir(parents=True,exist_ok=True)
    paths=[cache/'jp-zh-final.json',cache/'edict2u.gz']
    for path,url,limit in zip(paths,[CN_SOURCE,EN_SOURCE],[MAX_CN_BYTES,MAX_EDICT_BYTES]):
        if path.is_file() and path.stat().st_size > 200:
            continue
        if not allow_network:
            raise FileNotFoundError(f'Missing offline dictionary fixture: {path.name}')
        payload=fetch_bounded(url,limit)
        path.write_bytes(payload)
    cn=parse_chinese_json(paths[0].read_bytes())
    en=parse_edict2u(paths[1].read_bytes())
    if len(cn) < 1000 or len(en) < 1000:
        raise ValueError('dictionary coverage insufficient; do not publish')
    return cn,en


def improve_entries(state: dict, jp_zh: dict[str,str], jp_en: dict[str,str]) -> dict:
    """Erase unsafe legacy automatic candidates and repopulate from BOTH dictionaries.

    Historical title samples / counts / sources remain. We never touch Firebase,
    and never overwrite a manually verified word (if any).
    """
    stats={'candidates':0,'bilingual':0,'removed_legacy_translations':0,'filtered':0}
    for e in state.get('terms',{}).values():
        stats['candidates']+=1
        if e.get('verification') == '人工已核对':
            if eligible_word(e.get('jp',''),e.get('kana','')) and e.get('zh') and e.get('en'):
                e['qualityApproved']=True
                stats['bilingual']+=1
            continue
        if e.get('zh') or e.get('en'):
            stats['removed_legacy_translations']+=1
        # Never continue trusting old MyMemory results on subsequent runs.
        e['zh']=''; e['en']='';e.pop('translationSources',None)
        e['qualityApproved']=False
        e['verification']='词典候选，未按语境人工核对'
        jp=e.get('jp','');kana=e.get('kana','')
        if not eligible_word(jp,kana):
            stats['filtered']+=1
            continue
        zh=jp_zh.get(jp,'')
        en=jp_en.get(jp,'')
        if zh and en:
            e['zh']=zh;e['en']=en
            e['verification']='日中/日英公开词典候选，未按语境人工核对'
            e['translationSources']=['Japanese-Chinese-thesaurus (Unlicense)','EDRDG EDICT2u (CC BY-SA)']
            e['qualityApproved']=True
            stats['bilingual']+=1
    return stats
