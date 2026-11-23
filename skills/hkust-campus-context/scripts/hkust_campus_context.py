#!/usr/bin/env python3
"""Read-only HKUST(GZ) campus context connector."""
from __future__ import annotations
import argparse, datetime as dt, html, json, os, re, sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
from hkust_portal_calendar import DEFAULT_SESSION_PATH, PortalCalendarClient, PortalCalendarError, PORTAL_ORIGIN, parse_jsonp

EVENTS_ORIGIN = "https://events.hkust-gz.edu.cn"
EVENTS_API = f"{EVENTS_ORIGIN}/api/event-public"
PORTAL_CONTEXT_P = "YXM9MiZ0PTEmcD0xJm09TiY_"
PORTAL_CONTENT_P = "YXQ9NSZwPTEmbT1OJg__"

class CampusContextError(RuntimeError): pass
class _TextExtractor(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self, data): self.parts.append(data)
def clean_html(value):
    if value is None: return ""
    p=_TextExtractor(); p.feed(html.unescape(str(value)))
    return re.sub(r"\s+", " ", " ".join(p.parts)).strip()
def _portal_session_path(username):
    explicit=os.environ.get("HKUST_PORTAL_SESSION")
    if explicit: return Path(explicit).expanduser()
    return DEFAULT_SESSION_PATH
def _decode(response, callback=None):
    response.raise_for_status()
    try: return response.json()
    except (ValueError, json.JSONDecodeError):
        value=response.text.strip()
        if callback and value.startswith(callback+"("):
            return parse_jsonp(value.rstrip(";"), callback)
        raise CampusContextError("门户响应不是预期的 JSON 或 JSONP")
def _portal_data(payload, label):
    if not isinstance(payload,dict): raise CampusContextError(f"{label} 返回格式异常")
    if payload.get("result") not in (None,1,"1",True): raise CampusContextError(str(payload.get("reason") or f"{label} 请求失败"))
    return payload.get("data")
def _now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

class CampusContextClient:
    def __init__(self, portal=None, http=None):
        self.http=http or requests.Session(); self.http.headers.update({"User-Agent":"SenseBridge-HKUST-CampusContext/0.1","Accept":"application/json"}); self.portal=portal
    def _public(self,path,params):
        r=self.http.get(EVENTS_API+path,params=params,timeout=30); p=_decode(r)
        if not isinstance(p,dict) or p.get("code") not in (0,200,"0","200"): raise CampusContextError(str((p or {}).get("message") or "校园活动接口请求失败"))
        return p.get("data")
    def list_activities(self,page=1,page_size=20,locale="en",campus="gz",keyword=""):
        if page<1 or page_size<1 or page_size>100: raise ValueError("page 必须从 1 开始，page_size 必须在 1 到 100 之间")
        data=self._public("/public/event/page",{"locale":locale,"campusCode":campus,"pagination":json.dumps({"current":page,"pageSize":page_size},separators=(",",":"))}) or {}
        out=[]
        for x in data.get("events") or []:
            out.append({"id":x.get("id"),"title":clean_html(x.get("title")),"start_date":x.get("startAt"),"end_date":x.get("endAt"),"venue":clean_html((x.get("venue") or {}).get("location")),"organizer":x.get("organizerOrganizer") or x.get("author"),"event_format":x.get("eventFormat") or [],"audience":x.get("recommendedFor") or [],"status":x.get("eventStatus"),"detail_url":f"{EVENTS_ORIGIN}/detail/{x.get('id')}" if x.get("id") else "","source":EVENTS_ORIGIN})
        if keyword: out=[x for x in out if keyword.casefold() in (x["title"]+" "+x["venue"]).casefold()]
        return {"events":out,"pagination":data.get("pagination") or {},"keyword_scope":"current_page" if keyword else None}
    def get_activity(self,activity_id,locale="en"):
        if activity_id<=0: raise ValueError("activity_id 必须为正整数")
        x=(self._public("/public/event/get",{"id":activity_id,"locale":locale}) or {}).get("event") or {}; base=x.get("event") or {}; content=x.get("content") or {}; date=content.get("eventDate") or {}; venue=content.get("venue") or {}; reg=content.get("registration") or {}
        return {"id":base.get("id") or activity_id,"title":clean_html((content.get("title") or {}).get("title")),"start_date":date.get("startAtDate"),"end_date":date.get("endAtDate"),"start_time":date.get("startAtTime"),"end_time":date.get("endAtTime"),"venue":clean_html(venue.get("location")),"abstract":clean_html((content.get("abstract") or {}).get("abstract")),"speakers":[clean_html((s or {}).get("name")) for s in content.get("speakers") or []],"audience":content.get("recommendedFor") or [],"event_format":content.get("eventFormat") or [],"registration":{"required":reg.get("registrationRequired"),"review_required":reg.get("registrationReviewRequired"),"url":reg.get("registrationUrl") or "","start_at":reg.get("registrationStartAt"),"end_at":reg.get("registrationEndAt")},"status":base.get("eventStatus"),"source":f"{EVENTS_ORIGIN}/detail/{activity_id}"}
    def _portal(self,path,params,callback):
        if not self.portal: raise CampusContextError("MyPortal 会话未初始化")
        r=self.portal.session.get(PORTAL_ORIGIN+path,params={**params,"callback":callback},timeout=30)
        if "sso.hkust-gz.edu.cn" in r.url or "Account/Login" in r.text: raise CampusContextError("门户会话已失效，请使用 --relogin 重新登录")
        return _portal_data(_decode(r,callback),path)
    def announcements(self,kind="notice",locale="en"):
        if kind not in {"notice","news","activity"}: raise ValueError("kind 必须是 notice、news 或 activity")
        d=self._portal("/sopplus/_web/customized/getHkustArticleList.jsp",{"_p":PORTAL_CONTENT_P,"wybs":kind,"lang":locale},"campusAnnouncements") or {}
        return [{"title":clean_html(x.get("title")),"published_at":x.get("date"),"url":x.get("linkUrl") or "","column":x.get("colName") or kind,"source":PORTAL_ORIGIN} for x in d.get("list") or []]
    def portal_tasks(self,done=False,category="all"):
        path="/sopplus/_web/customized/todo/donetask.jsp" if done else "/sopplus/_web/customized/todo/todotask.jsp"; d=self._portal(path,{"_p":PORTAL_CONTEXT_P,"taskCategoryCode":category},"campusTasks") or {}; items=d.get("list") or []; return {"done":done,"category":category,"total":d.get("total",len(items)),"items":items}
    def unread_mail_count(self):
        d=self._portal("/sopplus/_web/customized/email/getUnReadCount.jsp",{"_p":PORTAL_CONTEXT_P},"unreadMail")
        try:return int(d or 0)
        except (TypeError,ValueError) as e: raise CampusContextError("邮件未读数格式异常") from e
    def library_loans(self,page=0,page_size=50):
        d=self._portal("/sopplus/_web/customized/book/queryBookList.jsp",{"_p":PORTAL_CONTEXT_P,"page":page,"pageSize":page_size},"libraryLoans") or {}; return {"total":d.get("total",0),"items":d.get("list") or []}
    def portal_apps(self,favorites=False,category_id="32",language="en"):
        if favorites: d=self._portal("/sopplus/_web/customized/getMyFavoriteApps.jsp",{"_p":PORTAL_CONTEXT_P,"parentCategoryId":category_id,"name":"MyFavoriteApps_side","clientType":"2","lang":language},"portalApps") or []; items=d if isinstance(d,list) else []
        else: d=self._portal("/sopplus/_web/customized/loadAllServiceApps.jsp",{"_p":PORTAL_CONTEXT_P,"parentCategoryId":category_id,"clientType":"2","appName":"","categoryId":"","lang":language},"portalApps") or {}; items=d.get("appList") or []
        keys=("id","name","appDetail","appUrl","entranceUrl","appType","isAllow","onlyEntry","enableService")
        return [{k:x.get(k) for k in keys if k in x} for x in items]

def _portal_client(relogin):
    username=os.environ.get("HKUST_USERNAME") or (input("HKUST username: ").strip() if sys.stdin.isatty() else "")
    if not username: raise CampusContextError("缺少 HKUST_USERNAME")
    c=PortalCalendarClient(session_path=_portal_session_path(username))
    if relogin or not c.load_session():
        password=os.environ.get("HKUST_PASSWORD")
        if not password and sys.stdin.isatty():
            import getpass; password=getpass.getpass("HKUST password: ")
        if not password: raise CampusContextError("缺少 HKUST_PASSWORD")
        c.login(username,password)
    probe=c.session.get(PORTAL_ORIGIN+"/sopplus/_web/customized/loginInfo.jsp",params={"_p":PORTAL_CONTEXT_P,"callback":"identityCheck"},timeout=30)
    if "sso.hkust-gz.edu.cn" in probe.url: raise CampusContextError("门户会话已失效，请使用 --relogin 重新登录")
    identity=_portal_data(_decode(probe,"identityCheck"),"用户身份") or {}
    if str(identity.get("loginName") or "").casefold()!=username.casefold(): raise CampusContextError("门户会话账号与 HKUST_USERNAME 不一致，请重新登录")
    return c
def emit(tool,data,source): print(json.dumps({"ok":True,"tool":tool,"data":data,"source":source,"fetched_at":_now()},ensure_ascii=False)); return 0
def main(argv=None):
    p=argparse.ArgumentParser(description="Read-only HKUST(GZ) campus context"); s=p.add_subparsers(dest="command",required=True)
    a=s.add_parser("activities"); a.add_argument("--page",type=int,default=1); a.add_argument("--page-size",type=int,default=20); a.add_argument("--locale",default="en"); a.add_argument("--campus",default="gz"); a.add_argument("--keyword",default="")
    d=s.add_parser("activity"); d.add_argument("id",type=int); d.add_argument("--locale",default="en")
    n=s.add_parser("announcements"); n.add_argument("--kind",choices=["notice","news","activity"],default="notice"); n.add_argument("--locale",default="en"); n.add_argument("--relogin",action="store_true")
    t=s.add_parser("tasks"); t.add_argument("--done",action="store_true"); t.add_argument("--category",default="all"); t.add_argument("--relogin",action="store_true")
    m=s.add_parser("unread-mail"); m.add_argument("--relogin",action="store_true")
    l=s.add_parser("loans"); l.add_argument("--page",type=int,default=0); l.add_argument("--page-size",type=int,default=50); l.add_argument("--relogin",action="store_true")
    q=s.add_parser("apps"); q.add_argument("--favorites",action="store_true"); q.add_argument("--category-id",default="32"); q.add_argument("--language",default="en"); q.add_argument("--relogin",action="store_true")
    x=p.parse_args(argv)
    try:
        if x.command=="activities": return emit("hkust_campus.list_activities",CampusContextClient().list_activities(x.page,x.page_size,x.locale,x.campus,x.keyword),EVENTS_ORIGIN)
        if x.command=="activity": return emit("hkust_campus.get_activity",CampusContextClient().get_activity(x.id,x.locale),EVENTS_ORIGIN)
        c=CampusContextClient(_portal_client(getattr(x,"relogin",False)))
        if x.command=="announcements": return emit("hkust_campus.list_announcements",c.announcements(x.kind,x.locale),PORTAL_ORIGIN)
        if x.command=="tasks": return emit("hkust_campus.list_tasks",c.portal_tasks(x.done,x.category),PORTAL_ORIGIN)
        if x.command=="unread-mail": return emit("hkust_campus.unread_mail_count",{"count":c.unread_mail_count()},PORTAL_ORIGIN)
        if x.command=="loans": return emit("hkust_campus.list_library_loans",c.library_loans(x.page,x.page_size),PORTAL_ORIGIN)
        return emit("hkust_campus.list_portal_apps",c.portal_apps(x.favorites,x.category_id,x.language),PORTAL_ORIGIN)
    except (CampusContextError,PortalCalendarError,requests.RequestException,ValueError,OSError) as e: print(json.dumps({"ok":False,"error":{"type":e.__class__.__name__,"message":str(e)}},ensure_ascii=False)); return 1
if __name__=="__main__": raise SystemExit(main())
