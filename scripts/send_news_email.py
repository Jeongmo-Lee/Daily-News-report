#!/usr/bin/env python3

import os
import smtplib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.request import urlopen, Request

FEEDS = [
    {"name": "BBC World News", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "emoji": "🇬🇧"},
    {"name": "Reuters World", "url": "https://feeds.reuters.com/reuters/worldNews", "emoji": "📰"},
    {"name": "AP News World", "url": "https://rsshub.app/apnews/topics/world-news", "emoji": "🌐"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "emoji": "🌍"},
]

MAX_ITEMS_PER_FEED = 5


def fetch_feed(feed):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}
    try:
        req = Request(feed["url"], headers=headers)
        with urlopen(req, timeout=15) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        results = []
        for item in items[:MAX_ITEMS_PER_FEED]:
            import re
            title = item.findtext("title", "").strip()
            link  = item.findtext("link",  "").strip()
            desc  = item.findtext("description", "").strip()
            if not title:
                title = item.findtext("{http://www.w3.org/2005/Atom}title", "").strip()
            if not link:
                el = item.find("{http://www.w3.org/2005/Atom}link")
                link = el.get("href", "") if el is not None else ""
            if not desc:
                desc = item.findtext("{http://www.w3.org/2005/Atom}summary", "").strip()
            desc = re.sub(r"<[^>]+>", "", desc)[:200]
            if title:
                results.append({"title": title, "link": link, "desc": desc})
        return results
    except Exception as e:
        print(f"  Warning: failed to fetch {feed['name']}: {e}")
        return []


def build_html(news_by_source):
    today = datetime.now(timezone.utc).strftime("%Y년 %m월 %d일")
    sections = ""
    for feed, items in news_by_source:
        if not items:
            continue
        rows = ""
        for item in items:
            link = (f'<a href="{item["link"]}" style="color:#1a73e8;text-decoration:none;font-weight:600;">{item["title"]}</a>'
                    if item["link"] else f'<strong>{item["title"]}</strong>')
            desc = f'<p style="margin:4px 0 0;color:#555;font-size:13px;">{item["desc"]}</p>' if item["desc"] else ""
            rows += f'<li style="margin-bottom:14px;line-height:1.5;">{link}{desc}</li>'
        sections += f"""
        <div style="margin-bottom:32px;">
          <h2 style="margin:0 0 12px;font-size:16px;color:#333;border-left:4px solid #1a73e8;padding-left:10px;">
            {feed['emoji']} {feed['name']}
          </h2>
          <ul style="margin:0;padding-left:20px;list-style:disc;">{rows}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:'Apple SD Gothic Neo',Arial,sans-serif;">
  <div style="max-width:640px;margin:24px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);">
    <div style="background:linear-gradient(135deg,#1a73e8,#0d47a1);padding:24px 28px;">
      <h1 style="margin:0;color:#fff;font-size:22px;">🌏 오늘의 국제 정세 뉴스</h1>
      <p style="margin:6px 0 0;color:#c8d8f8;font-size:14px;">{today} UTC 기준</p>
    </div>
    <div style="padding:24px 28px;">{sections}</div>
    <div style="padding:16px 28px;background:#f8f9fa;border-top:1px solid #e0e0e0;font-size:12px;color:#888;text-align:center;">
      이 메일은 GitHub Actions를 통해 자동 발송되었습니다.
    </div>
  </div>
</body></html>"""


def send_email(html_body, recipient, sender, app_password):
    today = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    subject = f"🌏 오늘의 국제 정세 뉴스 - {today}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.sendmail(sender, [recipient], msg.as_string())
    print(f"Email sent to {recipient}")


def main():
    recipient    = os.environ.get("EMAIL_RECIPIENT", "jeongmo.lee.biz@gmail.com")
    sender       = os.environ.get("GMAIL_SENDER")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not sender or not app_password:
        raise EnvironmentError("GMAIL_SENDER and GMAIL_APP_PASSWORD must be set.")

    print("Fetching news feeds...")
    news_by_source = []
    for feed in FEEDS:
        print(f"  Fetching {feed['name']}...")
        items = fetch_feed(feed)
        print(f"  -> {len(items)} articles")
        news_by_source.append((feed, items))

    if sum(len(i) for _, i in news_by_source) == 0:
        print("No articles fetched. Skipping email.")
        return

    send_email(build_html(news_by_source), recipient, sender, app_password)


if __name__ == "__main__":
    main()
