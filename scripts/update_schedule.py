#!/usr/bin/env python3
"""Conservative official-source schedule refresh for N.Flying.

Only events explicitly exposed by official FNC/Japan pages are promoted.
This first version intentionally does not infer dates from search snippets or
unverified social posts. Unparseable official entries are preserved in a
review report rather than silently discarded.
"""
from __future__ import annotations
import json, re, hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data.json"
REPORTS = ROOT / "reports"
TZ = ZoneInfo("Asia/Shanghai")
FNC = "https://www.fncent.com"
JP = "https://nflying-official.jp/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NFlyingScheduleBot/1.0; +https://github.com/matchawasabi/nflying-schedule)"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
MONTHS_AHEAD = 12
MONTHS_BACK = 1

def get(url):
    try:
        r = SESSION.get(url, timeout=25)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or r.encoding
        return r.text
    except Exception as exc:
        print(f"[WARN] fetch failed {url}: {exc}")
        return ""

def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()

def parse_time(text):
    m = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", text)
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else ""

def event_id(date, title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:30] or "event"
    return f"{date}-{slug}"

def fetch_fnc():
    found, unreadable, review = [], [], []
    now = datetime.now(TZ)
    for offset in range(-MONTHS_BACK, MONTHS_AHEAD + 1):
        month = (now.replace(day=1) + timedelta(days=32*offset)).replace(day=1)
        url = f"{FNC}/NFLYING/b/schedule?year={month.year}&month={month.month:02d}"
        html = get(url)
        if not html:
            unreadable.append(url); continue
        soup = BeautifulSoup(html, "html.parser")
        day_urls = {}
        for a in soup.select("a[href]"):
            href = urljoin(FNC, a.get("href", ""))
            m = re.search(r"(?:year=(\d{4}).*?month=(\d{1,2}).*?day=(\d{1,2})|/([0-9]{4})/([0-9]{1,2})/([0-9]{1,2}))", href)
            if m:
                vals = m.groups()
                y, mo, d = (int(vals[i] or vals[i+3]) for i in range(3))
                if y == month.year and mo == month.month:
                    day_urls[f"{y:04d}-{mo:02d}-{d:02d}"] = href
        # Some calendar implementations expose date cells without explicit links.
        for date, detail_url in day_urls.items():
            detail = get(detail_url)
            if not detail:
                unreadable.append(detail_url); continue
            ds = BeautifulSoup(detail, "html.parser")
            text = clean(ds.get_text(" ", strip=True))
            title = ""
            for selector in ["#content h2", "#content h3", ".board_view h2", ".view_title", "h2", "h3"]:
                node = ds.select_one(selector)
                if node and clean(node.get_text(" ", strip=True)):
                    title = clean(node.get_text(" ", strip=True)); break
            if not title:
                review.append({"source": detail_url, "date": date, "reason": "页面可访问但未识别活动标题", "excerpt": text[:500]})
                continue
            time = parse_time(text)
            found.append({
                "id": event_id(date, title), "date": date, "time": time, "tz": "KST", "bj": "",
                "cat": "other", "title": title, "short": title[:12], "venue": "", "ticket": "",
                "status": "confirmed", "sources": [{"label": "FNC 官网日历", "url": detail_url}]
            })
    return found, unreadable, review

def fetch_japan():
    found, unreadable, review = [], [], []
    for url in [urljoin(JP, "schedule/list/"), JP]:
        html = get(url)
        if not html:
            unreadable.append(url); continue
        soup = BeautifulSoup(html, "html.parser")
        # Inspect structured data and schedule-like text; only promote entries
        # when a complete explicit date and title appear in the same item.
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                obj = json.loads(script.string or script.get_text())
                objs = obj if isinstance(obj, list) else [obj]
                for item in objs:
                    if not isinstance(item, dict): continue
                    start = item.get("startDate", "")
                    title = clean(item.get("name", ""))
                    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", start)
                    if m and title:
                        date = "-".join(m.groups())
                        found.append({"id": event_id(date,title), "date":date, "time":"",
                            "tz":"JST", "bj":"", "cat":"other", "title":title,
                            "short":title[:12], "venue":clean(item.get("location",{}).get("name","")) if isinstance(item.get("location"),dict) else "",
                            "ticket":"", "status":"confirmed", "sources":[{"label":"N.Flying 日本官网","url":url}]})
            except Exception:
                pass
        # Preserve source references that need manual parsing.
        for node in soup.select("article, .schedule, .schedule-list li, .news-list li"):
            text = clean(node.get_text(" ", strip=True))
            if re.search(r"20\d{2}[./年-]\d{1,2}[./月-]\d{1,2}", text):
                review.append({"source":url, "reason":"日本官网存在日期内容，需人工确认结构", "excerpt":text[:400]})
    return found, unreadable, review

def main():
    now = datetime.now(TZ)
    old = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {
        "events": [], "changes": [], "unreadable_sources": []
    }
    official, unreadable, review = [], [], []
    a,b,c = fetch_fnc(); official += a; unreadable += b; review += c
    a,b,c = fetch_japan(); official += a; unreadable += b; review += c
    # Ingest explicit-date candidates from official X/Instagram API fetch.
    social_file = REPORTS / "social_posts.json"
    social_errors = []
    if social_file.exists():
        try:
            social = json.loads(social_file.read_text(encoding="utf-8"))
            for e in social.get("candidates", []):
                e = {k:v for k,v in e.items() if not k.startswith("_")}
                e["id"] = event_id(e["date"], e["title"])
                official.append(e)
            social_errors = social.get("errors", [])
        except Exception as exc:
            social_errors = [f"社交平台抓取结果解析失败：{exc}"]
    else:
        social_errors = ["本轮尚未生成官方 X/Instagram 抓取结果"]

    # Existing data remains the baseline; refresh matching IDs with current
    # official records. This avoids deleting future dates if a source is down.
    by_id = {e["id"]: e for e in old.get("events", []) if isinstance(e,dict) and e.get("id")}
    changes = []
    for e in official:
        prev = by_id.get(e["id"])
        if prev is None:
            changes.append({"id":e["id"], "kind":"new", "text":f"新增官方行程：{e['date']} {e['title']}"})
        elif any(prev.get(k) != e.get(k) for k in ("title","time","venue","status")):
            changes.append({"id":e["id"], "kind":"changed", "text":f"官方信息更新：{e['date']} {e['title']}"})
        by_id[e["id"]] = {**(prev or {}), **e}
    cutoff = (now.date() - timedelta(days=14)).isoformat()
    events = [e for e in by_id.values() if e.get("date","") >= cutoff]
    events.sort(key=lambda e:(e.get("date",""),e.get("time",""),e.get("title","")))

    # Compute Beijing display time only where timezone is known.
    for e in events:
        if e.get("time") and e.get("tz") in ("KST","JST"):
            h,m = map(int,e["time"].split(":")); total=(h*60+m-60)%1440
            e["bj"] = f"{total//60:02d}:{total%60:02d}"
        elif e.get("tz") == "北京":
            e["bj"] = e.get("time","")
    data = {
        "updated":now.isoformat(timespec="seconds"),
        "updated_label":now.strftime("%Y-%m-%d %H:%M 北京时间"),
        "changes":changes,
        "changes_note":"本次未发现新增或变更。" if not changes else "",
        "unreadable_sources":sorted(set(unreadable + social_errors + ["官方 Weverse（需先核验官方社区入口并接入读取方式）","官方 YouTube（未配置官方 API）"])),
        "events":events
    }
    DATA.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    REPORTS.mkdir(exist_ok=True)
    report = {"generated_at":data["updated"],"official_entries_seen":len(official),
              "unreadable_sources":data["unreadable_sources"],"manual_review":review,
              "change_count":len(changes),
              "note":"本版本自动解析官方网页和已配置的官方 X/Instagram 接口；第三方非官方信息须至少两个独立原始来源印证；同源转载不计多方。待人工核实内容不会自动写入日历。",
              "verification_policy":{"official_single_source_allowed":True,"official_social_platforms":["X","Instagram","Weverse"],"third_party_min_independent_sources":2,"syndicated_or_reposted_same_origin_counts_as":1,"single_non_official_source_status":"pending_verification","policy_file":"SOURCE_POLICY.md"} }
    (REPORTS/"latest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # Keep original design/template when supplied; otherwise create a small
    # accessible fallback page that reads data.json.
    template = ROOT/"tpl"/"index.html"
    if template.exists():
        html=template.read_text(encoding="utf-8")
        payload=json.dumps(data,ensure_ascii=False,separators=(",",":")).replace("</","<\/")
        if "/*NF_DATA*/" in html:
            html=html.replace("/*NF_DATA*/",payload)
        (ROOT/"index.html").write_text(html,encoding="utf-8")
    elif not (ROOT/"index.html").exists():
        (ROOT/"index.html").write_text("<!doctype html><meta charset='utf-8'><title>N.Flying 行程日历</title><h1>N.Flying 行程日历</h1><p>数据正在初始化，请查看 data.json。</p>",encoding="utf-8")
    print(f"Updated {len(events)} events; new/changed {len(changes)}; review {len(review)}")

if __name__ == "__main__":
    main()
