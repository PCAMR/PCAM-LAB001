"""Sondeo de fuentes de precios: guarda lo que devuelve cada fuente para los instrumentos de la cartera.
No calcula ni estima nada: solo registra respuestas crudas filtradas, para compararlas contra Rava."""
import json, urllib.request, datetime, os

ARG = ["AL30D", "AL35D", "AL30", "AL35", "T15E7", "MGCRD", "MGCRO", "YMCJD", "YMCJO", "GGAL"]
USA = ["SPY", "QQQ", "DIA", "XLP", "XLK", "XLF", "XLE", "XLRE", "XLU", "XLY", "XLC", "XLB", "GLD", "SLV"]
UA = {"User-Agent": "Mozilla/5.0 (PCAM-LAB001 sondeo)", "Accept": "application/json,text/csv,*/*"}

def get(url, method="GET", body=None):
    try:
        data = json.dumps(body).encode() if body is not None else None
        h = dict(UA)
        if data: h["Content-Type"] = "application/json"
        r = urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h, method=method), timeout=30)
        raw = r.read().decode("utf-8", "replace")
        try:
            return {"status": r.status, "json": json.loads(raw)}
        except Exception:
            return {"status": r.status, "text": raw[:3000]}
    except Exception as e:
        return {"error": repr(e)[:300]}

def pick(rows, keys, names):
    if not isinstance(rows, list): return rows
    out = []
    for row in rows:
        if not isinstance(row, dict): continue
        sym = str(row.get(keys[0]) or row.get(keys[1]) or "").upper()
        if sym in names: out.append(row)
    return out

res = {"ejecutado_utc": datetime.datetime.utcnow().isoformat(timespec="seconds")}

# 1) dolarapi: oficial, bolsa (MEP), contadoconliqui (CCL)
res["dolarapi"] = get("https://dolarapi.com/v1/dolares")

# 2) argentinadatos: riesgo país
res["argentinadatos_riesgo_pais"] = get("https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo")

# 3) data912: paneles en vivo
d912 = {}
for panel in ["mep", "ccl", "arg_bonds", "arg_notes", "arg_corp", "arg_stocks", "arg_cedears", "usa_stocks"]:
    r = get(f"https://data912.com/live/{panel}")
    if "json" in r and panel not in ("mep", "ccl"):
        names = USA if panel in ("arg_cedears", "usa_stocks") else ARG
        r = {"status": r["status"], "total_filas": len(r["json"]) if isinstance(r["json"], list) else None,
             "ejemplo_campos": list(r["json"][0].keys()) if isinstance(r["json"], list) and r["json"] else None,
             "filtrado": pick(r["json"], ["symbol", "ticker"], names)}
    elif "json" in r:
        r = {"status": r["status"], "muestra": r["json"][:5] if isinstance(r["json"], list) else r["json"]}
    d912[panel] = r
res["data912"] = d912

# 4) Yahoo Finance (ETFs EE.UU.: cierre y rendimiento del año)
yh = {}
for t in USA + ["^MERV"]:
    r = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=ytd&interval=1d")
    if "json" in r:
        try:
            q = r["json"]["chart"]["result"][0]
            closes = q["indicators"]["quote"][0]["close"]
            ts = q["timestamp"]
            yh[t] = {"meta_precio": q["meta"].get("regularMarketPrice"), "primer_cierre": closes[0],
                     "ultimo_cierre": closes[-1], "primera_fecha": ts[0], "ultima_fecha": ts[-1], "n": len(closes)}
        except Exception as e:
            yh[t] = {"error_parse": repr(e)[:200]}
    else:
        yh[t] = r
res["yahoo"] = yh

# 5) Stooq (alternativa para ETFs)
res["stooq_spy"] = get("https://stooq.com/q/l/?s=spy.us&f=sd2t2ohlcv&h&e=csv")

os.makedirs("pruebas/resultados", exist_ok=True)
stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M")
with open(f"pruebas/resultados/sondeo-{stamp}.json", "w") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print("ok", stamp)
