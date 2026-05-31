#!/usr/bin/env python3
"""
Servidor Flask do Dashboard Meta Ads - Mirella Imóveis.
Uso: python app.py
Acessar: http://localhost:5000/dashboard
"""

import json, os, sys, time, datetime

try:
    import requests
except ImportError:
    os.system("pip install requests")
    import requests

from flask import Flask, render_template, jsonify, request

# ===== CONFIG =====
APP_ID = "1028593009630321"
APP_SECRET = "09b831c19ef1dd187a57b9a7d0a8a0e0"
AD_ACCOUNT = "act_941166705291997"
BUSINESS_ID = "2729714934094405"
API_VERSION = "v22.0"
TOKEN_FILE = ".meta-token.json"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(SCRIPT_DIR, TOKEN_FILE)

# Cache em memória (evita bater na API a cada refresh)
cache = {"data": None, "expires_at": 0, "ttl": 300}

app = Flask(__name__)

# ===== TOKEN =====

def load_token():
    if os.path.exists(TOKEN_PATH):
        try:
            with open(TOKEN_PATH, "r") as f:
                data = json.load(f)
            if data.get("expires_at", 0) > time.time() - 86400:
                return data["token"]
        except:
            pass
    return None

def get_token():
    token = load_token()
    if token:
        return token
    env_token = os.environ.get("META_TOKEN")
    if env_token:
        save_token(env_token, 5184000)
        return env_token
    raise Exception("Token não encontrado. Defina META_TOKEN no ambiente ou execute: python gerar-dashboard.py --token=SEU_TOKEN")

# ===== API =====

def api_get(path, params=None):
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/{path}"
    resp = requests.get(url, headers=headers, params=params)
    data = resp.json()
    if "error" in data:
        raise Exception(f"API {path}: {data['error']}")
    return data

def fetch_all(path, params=None):
    if params is None:
        params = {}
    items = []
    result = api_get(path, params)
    items.extend(result.get("data", []))
    next_url = result.get("paging", {}).get("next")
    while next_url:
        resp = requests.get(next_url)
        result = resp.json()
        items.extend(result.get("data", []))
        next_url = result.get("paging", {}).get("next")
    return items

def safe_float(v, default=0.0):
    try: return float(v)
    except: return default

def safe_int(v, default=0):
    try: return int(v)
    except: return default

def parse_actions(insight):
    leads = 0
    for a in insight.get("actions", []):
        if a.get("action_type") in ("lead", "leadgen", "onsite_conversion.lead_grouped_instant_form"):
            leads += int(a.get("value", 0))
    cpl = None
    for cap in insight.get("cost_per_action_type", []):
        if cap.get("action_type") in ("lead", "leadgen", "onsite_conversion.lead_grouped_instant_form"):
            try: cpl = float(cap.get("value", "0"))
            except: pass
    return leads, cpl

def fetch_all_data():
    today = datetime.date.today()
    start_90 = today - datetime.timedelta(days=90)
    start_180 = today - datetime.timedelta(days=180)

    def tr(since, until):
        return json.dumps({"since": since.isoformat(), "until": until.isoformat()})

    campaigns = fetch_all(f"{AD_ACCOUNT}/campaigns", {"fields": "id,name,status,objective", "limit": 50})

    daily = fetch_all(f"{AD_ACCOUNT}/insights", {
        "time_range": tr(start_90, today),
        "time_increment": 1,
        "fields": "date_start,spend,impressions,clicks,ctr,cpc,cpm,reach",
        "limit": 100
    })

    current = fetch_all(f"{AD_ACCOUNT}/insights", {
        "time_range": tr(start_90, today),
        "fields": "spend,impressions,clicks,ctr,cpc,cpm,reach,frequency,actions,cost_per_action_type",
        "limit": 10
    })

    previous = fetch_all(f"{AD_ACCOUNT}/insights", {
        "time_range": tr(start_180, start_90 - datetime.timedelta(days=1)),
        "fields": "spend,impressions,clicks,ctr,cpc,cpm,reach,frequency,actions,cost_per_action_type",
        "limit": 10
    })

    camp_rows = fetch_all(f"{AD_ACCOUNT}/insights", {
        "time_range": tr(start_90, today),
        "level": "campaign",
        "fields": "campaign_name,spend,impressions,clicks,ctr,cpc,cpm,reach,frequency,actions,cost_per_action_type",
        "limit": 50
    })

    ads = fetch_all(f"{AD_ACCOUNT}/ads", {
        "fields": "id,name,status,creative{thumbnail_url,image_url,title,body},insights{spend,impressions,clicks,ctr,cpc}",
        "limit": 50
    })

    return {
        "today": today,
        "start_90": start_90,
        "start_180": start_180,
        "campaigns": campaigns,
        "daily": daily,
        "current": current[0] if current else {},
        "previous": previous[0] if previous else {},
        "camp_rows": camp_rows,
        "ads": ads
    }

def get_data():
    now = time.time()
    if cache["data"] and now < cache["expires_at"]:
        return cache["data"]
    cache["data"] = fetch_all_data()
    cache["expires_at"] = now + cache["ttl"]
    return cache["data"]

# ===== HELPERS DE FORMATAÇÃO =====

def pct(cur, prev):
    if prev == 0: return None
    return ((cur - prev) / prev) * 100

def fmt_money(v):
    if v >= 10000: return f"R$ {v/1000:.1f}K"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_cpc(v):
    return f"R$ {v:.2f}".replace(".", ",")

def fmt_ctr(v):
    return f"{v:.2f}%"

def fmt_delta(val, reverse=False):
    if val is None:
        return {"html": '<span class="delta neutral">—</span>', "icon": "—", "pct": ""}
    arrow = "&#9650;" if val > 0 else "&#9660;"
    cls = "up" if (val > 0 and not reverse) or (val < 0 and reverse) else "down"
    return {"html": f'<span class="delta {cls}">{arrow} {abs(val):.1f}%</span>', "icon": arrow, "pct": f"{abs(val):.1f}%"}

# ===== ROTAS =====

@app.route("/dashboard")
def dashboard():
    try:
        d = get_data()
        cur, prev = d["current"], d["previous"]

        c_spend = safe_float(cur.get("spend"))
        c_imps = safe_int(cur.get("impressions"))
        c_clicks = safe_int(cur.get("clicks"))
        c_ctr = safe_float(cur.get("ctr"))
        c_cpc = safe_float(cur.get("cpc"))
        c_cpm = safe_float(cur.get("cpm"))
        c_reach = safe_int(cur.get("reach"))
        c_leads, c_cpl = parse_actions(cur)

        p_spend = safe_float(prev.get("spend"))
        p_imps = safe_int(prev.get("impressions"))
        p_clicks = safe_int(prev.get("clicks"))
        p_ctr = safe_float(prev.get("ctr"))
        p_cpc = safe_float(prev.get("cpc"))
        p_cpm = safe_float(prev.get("cpm"))
        p_reach = safe_int(prev.get("reach"))
        p_leads, p_cpl = parse_actions(prev)

        cards = [
            {"icon": "fa-coins", "label": "Gasto", "value": fmt_money(c_spend),
             "delta": fmt_delta(pct(c_spend, p_spend))},
            {"icon": "fa-users", "label": "Leads", "value": str(c_leads),
             "delta": fmt_delta(pct(c_leads, p_leads))},
            {"icon": "fa-chart-pie", "label": "ROAS", "value": f"{c_leads/max(c_spend,1):.1f}x",
             "delta": fmt_delta(pct(c_leads/max(c_spend,1), p_leads/max(p_spend,1)))},
            {"icon": "fa-mouse-pointer", "label": "CPC", "value": fmt_cpc(c_cpc),
             "delta": fmt_delta(pct(c_cpc, p_cpc), reverse=True)},
            {"icon": "fa-percent", "label": "CTR", "value": fmt_ctr(c_ctr),
             "delta": fmt_delta(pct(c_ctr, p_ctr))},
            {"icon": "fa-eye", "label": "CPM", "value": fmt_cpc(c_cpm),
             "delta": fmt_delta(pct(c_cpm, p_cpm), reverse=True)},
        ]

        daily_labels = [x.get("date_start","") for x in d["daily"]]
        daily_spend = [safe_float(x.get("spend")) for x in d["daily"]]
        daily_imps = [safe_int(x.get("impressions")) for x in d["daily"]]

        # Mapa de campanhas anteriores para comparação na tabela
        camp_map = {}
        # Busca dados anteriores por campanha (já disponível via fetch)
        camp_prev = fetch_all(f"{AD_ACCOUNT}/insights", {
            "time_range": json.dumps({"since": d["start_180"].isoformat(), "until": (d["start_90"] - datetime.timedelta(days=1)).isoformat()}),
            "level": "campaign",
            "fields": "campaign_name,spend",
            "limit": 50
        })
        for c in camp_prev:
            camp_map[c.get("campaign_name")] = c

        camp_table = []
        for c in d["camp_rows"]:
            name = c.get("campaign_name", "N/A")
            sp = safe_float(c.get("spend"))
            cpc = safe_float(c.get("cpc"))
            ctr = safe_float(c.get("ctr"))
            leads, cpl = parse_actions(c)
            p_sp = safe_float(camp_map.get(name, {}).get("spend"))
            camp_table.append({
                "name": name,
                "spend": fmt_money(sp),
                "spend_raw": sp,
                "cpc": fmt_cpc(cpc),
                "ctr": fmt_ctr(ctr),
                "leads": leads,
                "cpl": fmt_cpc(cpl) if cpl else "—",
                "delta": fmt_delta(pct(sp, p_sp)) if p_sp else {"html": "", "icon": "", "pct": ""}
            })

        ads_list = []
        for ad in d["ads"][:20]:
            creative = ad.get("creative", {}) or {}
            thumb = creative.get("thumbnail_url") or creative.get("image_url") or ""
            ins = ad.get("insights", {}).get("data", [{}])[0] if ad.get("insights", {}).get("data") else {}
            ads_list.append({
                "name": ad.get("name", "Anúncio"),
                "status": ad.get("status", "UNKNOWN"),
                "thumb": thumb,
                "cpc": fmt_cpc(safe_float(ins.get("cpc"))),
                "ctr": fmt_ctr(safe_float(ins.get("ctr"))),
                "spend": fmt_money(safe_float(ins.get("spend")))
            })

        return render_template("dashboard.html",
            cards=cards,
            daily_labels=json.dumps(daily_labels),
            daily_spend=json.dumps(daily_spend),
            daily_imps=json.dumps(daily_imps),
            camp_table=camp_table,
            ads_list=ads_list,
            updated_at=datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            today=d["today"],
            start_90=d["start_90"]
        )
    except Exception as e:
        return f"<h2>Erro ao carregar dashboard</h2><pre>{e}</pre>", 500

@app.route("/api/refresh")
def api_refresh():
    cache["data"] = None
    cache["expires_at"] = 0
    return jsonify({"status": "ok", "message": "Cache limpo. Próximo acesso buscará dados novos."})

@app.route("/")
def index():
    return "<h2>Dashboard Meta Ads - Mirella Imóveis</h2><p>Acesse <a href='/dashboard'>/dashboard</a></p>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 5000))
    print(f"🚀 Servidor rodando em http://0.0.0.0:{port}")
    print(f"📊 Dashboard: http://0.0.0.0:{port}/dashboard")
    debug = os.environ.get("RENDER") is None
    app.run(host="0.0.0.0", port=port, debug=debug)
