#!/usr/bin/env python3
"""Bridge Agent Mail provider: normalized reads plus local draft operations."""
import argparse, hashlib, json, subprocess, sys
from datetime import datetime, timezone
from drafts import create as create_draft, get as get_draft, update as update_draft


def envelope(tool, data=None, error=None, code=0):
    out={'ok': error is None, 'tool': tool}
    if error is None:
        out.update({'data': data, 'source': 'agent.qq.com', 'fetched_at': datetime.now(timezone.utc).isoformat(timespec='seconds')})
    else: out['error']=error
    print(json.dumps(out, ensure_ascii=False))
    return code


def cli(cmd, tool):
    try: result=subprocess.run(['agently-cli'] + cmd, capture_output=True, text=True, timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return envelope(tool, error={'type': type(exc).__name__, 'message': str(exc)}, code=1)
    try: payload=json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return envelope(tool, error={'type':'invalid_provider_response','message':'Agent Mail CLI did not return valid JSON'}, code=result.returncode or 1)
    if result.returncode or not payload.get('ok'):
        return envelope(tool, error=payload.get('error') or {'message':'provider request failed'}, code=result.returncode or 1)
    return envelope(tool, payload.get('data'))


def mail_action(operation, payload):
    """Translate a validated JSON request to the provider's confirmation flow."""
    if not isinstance(payload, dict):
        raise ValueError('payload must be an object')
    fields = {
        'send': {'to', 'cc', 'bcc', 'subject', 'body', 'attachment', 'confirmation_token'},
        'reply': {'id', 'cc', 'bcc', 'body', 'attachment', 'reply_all', 'confirmation_token'},
        'forward': {'id', 'to', 'cc', 'bcc', 'body', 'attachment', 'include_attachments', 'confirmation_token'},
        'trash': {'id', 'confirmation_token'},
        'attachment-download': {'msg', 'att', 'output'},
    }
    if set(payload) - fields[operation]:
        raise ValueError('unknown fields in payload')
    required = {'send': ('to', 'subject', 'body'), 'reply': ('id', 'body'),
                'forward': ('id', 'to'), 'trash': ('id',),
                'attachment-download': ('msg', 'att')}[operation]
    for field in required:
        if not payload.get(field):
            raise ValueError(field + ' is required')
    list_fields = {'to', 'cc', 'bcc', 'attachment'}
    bool_fields = {'reply_all', 'include_attachments'}
    for key, value in payload.items():
        if key in list_fields:
            if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
                raise ValueError(key + ' must be a list of nonempty strings')
        elif key in bool_fields:
            if not isinstance(value, bool):
                raise ValueError(key + ' must be boolean')
        elif not isinstance(value, str) or not value.strip():
            raise ValueError(key + ' must be a nonempty string')
    cmd = ['attachment', '+download'] if operation == 'attachment-download' else ['message', '+' + operation]
    for key, value in payload.items():
        flag = '--' + key.replace('_', '-')
        if key in list_fields:
            for item in value: cmd += [flag, item]
        elif key in bool_fields:
            if value: cmd.append(flag)
        else: cmd += [flag, value]
    return cli(cmd, 'mail.' + operation.replace('-', '_'))


def main(argv=None):
    p=argparse.ArgumentParser(description='Bridge Agent Mail provider')
    sub=p.add_subparsers(dest='operation', required=True)
    sub.add_parser('account', aliases=['me'])
    listing=sub.add_parser('list'); listing.add_argument('--limit',type=int,default=10); listing.add_argument('--cursor'); listing.add_argument('--unread',action='store_true')
    search=sub.add_parser('search'); search.add_argument('--query',required=True); search.add_argument('--limit',type=int,default=10); search.add_argument('--cursor')
    read=sub.add_parser('read'); read.add_argument('--id',required=True)
    dc=sub.add_parser('draft-create'); dc.add_argument('--payload-json',required=True)
    dg=sub.add_parser('draft-get'); dg.add_argument('--id',required=True)
    du=sub.add_parser('draft-update'); du.add_argument('--id',required=True); du.add_argument('--version',type=int,required=True); du.add_argument('--changes-json',required=True)
    sp=sub.add_parser('send-prepare'); sp.add_argument('--draft-id',required=True)
    for name in ('send', 'reply', 'forward', 'trash', 'attachment-download'):
        action=sub.add_parser(name); action.add_argument('--payload-json', help='JSON object; omit to read JSON from stdin')
    a=p.parse_args(argv)
    if a.operation in ('list','search') and not 1 <= a.limit <= 50: return envelope('mail.'+a.operation,error={'type':'invalid_argument','message':'limit must be between 1 and 50'},code=2)
    if a.operation in ('account','me'): return cli(['+me'],'mail.account')
    if a.operation=='list':
        cmd=['message','+list','--dir','inbox','--limit',str(a.limit)]
        if a.cursor: cmd += ['--cursor',a.cursor]
        if a.unread: cmd += ['--is-unread']
        return cli(cmd,'mail.list')
    if a.operation=='search':
        cmd=['message','+search','--dir','inbox','--q',a.query,'--limit',str(a.limit)]
        if a.cursor: cmd += ['--cursor',a.cursor]
        return cli(cmd,'mail.search')
    if a.operation=='read': return cli(['message','+read','--id',a.id],'mail.read')
    try:
        if a.operation in ('send', 'reply', 'forward', 'trash', 'attachment-download'):
            return mail_action(a.operation, json.loads(a.payload_json if a.payload_json is not None else sys.stdin.read()))
        if a.operation=='draft-create': return envelope('mail.draft_create', create_draft(json.loads(a.payload_json)))
        if a.operation=='draft-get': return envelope('mail.draft_get', get_draft(a.id))
        if a.operation=='draft-update': return envelope('mail.draft_update', update_draft(a.id,a.version,json.loads(a.changes_json)))
        draft=get_draft(a.draft_id)
        payload=draft['payload']
        if not payload.get('to') or not payload.get('subject') or not payload.get('body'):
            raise ValueError('sending requires at least one recipient, a subject and a body')
        final_body=payload['body'] + ('\n\n' + payload['signature'] if payload.get('signature') else '')
        final={'to':payload['to'],'cc':payload.get('cc',[]),'bcc':payload.get('bcc',[]),'subject':payload['subject'],'body':final_body,'attachment':payload.get('attachment',[])}
        fingerprint=hashlib.sha256(json.dumps(final,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
        operation={'operation':'send','draft_id':draft['id'],'draft_version':draft['version'],'payload':final,'payload_sha256':fingerprint,'requires_gateway':True,'status':'prepared_not_sent'}
        return envelope('mail.send_prepare',operation)
    except (ValueError, TypeError) as exc:
        return envelope('mail.'+a.operation.replace('-','_'),error={'type':'invalid_argument','message':str(exc)},code=2)

if __name__=='__main__': sys.exit(main())
