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
    args=p.parse_args(argv)
    feed=run(args.root,args.catalog,no_network=args.no_network)
    print('STRICT INTERNET SLANG ONLY: {} published; {} pending review'.format(len(feed['items']),feed['counts']['pendingReview']))
    print('No general news-headline token frequency or machine translation is used.')
    if not feed['items']:
        print('NOTICE: no currently documented slang entries; do not recycle expired rankings.')
    return 0

if __name__=='__main__':sys.exit(main())
