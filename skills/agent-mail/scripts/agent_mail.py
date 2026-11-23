#!/usr/bin/env python3
"""Read-only Agent Mail tool adapter. OAuth is handled by agently-cli."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone


def main(argv=None):
    p=argparse.ArgumentParser(description="Read messages from the authorized Agent Mail account")
    sub=p.add_subparsers(dest="operation",required=True)
    sub.add_parser("me")
    listing=sub.add_parser("list")
    listing.add_argument("--limit",type=int,default=10)
    listing.add_argument("--cursor")
    listing.add_argument("--unread",action="store_true")
    search=sub.add_parser("search")
    search.add_argument("--query",required=True)
    search.add_argument("--limit",type=int,default=10)
    search.add_argument("--cursor")
    read=sub.add_parser("read")
    read.add_argument("--id",required=True)
    args=p.parse_args(argv)
    cmd=['agently-cli']
    if args.operation=='me': cmd+=['+me']
    elif args.operation=='list':
        cmd+=['message','+list','--dir','inbox','--limit',str(args.limit)]
        if args.cursor: cmd+=['--cursor',args.cursor]
        if args.unread: cmd+=['--is-unread']
    elif args.operation=='search':
        cmd+=['message','+search','--dir','inbox','--q',args.query,'--limit',str(args.limit)]
        if args.cursor: cmd+=['--cursor',args.cursor]
    else: cmd+=['message','+read','--id',args.id]
    if hasattr(args,'limit') and not 1 <= args.limit <= 50:
        print(json.dumps({'ok':False,'error':{'type':'invalid_argument','message':'limit must be between 1 and 50'}})); return 2
    try:
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=45,check=False)
        raw=result.stdout.strip()
        try: payload=json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError('Agent Mail CLI did not return valid JSON')
        if result.returncode != 0 or not payload.get('ok'):
            error=payload.get('error') or {}
            print(json.dumps({'ok':False,'tool':'agent_mail.'+args.operation,'error':error,'exit_code':result.returncode},ensure_ascii=False)); return result.returncode or 1
        out={'ok':True,'tool':'agent_mail.'+args.operation,'data':payload.get('data'),'source':'agent.qq.com','fetched_at':datetime.now(timezone.utc).isoformat(timespec='seconds')}
        if payload.get('_notice'): out['_notice']=payload['_notice']
        print(json.dumps(out,ensure_ascii=False))
        return 0
    except (OSError,subprocess.TimeoutExpired,RuntimeError) as e:
        print(json.dumps({'ok':False,'tool':'agent_mail.'+args.operation,'error':{'type':type(e).__name__,'message':str(e)}},ensure_ascii=False)); return 1

if __name__=='__main__': sys.exit(main())
