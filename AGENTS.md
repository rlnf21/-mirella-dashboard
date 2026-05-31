# Mirella Imóveis — Meta Ads Dashboard

## Goal
Dashboard Meta Ads para Mirella Imóveis com Flask backend, deploy no PythonAnywhere (nunca dorme). Versão nova em `/dashboard/novo` em produção.

## Stack
- **Backend:** Flask + requests (sem banco de dados)
- **Frontend:** HTML + CSS + Chart.js + Flatpickr
- **Deploy:** PythonAnywhere (`rlnf21.pythonanywhere.com`)
- **GitHub:** `https://github.com/rlnf21/-mirella-dashboard`
- **Portal:** `https://portal-mirella.netlify.app` (iframe aponta para `/dashboard/novo`)

## Estrutura
```
├── app.py                     # Flask backend (rotas /dashboard, /dashboard/novo, /api/refresh, /api/health)
├── wsgi.py                    # Entry point PythonAnywhere
├── requirements.txt           # Flask, requests
├── gerar-dashboard.py         # Script fallback (gera HTML estático)
├── templates/
│   ├── dashboard.html         # Dashboard original (com anúncios)
│   └── dashboard-novo.html    # Novo dashboard (sem anúncios, com gênero, idade, posicionamento)
├── index.html                 # Portal com iframe
└── AGENTS.md                  # Este arquivo
```

## Configuração
- **Meta Token:** `os.environ['META_TOKEN']` (long-lived 60 dias)
- **App ID:** `1028593009630321`
- **Business ID:** `2729714934094405` (M. Imóveis)
- **Ad Account:** `act_941166705291997` ([CA01] M. Imóveis)
- **API:** `https://graph.facebook.com/v22.0/`
- **Permissões:** `ads_read`, `ads_management`, `business_management`

## Rotas
| Rota | Descrição |
|------|-----------|
| `/dashboard` | Dashboard original |
| `/dashboard/novo?days=7\|30\|90&since=&until=` | Dashboard novo |
| `/api/refresh` | Limpa cache |`
| `/api/health` | Status do token |

## Cards (7)
Gasto, Leads, Alcance, **Cliques**, CPC, CTR, CPL, CVR

## Gráficos
1. **Diário** — gasto (barras laranja) + alcance (linha roxa) + leads (linha verde)
2. **Gênero** — doughnut (gasto por Female/Male/Unknown)
3. **Idade** — barras empilhadas (feminino laranja / masculino azul)
4. **Posicionamento** — barras horizontais (Feed/Stories/Reels)

## Arquitetura
- **Sem banco de dados:** dados da API Meta embutidos no HTML via Jinja2
- **Cache separado:** campanhas/anúncios (10 min) + insights por período (5 min)
- **Chamadas paralelas:** ThreadPoolExecutor (4 workers)
- **Pré-carregamento:** ao acessar 90d, busca 7d e 30d em background
- **Token via env var:** `.meta-token.json` no `.gitignore`

## Deploy (PythonAnywhere)
```bash
git pull
# Console: Reload web app via Web tab
```

## Keep Alive
GitHub Action `.github/workflows/keep-alive.yml` ping a cada 10 min.

## Observações
- Novo dashboard não tem seção de anúncios
- Tema claro/escuro
- Tooltips com fundo escuro `#1a1a2e`
- Loading overlay com timeout 60s
