#!/usr/bin/env python3
"""Fetch N.Flying official X and Instagram posts using official APIs.

Secrets/environment:
  X_BEARER_TOKEN                 X API app bearer token
  META_ACCESS_TOKEN              Meta Graph API user access token
  META_IG_USER_ID                Instagram professional account ID connected to the Meta app
  META_GRAPH_VERSION             optional, defaults to v24.0

Posts are stored as source evidence. A post is only promoted to the calendar
when it contains an unambiguous explicit date and an event keyword; ambiguous
items remain in reports/social_review.json.
"""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
TIMEOUT = 25
HEADERS = {"User-Agent": "NFlyingScheduleBot/1.0"}
EVENT_WORDS = re.compile(
    r"(concert|live|tour|fan.?meeting|fan.?con|showcase|festival|"
    r"공연|콘서트|팬미팅|팬콘|페스티벌|ライブ|コンサート|ファンミ|"
    r"イベント|サイン会|영통|영상통화|팬사인회)",
    re.I,
)
DATE_PATTERNS = [
    re.compile(r"(?P<y>20\d{2})[./年-](?P<m>0?[1-9]|1[0-2])[./月-](?P<d>0?[1-9]|[12]\d|3[01])日?"),
    re.compile(r"(?P<m>0?[1-9]|1[0-2])[./月](?P<d>0?[1-9]|[12]\d|3[01])日"),
]
MONTHS = {m.lower(): i for i, m in enumerate(
    ["January","February","March","April","May","June","July","August","September","October","November","December"],1)}
MONTHS.update({k[:3].lower():v for k,v in list(MONTHS.items())})

def req_json(url, headers=None, params=None):
    r = requests.get(url, headers=headers or HEADERS, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def x_fetch():
    token = os.getenv("X_BEARER_TOKEN")
    if not token:
        return [], "未配置 GitHub Secret：X_BEARER_TOKEN"
    headers = {"Authorization": f"Bearer {token}", **HEADERS}
    posts, errors = [], []
    for username in ("NFlyingofficial", "NF_official_jp"):
        try:
            user = req_json("https://api.x.com/2/users/by/username/" + username,
                            headers, {"user.fields":"id,username,name,verified"})
            uid = user["data"]["id"]
            result = req_json(f"https://api.x.com/2/users/{uid}/tweets", headers, {
                "max_results": 100,
                "tweet.fields": "id,text,created_at,lang,referenced_tweets",
                "exclude": "retweets,replies",
            })
            for p in result.get("data", []):
                posts.append({
                    "platform":"X", "account":"@"+username,
                    "id":p.get("id"), "text":p.get("text",""),
                    "created_at":p.get("created_at",""),
                    "url":f"https://x.com/{username}/status/{p.get('id')}",
                    "source_type":"official_social",
                })
        except Exception as e:
            errors.append(f"X @{username}: {type(e).__name__}: {e}")
    return posts, errors

def instagram_fetch():
    token = os.getenv("META_ACCESS_TOKEN")
    ig_id = os.getenv("META_IG_USER_ID")
    if not token or not ig_id:
        return [], "未配置 GitHub Secrets：META_ACCESS_TOKEN / META_IG_USER_ID"
    version = os.getenv("META_GRAPH_VERSION", "v24.0")
    username = "letsroll_nf"
    fields = f"business_discovery.username({username}){{username,media.limit(50){{id,caption,permalink,timestamp,media_type}}}}"
    try:
        data = req_json(f"https://graph.facebook.com/{version}/{ig_id}",
                        HEADERS, {"fields":fields, "access_token":token})
        profile = data.get("business_discovery", {})
        if profile.get("username","").lower() != username:
            return [], "Instagram Business Discovery 返回账号不匹配，已停止采信"
        posts = []
        for p in profile.get("media",{}).get("data",[]):
            posts.append({
                "platform":"Instagram", "account":"@"+username,
                "id":p.get("id"), "text":p.get("caption",""),
                "created_at":p.get("timestamp",""), "url":p.get("permalink",""),
                "source_type":"official_social",
            })
        return posts, None
    except Exception as e:
        return [], f"Instagram @{username}: {type(e).__name__}: {e}"

def parse_dates(text, post_year):
    dates = []
    for m in DATE_PATTERNS[0].finditer(text):
        try:
            dates.append(f"{int(m.group('y')):04d}-{int(m.group('m')):02d}-{int(m.group('d')):02d}")
        except ValueError:
            pass
    if not dates:
        for m in DATE_PATTERNS[1].finditer(text):
            try:
                dates.append(f"{post_year:04d}-{int(m.group('m')):02d}-{int(m.group('d')):02d}")
            except ValueError:
                pass
    for m in re.finditer(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})(?:,?\s+(20\d{2}))?\b", text, re.I):
        try:
            month = MONTHS[m.group(1).lower()]
            year = int(m.group(3) or post_year)
            dates.append(f"{year:04d}-{month:02d}-{int(m.group(2)):02d}")
        except ValueError:
            pass
    return list(dict.fromkeys(dates))

def main():
    x_posts, x_error = x_fetch()
    ig_posts, ig_error = instagram_fetch()
    posts = x_posts + ig_posts
    review, candidates = [], []
    for p in posts:
        created = p.get("created_at","")
        try:
            year = datetime.fromisoformat(created.replace("Z","+00:00")).year
        except Exception:
            year = datetime.now(timezone.utc).year
        txt = p.get("text","")
        dates = parse_dates(txt, year)
        if EVENT_WORDS.search(txt) and dates:
            # Retain the complete official post text as the title/evidence.
            # Human review is required before splitting multi-day ranges or
            # interpreting relative dates, time zones, and ticket details.
            title = next((re.sub(r"\s+"," ",line).strip() for line in txt.splitlines() if line.strip()), re.sub(r"\s+"," ",txt).strip())
            title = title[:110]
            cat = "sign_online" if re.search(r"(sign|영통|영상통화|팬사인회|サイン会)", txt, re.I) else ("fanmeeting" if re.search(r"(fan.?meeting|팬미팅|ファンミ)", txt, re.I) else "concert")
            for date in dates:
                candidates.append({
                    "date":date, "title":title,
                    "time":"", "tz":"KST" if p["platform"]=="X" else "JST",
                    "bj":"", "cat":cat, "venue":"", "ticket":"",
                    "status":"confirmed", "short":"官方社媒行程",
                    "sources":[{"label":f"官方{p['platform']} {p['account']}",
                                "url":p["url"], "published_at":created,
                                "source_type":"official"}],
                    "_evidence_text":txt
                })
        elif txt.strip():
            review.append({**p, "reason":"未能从原帖中同时识别明确日期和活动关键词，保留人工核验"})
    payload = {
        "fetched_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "posts_count":len(posts), "posts":posts, "candidates":candidates,
        "errors":[x for x in (x_error,ig_error) if x],
    }
    (REPORTS/"social_posts.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (REPORTS/"social_review.json").write_text(json.dumps(review,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Social posts fetched: {len(posts)}; explicit-date candidates: {len(candidates)}; review: {len(review)}")
    for e in payload["errors"]: print("[SOCIAL SOURCE]", e)

if __name__ == "__main__":
    main()
