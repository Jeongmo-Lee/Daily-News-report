#!/usr/bin/env python3

import os
import re
import smtplib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.request import urlopen, Request
from urllib.parse import quote

try:
    from deep_translator import GoogleTranslator
    TRANSLATOR = GoogleTranslator(source="en", target="ko")
except Exception:
    TRANSLATOR = None


def tr(text: str) -> str:
    if not TRANSLATOR or not text:
        return text
    try:
        return TRANSLATOR.translate(text[:500]) or text
    except Exception:
        return text


def google_news_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"


FEEDS = [
    {
        "name": "무역·수출 뉴스",
        "url": google_news_url("무역 수출 관세"),
        "emoji": "📦",
        "translate": False,
    },
    {
        "name": "경제·거시경제",
        "url": google_news_url("경제 금리 환율 GDP"),
        "emoji": "📊",
        "translate": False,
    },
    {
        "name": "주식·증시",
        "url": google_news_url("주식 코스피 코스닥 증시"),
        "emoji": "📈",
        "translate": False,
    },
    {
        "name": "현대글로비스",
        "url": google_news_url("현대글로비스"),
        "emoji": "🚗",
        "translate": False,
    },
    {
        "name": "HMM (해운)",
        "url": google_news_url("HMM 해운 컨테이너"),
        "emoji": "🛳️",
        "translate": False,
    },
    {
        "name": "종합상사 (삼성물산·포스코인터·LG상사 등)",
        "url": google_news_url("삼성물산 포스코인터내셔널 LG상사 현대코퍼레이션 SK트레이딩인터내셔널 종합상사"),
        "emoji": "🏢",
        "translate": False,
    },
    {
        "name": "국제 경제 (Reuters · 번역)",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "emoji": "🌐",
        "translate": True,
    },
    {
        "name": "글로벌 해운·물류 (번역)",
        "url": "https://www.hellenicshippingnews.com/feed/",
        "emoji": "⚓",
        "translate": True,
    },
]

MAX_ITEMS = 6


def fetch_feed(feed: dict) -> list[dict]:
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
        for item in items[:MAX_ITEMS]:
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
            desc = re.sub(r"<[^>]+>", "", desc)[:200].strip()
            if title:
                if feed.get("translate"):
                    title = tr(title)
                    desc  = tr(desc) if desc else ""
                results.append({"title": title, "link": link, "desc": desc})
        return results
    except Exception as e:
        print(f"  Warning: {feed['name']} 피드 실패: {e}")
        return []


def build_html(news_by_source: list[tuple[dict, list[dict]]]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y년 %m월 %d일")
    sections = ""
    for feed, items in news_by_source:
        if not items:
            continue
        rows = ""
        for item in items:
            anchor = (
                f'<a href="{item["link"]}" style="color:#1a73e8;text-decoration:none;font-weight:600;">{item["title"]}</a>'
                if item["link"] else f'<strong>{item["title"]}</strong>'
            )
            desc_html = (
                f'<p style="margin:4px 0 0;color:#555;font-size:13px;">{item["desc"]}</p>'
                if item["desc"] else ""
            )
            rows += f'<li style="margin-bottom:14px;line-height:1.5;">{anchor}{desc_html}</li>'
        sections += f"""
        <div style="margin-bottom:32px;">
          <h2 style="margin:0 0 12px;font-size:16px;color:#222;border-left:4px solid #1a73e8;padding-left:10px;">
            {feed['emoji']} {feed['name']}
          </h2>
          <ul style="margin:0;padding-left:20px;list-style:disc;">{rows}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'Apple SD Gothic Neo',Arial,sans-serif;">
  <div style="max-width:660px;margin:28px auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.12);">
    <div style="background:linear-gradient(135deg,#0d47a1,#1565c0);padding:28px 32px;">
      <h1 style="margin:0;color:#fff;font-size:22px;">📬 오늘의 경제·무역·기업 뉴스</h1>
      <p style="margin:8px 0 0;color:#90caf9;font-size:13px;">{today} — 무역 · 해운 · 주식 · 관심 기업</p>
    </div>
    <div style="padding:28px 32px;">{sections}</div>
    <div style="padding:16px 32px;background:#f8f9fa;border-top:1px solid #e0e0e0;font-size:12px;color:#999;text-align:center;">
      GitHub Actions 자동 발송 · 매일 오전 8시 KST
    </div>
  </div>
</body></html>"""


def send_email(html_body: str, recipient: str, sender: str, app_password: str) -> None:
    today = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    subject = f"📬 오늘의 경제·무역·기업 뉴스 — {today}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.sendmail(sender, [recipient], msg.as_string())
    print(f"✅ 이메일 발송 완료 → {recipient}")


def main():
    recipient    = os.environ.get("EMAIL_RECIPIENT", "jeongmo.lee.biz@gmail.com")
    sender       = os.environ.get("GMAIL_SENDER")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not sender or not app_password:
        raise EnvironmentError("GMAIL_SENDER와 GMAIL_APP_PASSWORD 환경변수가 필요합니다.")

    print("📡 뉴스 피드 수집 중...")
    news_by_source = []
    for feed in FEEDS:
        print(f"  → {feed['name']} ...")
        items = fetch_feed(feed)
        print(f"     {len(items)}개 기사")
        news_by_source.append((feed, items))

    total = sum(len(i) for _, i in news_by_source)
    if total == 0:
        print("수집된 기사가 없어 이메일을 발송하지 않습니다.")
        return

    send_email(build_html(news_by_source), recipient, sender, app_password)


if __name__ == "__main__":
    main()
