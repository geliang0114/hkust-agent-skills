#!/usr/bin/env python3
"""Interactive Microsoft identity platform device-code login for Graph."""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote
import requests

SCOPES = 'openid profile offline_access User.Read Mail.ReadWrite Mail.Send'


def main():
    p=argparse.ArgumentParser(description='Sign in to Microsoft Graph using device code')
    p.add_argument('--client-id',default=os.environ.get('GRAPH_CLIENT_ID'))
    p.add_argument('--tenant',default=os.environ.get('GRAPH_TENANT_ID','organizations'))
    p.add_argument('--cache',default=os.environ.get('GRAPH_TOKEN_FILE','~/.sensebridge/graph_token.json'))
    a=p.parse_args()
    if not a.client_id:
        print('缺少 GRAPH_CLIENT_ID：请使用已注册的 Microsoft Entra 公共客户端应用 ID。',file=sys.stderr); return 1
    base='https://login.microsoftonline.com/'+quote(a.tenant,safe='')+'/oauth2/v2.0/'
    try:
        r=requests.post(base+'devicecode',data={'client_id':a.client_id,'scope':SCOPES},timeout=30); d=r.json()
        if not r.ok or 'device_code' not in d:
            print('设备码请求失败: '+str(d.get('error_description') or d.get('error') or r.status_code),file=sys.stderr); return 1
        print(d.get('message') or f"打开 {d['verification_uri']} 输入代码 {d['user_code']}",file=sys.stderr,flush=True)
        deadline=time.monotonic()+int(d.get('expires_in',900)); interval=max(1,int(d.get('interval',5)))
        while time.monotonic()<deadline:
            time.sleep(interval)
            r=requests.post(base+'token',data={'grant_type':'urn:ietf:params:oauth:grant-type:device_code','client_id':a.client_id,'device_code':d['device_code']},timeout=30); result=r.json()
            if r.ok and result.get('access_token'):
                path=Path(a.cache).expanduser(); path.parent.mkdir(parents=True,exist_ok=True)
                if path.exists():
                    print('令牌文件已存在；请指定新的 GRAPH_TOKEN_FILE，避免覆盖现有会话。',file=sys.stderr); return 1
                result.update({'client_id':a.client_id,'tenant':a.tenant,'expires_at':int(time.time())+int(result.get('expires_in',3600))})
                fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(result,f)
                print(json.dumps({'ok':True,'cache':str(path),'expires_at':result['expires_at']})); return 0
            error=result.get('error')
            if error=='authorization_pending': continue
            if error=='slow_down': interval+=5; continue
            print('微软登录未完成: '+str(result.get('error_description') or error or r.status_code),file=sys.stderr); return 1
        print('设备码已过期，请重新登录。',file=sys.stderr); return 1
    except (requests.RequestException, ValueError, OSError) as exc:
        print('登录失败: '+str(exc),file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
