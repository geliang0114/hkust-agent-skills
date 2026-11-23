#!/usr/bin/env python3
"""Microsoft Graph Outlook mail adapter for Personal Agent.

Read/search mail, create/update drafts, and send a confirmed draft. This
adapter never accepts a password; provide a delegated Graph bearer token via
GRAPH_ACCESS_TOKEN or GRAPH_TOKEN_FILE.
"""
from __future__ import annotations
import argparse, hashlib, html, json, os, sys
from pathlib import Path
from urllib.parse import quote
from typing import Any, Dict, List, Optional
import requests

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
DEFAULT_SIGNATURE = ""

class GraphError(RuntimeError): pass

def token() -> str:
    value = os.environ.get("GRAPH_ACCESS_TOKEN", "").strip()
    if value: return value
    path = os.environ.get("GRAPH_TOKEN_FILE", "~/.sensebridge/graph_token.json")
    p = Path(path).expanduser()
    if p.is_file():
        try:
            data=json.loads(p.read_text())
            value=str(data.get("access_token", "")).strip()
            if value: return value
        except (OSError, json.JSONDecodeError) as exc: raise GraphError(f"读取 Graph token 失败: {exc}") from exc
    raise GraphError("缺少 GRAPH_ACCESS_TOKEN 或 GRAPH_TOKEN_FILE；请先完成 Microsoft Graph OAuth 授权")

def signature() -> str:
    return os.environ.get("GRAPH_SIGNATURE", DEFAULT_SIGNATURE)

def request(method: str, path: str, *, params=None, body=None) -> Any:
    r=requests.request(method, GRAPH_ROOT+path, headers={"Authorization": f"Bearer {token()}", "Accept":"application/json", "Content-Type":"application/json"}, params=params, json=body, timeout=30)
    if r.status_code >= 400:
        try: detail=r.json().get("error", {}).get("message")
        except ValueError: detail=r.text[:300]
        raise GraphError(f"Graph HTTP {r.status_code}: {detail or 'request failed'}")
    if not r.content: return {}
    return r.json()

def clean_message(item: Dict[str, Any]) -> Dict[str, Any]:
    sender=((item.get("from") or {}).get("emailAddress") or {})
    return {"id":item.get("id"),"subject":item.get("subject"),"from":sender,"receivedDateTime":item.get("receivedDateTime"),"isRead":item.get("isRead"),"bodyPreview":item.get("bodyPreview"),"hasAttachments":item.get("hasAttachments"),"webLink":item.get("webLink")}

def body_html(text: str, *, add_signature: bool=True) -> str:
    content=html.escape(text).replace("\n", "<br>")
    if add_signature and signature():
        content += "<br><br>" + html.escape(signature())
    return f"<div>{content}</div>"

def recipients(values: List[str]) -> List[Dict[str, Dict[str, str]]]:
    return [{"emailAddress": {"address": x.strip()}} for x in values if x.strip()]

def draft_fingerprint(draft: Dict[str, Any]) -> str:
    fields={key:draft.get(key) for key in ("id","isDraft","subject","body","toRecipients","ccRecipients","bccRecipients","changeKey")}
    return hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()

def get_draft(identifier: str) -> Dict[str, Any]:
    draft=request("GET",f"/me/messages/{quote(identifier,safe='')}",params={"$select":"id,isDraft,subject,body,toRecipients,ccRecipients,bccRecipients,changeKey"})
    if not draft.get("isDraft"): raise GraphError("该邮件不是草稿")
    return draft

def main(argv=None) -> int:
    p=argparse.ArgumentParser(description="Microsoft Graph Outlook adapter")
    sub=p.add_subparsers(dest="cmd", required=True)
    l=sub.add_parser("list"); l.add_argument("--folder",default="inbox"); l.add_argument("--top",type=int,default=10)
    s=sub.add_parser("search"); s.add_argument("query"); s.add_argument("--top",type=int,default=10)
    r=sub.add_parser("read"); r.add_argument("id")
    d=sub.add_parser("draft"); d.add_argument("--to",action="append",required=True); d.add_argument("--subject",required=True); d.add_argument("--body",required=True); d.add_argument("--cc",action="append",default=[]); d.add_argument("--no-signature",action="store_true")
    u=sub.add_parser("update-draft"); u.add_argument("id"); u.add_argument("--to",action="append"); u.add_argument("--subject"); u.add_argument("--body"); u.add_argument("--cc",action="append"); u.add_argument("--no-signature",action="store_true")
    v=sub.add_parser("review-draft"); v.add_argument("id")
    e=sub.add_parser("send"); e.add_argument("id"); e.add_argument("--confirm",action="store_true"); e.add_argument("--review-hash",required=True)
    a=p.parse_args(argv)
    try:
        if a.cmd=="list":
            data=request("GET",f"/me/mailFolders/{quote(a.folder,safe='')}/messages",params={"$top":min(max(a.top,1),50),"$orderby":"receivedDateTime desc","$select":"id,subject,from,receivedDateTime,isRead,bodyPreview,hasAttachments,webLink"})
            out={"items":[clean_message(x) for x in data.get("value",[])],"nextLink":data.get("@odata.nextLink")}
            return emit("outlook.list_mail",out)
        if a.cmd=="search":
            data=request("GET","/me/messages",params={"$top":min(max(a.top,1),50),"$search":f'\"{a.query}\"',"$select":"id,subject,from,receivedDateTime,isRead,bodyPreview,hasAttachments,webLink"})
            return emit("outlook.search_mail",{"items":[clean_message(x) for x in data.get("value",[])]})
        if a.cmd=="read":
            data=request("GET",f"/me/messages/{quote(a.id,safe='')}",params={"$select":"id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,bodyPreview,hasAttachments,isRead,webLink"})
            return emit("outlook.read_mail",data)
        if a.cmd=="draft":
            data=request("POST","/me/messages",body={"subject":a.subject,"body":{"contentType":"HTML","content":body_html(a.body,add_signature=not a.no_signature)},"toRecipients":recipients(a.to),"ccRecipients":recipients(a.cc)})
            return emit("outlook.create_draft",{"id":data.get("id"),"subject":data.get("subject"),"isDraft":True})
        if a.cmd=="update-draft":
            body={}
            if a.subject is not None: body["subject"]=a.subject
            if a.body is not None: body["body"]={"contentType":"HTML","content":body_html(a.body,add_signature=not a.no_signature)}
            if a.to is not None: body["toRecipients"]=recipients(a.to)
            if a.cc is not None: body["ccRecipients"]=recipients(a.cc)
            if not body: raise GraphError("没有提供要修改的字段")
            get_draft(a.id)
            data=request("PATCH",f"/me/messages/{quote(a.id,safe='')}",body=body)
            return emit("outlook.update_draft",{"id":a.id,"updated":list(body)})
        if a.cmd=="review-draft":
            draft=get_draft(a.id)
            return emit("outlook.review_draft",{"draft":draft,"review_hash":draft_fingerprint(draft)})
        if a.cmd=="send":
            if not a.confirm: raise GraphError("发送邮件是外部写操作；请在用户确认收件人、主题和正文后再次使用 --confirm")
            draft=get_draft(a.id)
            if draft_fingerprint(draft)!=a.review_hash: raise GraphError("草稿在确认后发生变化，请重新预览并获得确认")
            request("POST",f"/me/messages/{quote(a.id,safe='')}/send")
            return emit("outlook.send_mail",{"id":a.id,"status":"accepted_by_graph","message":"Graph 已接受发送请求；未独立验证送达"})
    except (GraphError, requests.RequestException, ValueError, OSError) as exc:
        print(json.dumps({"ok":False,"error":{"type":exc.__class__.__name__,"message":str(exc)}},ensure_ascii=False)); return 1
    return 2

def emit(tool: str, data: Any) -> int:
    print(json.dumps({"ok":True,"tool":tool,"data":data},ensure_ascii=False)); return 0

if __name__=="__main__": raise SystemExit(main())
