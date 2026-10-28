#!/usr/bin/env python3
"""V8.5.3 strict Japanese internet-slang curator; no ordinary headline tokens."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from slang_only import run


def main(argv=None):
    p=argparse.ArgumentParser(description='Publish verified recent Japanese slang only')
    p.add_argument('--root',default='docs')
    p.add_argument('--catalog',default='slang_terms.json')
    p.add_argument('--no-network',action='store_true',help='Offline audit; keep catalog and existing reports')
    p.add_argument('--translate-pending',action='store_true',help='Generate unverified Chinese and English drafts for new public slang candidates (never auto-publish)')
    p.add_argument('--translation-limit',type=int,default=8,help='Maximum draft candidates per run (0-8)')
    args=p.parse_args(argv)
    feed=run(args.root,args.catalog,no_network=args.no_network,
        translate_pending=args.translate_pending,translation_limit=args.translation_limit)
    print('STRICT INTERNET SLANG ONLY: {} published; {} pending review'.format(len(feed['items']),feed['counts']['pendingReview']))
    print('No general-news token frequency is used; machine translations, when enabled, are unverified pending drafts only.')
    if not feed['items']:
        print('NOTICE: no currently documented slang entries; do not recycle expired rankings.')
    return 0

if __name__=='__main__':sys.exit(main())
