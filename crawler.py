#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import time
import json
import sqlite3
import requests
import schedule
import plotly.graph_objs as go
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import Counter
from jinja2 import Environment, FileSystemLoader


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


DB_PATH = "history.db"
TEMPLATE_PATH = "templates"
TEMPLATE_NAME = "report_template.html"
OUTPUT_HTML = "rapport.html"
SITES_FILE = "sites.txt"
DEPTH = 2  # profondeur d'exploration
NOTIF_TITLE = "Monitor Ping"

# --- Fonctions existantes de crawling + stockage ---

def load_sites(file_path=SITES_FILE):
    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip()]

def extract_internal_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    base_domain = urlparse(base_url).netloc
    for a in soup.find_all("a", href=True):
        full = urljoin(base_url, a["href"])
        if urlparse(full).netloc == base_domain:
            links.add(full)
    return links

def check_url(url, timeout=10):
    try:
        start = time.time()
        res = requests.get(url, timeout=timeout)
        dt = round(time.time() - start, 3)
        ok = res.ok
        links = extract_internal_links(url, res.text) if "text/html" in res.headers.get("Content-Type", "") else []
        return {"url": url, "status_code": res.status_code, "response_time": dt, "ok": ok, "error": None, "links": links}
    except Exception as e:
        return {"url": url, "status_code": None, "response_time": None, "ok": False, "error": str(e), "links": []}

def explore_site(base_url):
    visited, results = set(), []
    def _visit(u, level):
        if u in visited or level > DEPTH: return
        visited.add(u)
        r = check_url(u)
        results.append(r)
        if level < DEPTH:
            for l in r["links"]:
                _visit(l, level+1)
    _visit(base_url, 0)
    return results

def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    status_code INTEGER,
                    response_time REAL,
                    ok BOOLEAN,
                    error TEXT,
                    FOREIGN KEY(check_id) REFERENCES checks(id)
                )""")
    conn.commit(); conn.close()

def save_results(results, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    ts = datetime.utcnow().isoformat()
    c.execute("INSERT INTO checks (timestamp) VALUES (?)", (ts,))
    cid = c.lastrowid
    for r in results:
        c.execute("""INSERT INTO pages
                     (check_id,url,status_code,response_time,ok,error)
                     VALUES (?,?,?,?,?,?)""",
                  (cid, r["url"], r["status_code"], r["response_time"], r["ok"], r["error"]))
    conn.commit(); conn.close()
    return ts

# --- Extraction pour rapport + historique 12h ---

def get_latest_check(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, timestamp FROM checks ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    if not row: return None, []
    cid, ts = row
    c.execute("SELECT url,status_code,response_time,ok,error FROM pages WHERE check_id=?", (cid,))
    pages = [{"url":u,"status_code":sc,"response_time":rt,"ok":bool(ok),"error":err}
             for u,sc,rt,ok,err in c.fetchall()]
    conn.close()
    return ts, pages

def get_history_12h(db_path=DB_PATH):
    """Retourne un histogramme hourly des UP vs DOWN des 12 dernières heures."""
    cutoff = datetime.utcnow() - timedelta(hours=12)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""SELECT ch.timestamp, p.ok
                 FROM pages p
                 JOIN checks ch ON p.check_id=ch.id
                 WHERE ch.timestamp >= ?""", (cutoff.isoformat(),))
    data = c.fetchall()
    conn.close()
    # Grouper par heure
    hours = [(datetime.fromisoformat(ts).replace(minute=0,second=0,microsecond=0), ok) for ts,ok in data]
    counter = {}
    for hr, ok in hours:
        counter.setdefault(hr, {"up":0,"down":0})
        counter[hr]["up" if ok else "down"] += 1
    # Tris
    hrs = sorted(counter.keys())
    ups = [counter[h]["up"] for h in hrs]
    dns = [counter[h]["down"] for h in hrs]
    labels = [h.strftime("%H:%M") for h in hrs]
    return labels, ups, dns

# --- Génération du rapport avec Jinja2 + Plotly ---

def generate_html_report(ts, pages, output=OUTPUT_HTML):
    # répartition dernier check
    codes = [p["status_code"] for p in pages if p["status_code"]]
    cnt = Counter(codes)
    labels, vals = list(map(str,cnt.keys())), list(cnt.values())
    # historique 12h
    hrs, ups, dns = get_history_12h()
    env = Environment(loader=FileSystemLoader(TEMPLATE_PATH))
    tpl = env.get_template(TEMPLATE_NAME)
    html = tpl.render(
        timestamp=ts,
        pages=pages,
        status_labels=labels,
        status_counts=vals,
        hist_labels=hrs,
        hist_up=ups,
        hist_down=dns
    )
    with open(output, "w") as f:
        f.write(html)

# --- Notification KDE si besoin ---

def notify_if_fail(pages):
    fails = [p for p in pages if not p["ok"]]
    if not fails: 
        return
    msg = "\n".join(f"{p['url']} → {p.get('status_code','?')}" for p in fails)
    os.system(f"notify-send \"{NOTIF_TITLE}\" \"Sites DOWN:\\n{msg}\"")

# --- Tâche principale et scheduling ---

def job():
    init_db()
    sites = load_sites()
    all_pages = []
    for s in sites:
        res = explore_site(s)
        all_pages.extend(res)
    ts = save_results(all_pages)
    _, latest = get_latest_check()
    generate_html_report(ts, latest)
    notify_if_fail(latest)
    print(f"[{datetime.utcnow().isoformat()}] Check done, report updated.")

if __name__ == "__main__":
    # Lancer immédiatement une première execution
    job()
    # Schedule toutes les 30 min
    schedule.every(30).minutes.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)
