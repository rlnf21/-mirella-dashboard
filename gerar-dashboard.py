#!/usr/bin/env python3
"""
Gerador de Dashboard Meta Ads para Mirella Imóveis.
Gera dashboard-meta-mirella.html com dados reais da API.
Uso: python gerar-dashboard.py
"""

import json, os, sys, time, datetime, textwrap

try:
    import requests
except ImportError:
    print("Instalando requests...")
    os.system("pip install requests")
    import requests

# ===== CONFIG =====
APP_ID = "1028593009630321"
APP_SECRET = "09b831c19ef1dd187a57b9a7d0a8a0e0"
AD_ACCOUNT = "act_941166705291997"
API_VERSION = "v22.0"
TOKEN_FILE = ".meta-token.json"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(SCRIPT_DIR, TOKEN_FILE)

# ===== TOKEN MANAGEMENT =====
BUSINESS_ID = "2729714934094405"

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

def save_token(token, expires_in=5184000):
    data = {
        "token": token,
        "expires_at": time.time() + expires_in,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(TOKEN_PATH, "w") as f:
        json.dump(data, f, indent=2)

def get_app_token():
    url = f"{BASE_URL}/oauth/access_token"
    params = {
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "grant_type": "client_credentials",
        "scope": "ads_read,ads_management,business_management"
    }
    resp = requests.get(url, params=params)
    data = resp.json()
    if "access_token" in data:
        return data["access_token"]
    return None

def try_create_system_user(app_token):
    print("Tentando criar System User no Business Manager...")
    url = f"{BASE_URL}/{BUSINESS_ID}/system_users"
    params = {
        "name": "Dashboard Mirella",
        "role": "EMPLOYEE",
        "access_token": app_token
    }
    resp = requests.post(url, params=params)
    data = resp.json()
    if "id" in data:
        su_id = data["id"]
        print(f"  System User criado: {su_id}")
        # Atribuir app ao system user
        url2 = f"{BASE_URL}/{su_id}/applications"
        params2 = {"app_id": APP_ID, "access_token": app_token}
        requests.post(url2, params=params2)
        # Gerar token
        url3 = f"{BASE_URL}/{su_id}/access_tokens"
        params3 = {
            "app_id": APP_ID,
            "scope": "ads_read,ads_management,business_management",
            "access_token": app_token
        }
        resp3 = requests.post(url3, params=params3)
        td = resp3.json()
        if "access_token" in td:
            return td["access_token"]
        print(f"  Falha ao gerar token do system user: {td}")
    else:
        print(f"  Falha ao criar system user: {data}")
    return None

def get_token():
    token = load_token()
    if token:
        return token

    print("Obtendo app token...")
    app_token = get_app_token()
    if not app_token:
        print("  App token falhou. Vamos tentar manual.")
    else:
        print("  App token obtido. Tentando criar system user...")
        sys_token = try_create_system_user(app_token)
        if sys_token:
            save_token(sys_token, 5184000)
            return sys_token

    print("\\n" + "="*70)
    print("NÃO FOI POSSÍVEL GERAR TOKEN AUTOMATICAMENTE.")
    print("="*70)
    print("""
VOCÊ PRECISA GERAR UM TOKEN MANUALMENTE:

1. Acesse: https://developers.facebook.com/tools/explorer/
2. Selecione o app 'Dashboard Mirella Imóveis' (ID: {app_id})
3. Permissões: ads_read, ads_management, business_management
4. Gere o token (curto) e clique em 'Exchange Token' (long-lived, 60 dias)
5. Copie o token gerado

Depois, execute o script com:
  python gerar-dashboard.py --token=SEU_TOKEN_AQUI

Ou crie o arquivo {token_file} manualmente com:
  {{"token": "SEU_TOKEN", "expires_at": 9999999999, "generated_at": "2026-05-31"}}
""".format(app_id=APP_ID, token_file=TOKEN_FILE))
    sys.exit(1)

# ===== API FETCH =====

def api_get(path, params=None):
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/{path}"
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 401:
        os.remove(TOKEN_PATH)
        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}
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

def fetch_campaigns():
    print("Buscando campanhas...")
    fields = "id,name,status,objective,daily_budget,lifetime_budget,start_time,created_time"
    return fetch_all(f"{AD_ACCOUNT}/campaigns", {"fields": fields, "limit": 50})

def fetch_insights(time_range, level="account", fields_extra=None):
    fields = "spend,impressions,clicks,ctr,cpc,cpm,reach,frequency"
    if fields_extra:
        fields += f",{fields_extra}"
    params = {
        "time_range": json.dumps(time_range),
        "level": level,
        "fields": fields,
        "limit": 500
    }
    return fetch_all(f"{AD_ACCOUNT}/insights", params)

def fetch_daily_insights():
    print("Buscando insights diários (90d)...")
    fields = "date_start,spend,impressions,clicks,ctr,cpc,cpm,reach"
    params = {
        "date_preset": "last_90d",
        "time_increment": 1,
        "fields": fields,
        "limit": 100
    }
    return fetch_all(f"{AD_ACCOUNT}/insights", params)

def fetch_campaign_insights(time_range):
    fields = "campaign_name,spend,impressions,clicks,ctr,cpc,cpm,reach,frequency,actions,cost_per_action_type"
    params = {
        "time_range": json.dumps(time_range),
        "level": "campaign",
        "fields": fields,
        "limit": 50
    }
    return fetch_all(f"{AD_ACCOUNT}/insights", params)

def fetch_ads():
    print("Buscando anúncios...")
    fields = "id,name,status,creative{thumbnail_url,image_url,title,body},insights{spend,impressions,clicks,ctr,cpc}"
    return fetch_all(f"{AD_ACCOUNT}/ads", {"fields": fields, "limit": 50})

def parse_actions(insight):
    leads = 0
    for a in insight.get("actions", []):
        if a.get("action_type") in ("lead", "leadgen", "onsite_conversion.lead_grouped_instant_form"):
            leads += int(a.get("value", 0))
    cpl = None
    for cap in insight.get("cost_per_action_type", []):
        if cap.get("action_type") in ("lead", "leadgen", "onsite_conversion.lead_grouped_instant_form"):
            val = cap.get("value", "0")
            try:
                cpl = float(val)
            except:
                pass
    return leads, cpl

def safe_float(v, default=0.0):
    try:
        return float(v)
    except:
        return default

def safe_int(v, default=0):
    try:
        return int(v)
    except:
        return default

# ===== HTML GENERATION =====

def generate_html(current, previous, daily, campaigns, ads):
    today = datetime.date.today()
    start_90 = today - datetime.timedelta(days=90)
    start_180 = today - datetime.timedelta(days=180)
    c_spend = safe_float(current.get("spend"))
    c_imps = safe_int(current.get("impressions"))
    c_clicks = safe_int(current.get("clicks"))
    c_ctr = safe_float(current.get("ctr"))
    c_cpc = safe_float(current.get("cpc"))
    c_cpm = safe_float(current.get("cpm"))
    c_reach = safe_int(current.get("reach"))
    c_leads, c_cpl = parse_actions(current)

    p_spend = safe_float(previous.get("spend"))
    p_imps = safe_int(previous.get("impressions"))
    p_clicks = safe_int(previous.get("clicks"))
    p_ctr = safe_float(previous.get("ctr"))
    p_cpc = safe_float(previous.get("cpc"))
    p_cpm = safe_float(previous.get("cpm"))
    p_reach = safe_int(previous.get("reach"))
    p_leads, p_cpl = parse_actions(previous)

    def pct(cur, prev):
        if prev == 0:
            return None
        return ((cur - prev) / prev) * 100

    delta_spend = pct(c_spend, p_spend)
    delta_leads = pct(c_leads, p_leads)
    delta_ctr = pct(c_ctr, p_ctr)
    delta_cpc = pct(c_cpc, p_cpc)
    delta_cpm = pct(c_cpm, p_cpm)
    delta_reach = pct(c_reach, p_reach)

    c_roas = c_spend / max(c_leads, 1)
    p_roas = p_spend / max(p_leads, 1)
    delta_roas = pct(c_roas, p_roas)

    def fmt_delta(val, reverse=False):
        if val is None:
            return '<span class="delta neutral">—</span>'
        arrow = "&#9650;" if val > 0 else "&#9660;"
        cls = "up" if (val > 0 and not reverse) or (val < 0 and reverse) else "down"
        return f'<span class="delta {cls}">{arrow} {abs(val):.1f}%</span>'

    def fmt_money(v):
        if v >= 10000:
            return f"R$ {v/1000:.1f}K"
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def fmt_number(v):
        if v >= 10000:
            return f"{v/1000:.1f}K"
        if v >= 1000:
            return f"{v/1000:.1f}K"
        return str(v)

    def fmt_ctr(v):
        return f"{v:.2f}%"

    def fmt_cpc(v):
        return f"R$ {v:.2f}".replace(".", ",")

    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    daily_labels = json.dumps([d.get("date_start", "") for d in daily])
    daily_spend = json.dumps([safe_float(d.get("spend")) for d in daily])
    daily_imps = json.dumps([safe_int(d.get("impressions")) for d in daily])
    daily_clicks = json.dumps([safe_int(d.get("clicks")) for d in daily])

    # Campaign table rows
    camp_rows = fetch_campaign_insights({"since": start_90.isoformat(), "until": today.isoformat()})
    camp_prev = fetch_campaign_insights({"since": start_180.isoformat(), "until": (start_90 - datetime.timedelta(days=1)).isoformat()})
    camp_map = {}
    for c in camp_prev:
        camp_map[c.get("campaign_name")] = c

    table_rows = ""
    for c in camp_rows:
        name = c.get("campaign_name", "N/A")
        sp = safe_float(c.get("spend"))
        imps = safe_int(c.get("impressions"))
        clk = safe_int(c.get("clicks"))
        ctr = safe_float(c.get("ctr"))
        cpc = safe_float(c.get("cpc"))
        leads, cpl = parse_actions(c)
        prev_c = camp_map.get(name, {})
        p_sp = safe_float(prev_c.get("spend"))
        d_sp = pct(sp, p_sp)
        d_arr = "&#9650;" if d_sp and d_sp > 0 else "&#9660;"
        d_cls = "up" if d_sp and d_sp > 0 else "down"
        delt = f'<span class="delta {d_cls}">{d_arr}</span>' if d_sp else ""
        table_rows += f"""<tr>
<td><span class="camp-name">{name}</span></td>
<td class="num">{fmt_money(sp)} {delt}</td>
<td class="num">{fmt_cpc(cpc)}</td>
<td class="num">{fmt_ctr(ctr)}</td>
<td class="num">{leads}</td>
<td class="num">{fmt_cpc(cpl) if cpl else "—"}</td>
</tr>"""

    # Ads grid
    ads_grid = ""
    for ad in ads[:20]:
        ad_name = ad.get("name", "Anúncio")
        ad_status = ad.get("status", "UNKNOWN")
        creative = ad.get("creative", {}) or {}
        thumb = creative.get("thumbnail_url") or creative.get("image_url") or ""
        insights = ad.get("insights", {}).get("data", [{}])[0] if ad.get("insights", {}).get("data") else {}
        a_spend = safe_float(insights.get("spend"))
        a_cpc = safe_float(insights.get("cpc"))
        a_ctr = safe_float(insights.get("ctr"))
        a_status_class = "active" if ad_status == "ACTIVE" else "paused"
        a_status_label = "Ativo" if ad_status == "ACTIVE" else "Pausado" if ad_status == "PAUSED" else ad_status
        ads_grid += f"""<div class="ad-card {a_status_class}">
<div class="ad-thumb"><img src="{thumb}" alt="" onerror="this.parentElement.innerHTML='<i class=\\'fas fa-ad\\'></i>'"></div>
<div class="ad-info">
<span class="ad-name">{ad_name}</span>
<span class="ad-status {a_status_class}">{a_status_label}</span>
<div class="ad-metrics">
<span>CPC: {fmt_cpc(a_cpc)}</span>
<span>CTR: {fmt_ctr(a_ctr)}</span>
<span>Gasto: {fmt_money(a_spend)}</span>
</div>
</div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Meta Ads — Mirella Imóveis</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Poppins:wght@400;500;600;700;800&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
<style>
:root {{
--mi-orange: #E36100;
--mi-orange-hover: #ff7d26;
--mi-orange-light: rgba(227, 97, 0, 0.1);
--brand-accent: #864df9;
--brand-accent-light: rgba(134, 77, 249, 0.1);
--bg-page: #f7f5f2;
--bg-card: #ffffff;
--bg-code: #f1f3f5;
--text-main: #2d3748;
--text-muted: #718096;
--border-color: rgba(227, 97, 0, 0.15);
--shadow-sm: 0 2px 10px rgba(0, 0, 0, 0.03);
--shadow-md: 0 10px 30px rgba(227, 97, 0, 0.06);
--shadow-lg: 0 15px 35px rgba(0, 0, 0, 0.05);
--tag-bg: #edf2f7;
--scrollbar-bg: #e2e8f0;
--scrollbar-thumb: #cbd5e0;
--green: #22c55e;
--red: #ef4444;
}}
[data-theme="dark"] {{
--bg-page: #0b0e17;
--bg-card: #151a2d;
--bg-code: #1e253f;
--text-main: #e2e8f0;
--text-muted: #a0aec0;
--border-color: rgba(255,255,255,0.07);
--shadow-sm: 0 2px 10px rgba(0,0,0,0.2);
--shadow-md: 0 10px 30px rgba(0,0,0,0.3);
--shadow-lg: 0 15px 35px rgba(0,0,0,0.4);
--tag-bg: #1e253f;
--scrollbar-bg: #151a2d;
--scrollbar-thumb: #2d3748;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
font-family: 'Inter', sans-serif;
background: var(--bg-page);
color: var(--text-main);
overflow-x: hidden;
}}
.orb {{
position: fixed; border-radius: 50%; filter: blur(120px);
opacity: 0.12; pointer-events: none; z-index: -1;
}}
.orb-1 {{ width:600px; height:600px; background:var(--mi-orange); top:-200px; right:-100px; }}
.orb-2 {{ width:500px; height:500px; background:var(--brand-accent); bottom:-100px; left:-100px; }}
::-webkit-scrollbar {{ width:8px; height:8px; }}
::-webkit-scrollbar-track {{ background:var(--scrollbar-bg); }}
::-webkit-scrollbar-thumb {{ background:var(--scrollbar-thumb); border-radius:4px; }}
::-webkit-scrollbar-thumb:hover {{ background:var(--mi-orange); }}

.topbar {{
display: flex; align-items: center; justify-content: space-between;
padding: 20px 30px; border-bottom: 1px solid var(--border-color);
background: var(--bg-card); flex-wrap: wrap; gap: 15px;
}}
.topbar-left {{ display: flex; align-items: center; gap: 15px; }}
.topbar-left img {{ height: 32px; }}
.topbar-left .badge {{
background: var(--mi-orange); color: #fff; padding: 4px 12px;
border-radius: 20px; font-size: 11px; font-weight: 700; font-family: Poppins;
}}
.topbar-left .update-info {{ font-size: 12px; color: var(--text-muted); }}
.topbar-right {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
.period-btn {{
padding: 7px 16px; border-radius: 8px; border: 1px solid var(--border-color);
background: var(--bg-card); color: var(--text-main); font-size: 13px;
font-weight: 600; cursor: pointer; font-family: Inter; transition: all 0.2s;
}}
.period-btn:hover {{ border-color: var(--mi-orange); color: var(--mi-orange); }}
.period-btn.active {{ background: var(--mi-orange); color: #fff; border-color: var(--mi-orange); }}
.theme-btn {{
width: 38px; height: 38px; border-radius: 50%; border: 1px solid var(--border-color);
background: var(--bg-card); color: var(--text-main); cursor: pointer;
display: flex; align-items: center; justify-content: center; transition: all 0.2s;
font-size: 16px;
}}
.theme-btn:hover {{ background: var(--mi-orange); color: #fff; }}

.content {{ padding: 25px 30px; max-width: 1400px; margin: 0 auto; }}
.filter-bar {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; align-items: center; }}
.filter-bar label {{ font-size: 13px; font-weight: 600; color: var(--text-muted); }}
.filter-select {{
padding: 7px 12px; border-radius: 8px; border: 1px solid var(--border-color);
background: var(--bg-card); color: var(--text-main); font-size: 13px; font-family: Inter;
min-width: 200px;
}}
#datepicker {{ display: none; }}

.cards-grid {{
display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
gap: 15px; margin-bottom: 30px;
}}
.card-stat {{
background: var(--bg-card); border: 1px solid var(--border-color);
border-radius: 16px; padding: 20px; box-shadow: var(--shadow-md);
position: relative; overflow: hidden;
}}
.card-stat::before {{
content: ''; position: absolute; top: 0; left: 0; height: 4px;
width: 100%; background: linear-gradient(90deg, var(--mi-orange), var(--brand-accent));
}}
.card-stat .icon {{
width: 40px; height: 40px; border-radius: 10px;
background: var(--mi-orange-light); color: var(--mi-orange);
display: flex; align-items: center; justify-content: center;
font-size: 18px; margin-bottom: 12px;
}}
.card-stat:nth-child(even) .icon {{ background: var(--brand-accent-light); color: var(--brand-accent); }}
.card-stat .label {{ font-size: 11px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
.card-stat .value {{
font-family: 'Outfit', sans-serif; font-size: 24px; font-weight: 800;
color: var(--text-main); margin: 4px 0;
}}
.card-stat .footer {{ display: flex; align-items: center; gap: 8px; font-size: 12px; }}
.delta {{ font-weight: 700; font-size: 12px; }}
.delta.up {{ color: var(--green); }}
.delta.down {{ color: var(--red); }}
.delta.neutral {{ color: var(--text-muted); }}

.chart-card {{
background: var(--bg-card); border: 1px solid var(--border-color);
border-radius: 16px; padding: 25px; box-shadow: var(--shadow-md); margin-bottom: 30px;
}}
.chart-card h3 {{
font-family: 'Outfit', sans-serif; font-size: 18px; margin-bottom: 15px;
display: flex; align-items: center; gap: 8px;
}}
.chart-card h3 i {{ color: var(--mi-orange); }}
.chart-wrapper {{ position: relative; height: 300px; }}

.table-card {{
background: var(--bg-card); border: 1px solid var(--border-color);
border-radius: 16px; padding: 25px; box-shadow: var(--shadow-md); margin-bottom: 30px;
overflow-x: auto;
}}
.table-card h3 {{
font-family: 'Outfit', sans-serif; font-size: 18px; margin-bottom: 15px;
display: flex; align-items: center; gap: 8px;
}}
.table-card h3 i {{ color: var(--brand-accent); }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th {{
text-align: left; padding: 12px 15px; font-weight: 600; font-size: 12px;
color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;
border-bottom: 2px solid var(--border-color); cursor: pointer; user-select: none;
white-space: nowrap;
}}
th:hover {{ color: var(--mi-orange); }}
th i {{ margin-left: 4px; font-size: 10px; }}
td {{ padding: 12px 15px; border-bottom: 1px solid var(--border-color); }}
tr:hover td {{ background: var(--mi-orange-light); }}
.num {{ font-family: 'Outfit', sans-serif; text-align: right; white-space: nowrap; }}
.camp-name {{ font-weight: 600; }}

.creatives-section {{
background: var(--bg-card); border: 1px solid var(--border-color);
border-radius: 16px; padding: 25px; box-shadow: var(--shadow-md); margin-bottom: 30px;
}}
.creatives-section h3 {{
font-family: 'Outfit', sans-serif; font-size: 18px; margin-bottom: 15px;
display: flex; align-items: center; gap: 8px;
}}
.creatives-section h3 i {{ color: var(--mi-orange); }}
.creatives-grid {{
display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
gap: 15px;
}}
.ad-card {{
border: 1px solid var(--border-color); border-radius: 12px;
overflow: hidden; transition: all 0.2s; background: var(--bg-page);
}}
.ad-card:hover {{ transform: translateY(-2px); box-shadow: var(--shadow-md); }}
.ad-card.paused {{ opacity: 0.6; }}
.ad-thumb {{
width: 100%; height: 160px; background: var(--tag-bg);
display: flex; align-items: center; justify-content: center;
overflow: hidden;
}}
.ad-thumb img {{ width: 100%; height: 100%; object-fit: cover; }}
.ad-thumb i {{ font-size: 40px; color: var(--text-muted); }}
.ad-info {{ padding: 12px; }}
.ad-name {{ font-weight: 600; font-size: 13px; display: block; margin-bottom: 4px; }}
.ad-status {{ font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 2px 8px; border-radius: 10px; }}
.ad-status.active {{ background: rgba(34,197,94,0.1); color: var(--green); }}
.ad-status.paused {{ background: var(--tag-bg); color: var(--text-muted); }}
.ad-metrics {{ display: flex; gap: 10px; font-size: 11px; color: var(--text-muted); margin-top: 6px; }}

@media (max-width: 768px) {{
.topbar {{ padding: 15px; }}
.content {{ padding: 15px; }}
.cards-grid {{ grid-template-columns: repeat(2, 1fr); }}
.card-stat .value {{ font-size: 20px; }}
.creatives-grid {{ grid-template-columns: 1fr; }}
.period-btn {{ font-size: 12px; padding: 5px 12px; }}
}}
</style>
</head>
<body data-theme="light">
<div class="orb orb-1"></div>
<div class="orb orb-2"></div>

<div class="topbar">
<div class="topbar-left">
<img src="https://mirellaimoveis.com/wp-content/uploads/2025/09/Camada-0.png" alt="Mirella Imóveis">
<span class="badge">Meta Ads</span>
<span class="update-info">Atualizado em {now_str} &middot; {start_90} a {today}</span>
</div>
<div class="topbar-right">
<button class="period-btn active" data-days="90">90d</button>
<button class="period-btn" data-days="30">30d</button>
<button class="period-btn" data-days="7">7d</button>
<button class="period-btn" data-days="custom">&#128197; Custom</button>
<input type="text" id="datepicker" placeholder="Selecionar datas">
<button class="theme-btn" id="theme-toggle"><i class="fas fa-moon"></i></button>
</div>
</div>

<div class="content">
<div class="filter-bar">
<label for="camp-filter"><i class="fas fa-filter"></i> Campanhas:</label>
<select id="camp-filter" class="filter-select" multiple>
<option value="all" selected>Todas</option>
</select>
<span style="font-size:12px;color:var(--text-muted)">Ctrl+clique para selecionar múltiplas</span>
</div>

<div class="cards-grid" id="cards-container">
<div class="card-stat">
<div class="icon"><i class="fas fa-coins"></i></div>
<div class="label">Gasto</div>
<div class="value">{fmt_money(c_spend)}</div>
<div class="footer">{fmt_delta(delta_spend)} vs período anterior</div>
</div>
<div class="card-stat">
<div class="icon"><i class="fas fa-users"></i></div>
<div class="label">Leads</div>
<div class="value">{c_leads}</div>
<div class="footer">{fmt_delta(delta_leads)} vs período anterior</div>
</div>
<div class="card-stat">
<div class="icon"><i class="fas fa-chart-pie"></i></div>
<div class="label">ROAS</div>
<div class="value">{c_leads/c_spend:.1f}x</div>
<div class="footer">{fmt_delta(delta_roas)} vs período anterior</div>
</div>
<div class="card-stat">
<div class="icon"><i class="fas fa-mouse-pointer"></i></div>
<div class="label">CPC</div>
<div class="value">{fmt_cpc(c_cpc)}</div>
<div class="footer">{fmt_delta(delta_cpc, reverse=True)} vs período anterior</div>
</div>
<div class="card-stat">
<div class="icon"><i class="fas fa-percent"></i></div>
<div class="label">CTR</div>
<div class="value">{fmt_ctr(c_ctr)}</div>
<div class="footer">{fmt_delta(delta_ctr)} vs período anterior</div>
</div>
<div class="card-stat">
<div class="icon"><i class="fas fa-eye"></i></div>
<div class="label">CPM</div>
<div class="value">{fmt_cpc(c_cpm)}</div>
<div class="footer">{fmt_delta(delta_cpm, reverse=True)} vs período anterior</div>
</div>
</div>

<div class="chart-card">
<h3><i class="fas fa-chart-area"></i> Gastos Diários (90 dias)</h3>
<div class="chart-wrapper">
<canvas id="dailyChart"></canvas>
</div>
</div>

<div class="table-card">
<h3><i class="fas fa-table"></i> Campanhas</h3>
<table id="camp-table">
<thead>
<tr>
<th data-col="name">Campanha <i class="fas fa-sort"></i></th>
<th data-col="spend" class="num">Gasto <i class="fas fa-sort"></i></th>
<th data-col="cpc" class="num">CPC <i class="fas fa-sort"></i></th>
<th data-col="ctr" class="num">CTR <i class="fas fa-sort"></i></th>
<th data-col="leads" class="num">Leads <i class="fas fa-sort"></i></th>
<th data-col="cpl" class="num">CPL <i class="fas fa-sort"></i></th>
</tr>
</thead>
<tbody id="camp-tbody">
{table_rows}
</tbody>
</table>
</div>

<div class="creatives-section">
<h3><i class="fas fa-images"></i> Criativos</h3>
<div class="creatives-grid" id="ads-grid">
{ads_grid}
</div>
</div>
</div>

<script>
const dailyData = {{
labels: {daily_labels},
spend: {daily_spend},
impressions: {daily_imps},
clicks: {daily_clicks}
}};

const ctx = document.getElementById('dailyChart').getContext('2d');
const chart = new Chart(ctx, {{
type: 'bar',
data: {{
labels: dailyData.labels.map(d => {{
const parts = d.split('-');
return parts[2] + '/' + parts[1];
}}),
datasets: [
{{
label: 'Gasto (R$)',
data: dailyData.spend,
backgroundColor: 'rgba(227, 97, 0, 0.7)',
borderColor: '#E36100',
borderWidth: 1,
borderRadius: 4,
order: 2,
yAxisID: 'y'
}},
{{
label: 'Impressões',
data: dailyData.impressions,
type: 'line',
borderColor: '#864df9',
backgroundColor: 'rgba(134, 77, 249, 0.1)',
fill: true,
tension: 0.3,
pointRadius: 2,
pointHitRadius: 10,
order: 1,
yAxisID: 'y1'
}}
]
}},
options: {{
responsive: true,
maintainAspectRatio: false,
interaction: {{ intersect: false, mode: 'index' }},
plugins: {{
legend: {{
position: 'top',
labels: {{ usePointStyle: true, padding: 20, font: {{ family: 'Inter', size: 12 }} }}
}},
tooltip: {{
backgroundColor: 'var(--bg-card)',
titleColor: 'var(--text-main)',
bodyColor: 'var(--text-main)',
borderColor: 'var(--border-color)',
borderWidth: 1,
padding: 12,
cornerRadius: 8,
callbacks: {{
label: function(ctx) {{
if (ctx.dataset.label === 'Gasto (R$)') return 'Gasto: R$ ' + ctx.parsed.y.toFixed(2).replace('.', ',');
return ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString('pt-BR');
}}
}}
}}
}},
scales: {{
x: {{
grid: {{ display: false }},
ticks: {{ maxTicksLimit: 15, font: {{ size: 11, family: 'Inter' }} }}
}},
y: {{
type: 'linear',
display: true,
position: 'left',
grid: {{ color: 'var(--border-color)' }},
ticks: {{
font: {{ size: 11, family: 'Inter' }},
callback: function(v) {{ return 'R$' + v.toFixed(0); }}
}},
title: {{ display: true, text: 'Gasto (R$)', font: {{ size: 12, family: 'Inter' }} }}
}},
y1: {{
type: 'linear',
display: true,
position: 'right',
grid: {{ drawOnChartArea: false }},
ticks: {{
font: {{ size: 11, family: 'Inter' }},
callback: function(v) {{ return v >= 1000 ? (v/1000).toFixed(0)+'K' : v; }}
}},
title: {{ display: true, text: 'Impressões', font: {{ size: 12, family: 'Inter' }} }}
}}
}}
}}
}});

// Theme toggle
const themeToggle = document.getElementById('theme-toggle');
const html = document.documentElement;
themeToggle.addEventListener('click', () => {{
const isDark = html.getAttribute('data-theme') === 'dark';
html.setAttribute('data-theme', isDark ? 'light' : 'dark');
themeToggle.innerHTML = isDark ? '<i class=\\"fas fa-moon\\"></i>' : '<i class=\\"fas fa-sun\\"></i>';
}});

// Period tabs
document.querySelectorAll('.period-btn').forEach(btn => {{
btn.addEventListener('click', function() {{
if (this.dataset.days === 'custom') {{
document.getElementById('datepicker').click();
return;
}}
document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
this.classList.add('active');
fetchByPeriod(this.dataset.days);
}});
}});

flatpickr('#datepicker', {{
mode: 'range',
dateFormat: 'd/m/Y',
locale: 'pt',
onClose: function(selectedDates) {{
if (selectedDates.length === 2) {{
document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
document.querySelector('[data-days=\\"custom\\"]').classList.add('active');
fetchByPeriod('custom', selectedDates[0], selectedDates[1]);
}}
}}
}});

function fetchByPeriod(days, start, end) {{
const params = new URLSearchParams();
params.set('period', days);
if (start && end) {{
params.set('start', start.toISOString().split('T')[0]);
params.set('end', end.toISOString().split('T')[0]);
}}
}}
// Nota: refresh real exigiria nova chamada API.
// Por enquanto, o dashboard é estático gerado pelo script.
// Rode python gerar-dashboard.py para atualizar os dados.

// Table sorting
document.querySelectorAll('#camp-table th').forEach(th => {{
th.addEventListener('click', function() {{
const tbody = document.getElementById('camp-tbody');
const rows = Array.from(tbody.querySelectorAll('tr'));
const col = this.dataset.col;
const idx = Array.from(this.parentElement.children).indexOf(this);
const isNum = this.classList.contains('num');
const asc = this.dataset.asc !== 'true';
rows.sort((a, b) => {{
const va = a.children[idx]?.textContent.trim() || '';
const vb = b.children[idx]?.textContent.trim() || '';
if (isNum) {{
const na = parseFloat(va.replace(/[^0-9,.-]/g, '').replace(',', '.')) || 0;
const nb = parseFloat(vb.replace(/[^0-9,.-]/g, '').replace(',', '.')) || 0;
return asc ? na - nb : nb - na;
}}
return asc ? va.localeCompare(vb) : vb.localeCompare(va);
}});
rows.forEach(r => tbody.appendChild(r));
this.dataset.asc = asc;
document.querySelectorAll('#camp-table th').forEach(h => {{
if (h !== this) h.dataset.asc = '';
}});
}});
}});

// Campaign filter
const campFilter = document.getElementById('camp-filter');
campFilter.addEventListener('change', function() {{
const selected = Array.from(this.selectedOptions).map(o => o.value);
const rows = document.querySelectorAll('#camp-tbody tr');
rows.forEach(row => {{
const name = row.querySelector('.camp-name')?.textContent.trim();
if (selected.includes('all') || selected.includes(name)) {{
row.style.display = '';
}} else {{
row.style.display = 'none';
}}
}});
}});
</script>
</body>
</html>"""

    return html

def main():
    # Parse --token argument
    import argparse
    parser = argparse.ArgumentParser(description="Gera dashboard Meta Ads Mirella Imóveis")
    parser.add_argument("--token", help="Token long-lived do Facebook Graph API")
    args = parser.parse_args()
    if args.token:
        save_token(args.token, 5184000)
        print("Token salvo em .meta-token.json")

    try:
        get_token()

        campaigns = fetch_campaigns()
        print(f"  -> {len(campaigns)} campanhas encontradas")

        daily = fetch_daily_insights()
        print(f"  -> {len(daily)} dias de dados")

        today = datetime.date.today()
        start_90 = today - datetime.timedelta(days=90)
        start_180 = today - datetime.timedelta(days=180)

        current = fetch_insights({"since": start_90.isoformat(), "until": today.isoformat()})
        previous = fetch_insights({"since": start_180.isoformat(), "until": (start_90 - datetime.timedelta(days=1)).isoformat()})
        print("  -> Insights consolidados OK")

        ads = fetch_ads()
        print(f"  -> {len(ads)} anúncios encontrados")

        current_data = current[0] if current else {}
        prev_data = previous[0] if previous else {}

        html = generate_html(current_data, prev_data, daily, campaigns, ads)

        out_path = os.path.join(SCRIPT_DIR, "dashboard-meta-mirella.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n✅ Dashboard gerado: {out_path}")
        print(f"📊 {len(campaigns)} campanhas, {len(daily)} dias, {len(ads)} anúncios")
        print(f"💡 Abra index.html no navegador e clique em 'Resultados ADS'")

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
