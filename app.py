import os, time, hmac, hashlib, urllib.parse as up
import numpy as np
import pandas as pd
import requests, streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

"""
Bybit v5 – Posições Abertas (Futuros)
-------------------------------------
Campos: Symbol · Side (Lev) · Investido (USDT) · Entry · Mark · uPnl (abs + %) · [TP] · [SL]
"""

# ---------------------------------------------------------------------------
# 1. Configurações básicas
# ---------------------------------------------------------------------------
load_dotenv()
API_KEY    = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
SUB_UID    = os.getenv("SUBACCOUNT_ID", "")
BASE_URL   = os.getenv("BASE_URL", "https://api.bybit.com")
RECV_WIN   = "5000"
REFRESH_MS = 15_000

st.set_page_config(page_title="Posições Abertas – Bybit", layout="wide")
st_autorefresh(interval=REFRESH_MS, key="refresh")
st.title("Posições Abertas – Bybit v5 🟢")

# --- Fonte maior ------------------------------------------------------------
st.markdown(
    """
    <style>
    div[data-testid="stDataFrame"] div[data-testid="styled-table"] td {font-size:18px !important;}
    div[data-testid="stDataFrame"] div[data-testid="styled-table"] th {font-size:20px !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

show_json = st.sidebar.checkbox("Mostrar JSON bruto (debug)")

# --- SIDEBAR ----------------------------------------------------------------
cat = st.sidebar.selectbox(
    "Categoria de mercado",
    ["linear", "inverse", "spot", "option"],
    index=0,
    help="Futuros perp USDT = linear; perp coin-m = inverse.",
)
if cat not in ["linear", "inverse"]:
    st.warning("Disponível apenas para futuros perpétuos (linear/inverse).")
    st.stop()

# ---------------------------------------------------------------------------
# 2. Helpers de API
# ---------------------------------------------------------------------------
def _sign(payload: str) -> str:
    return hmac.new(API_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()

def bybit_get(path: str, params: dict | None = None):
    params = params or {}
    ts = str(int(time.time() * 1000))
    qs = up.urlencode(params, doseq=True)
    sig = _sign(ts + API_KEY + RECV_WIN + qs)
    hdrs = {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-TIMESTAMP": ts,
        "X-BAPI-RECV-WINDOW": RECV_WIN,
        "X-BAPI-SIGN": sig,
    }
    if SUB_UID:
        hdrs["X-BAPI-SUB-UID"] = SUB_UID
    url = f"{BASE_URL}{path}?{qs}"
    r = requests.get(url, headers=hdrs, timeout=10)
    r.raise_for_status()
    return r.json()

# ---------------------------------------------------------------------------
# 3. Posição por símbolo
# ---------------------------------------------------------------------------
def fetch_position_symbol(symbol: str, category: str = "linear") -> pd.DataFrame:
    try:
        raw = bybit_get("/v5/position/list", {"category": category, "symbol": symbol})
    except Exception as e:
        if show_json:
            with st.expander(f"Erro – {category}/{symbol}"):
                st.write(str(e))
        return pd.DataFrame()

    if show_json:
        with st.expander(f"JSON – {category}/{symbol}"):
            st.json(raw)

    rows = raw.get("result", {}).get("list", [])
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # ---- Normalização -------------------------------------------------------
    rename = {
        "symbol": "Symbol",
        "side": "Side",
        "size": "Qty", "qty": "Qty",
        "entryPrice": "Entry", "markPrice": "Mark",
        "unRealisedPnl": "uPnl", "unrealisedPnl": "uPnl",
        "leverage": "Lev", "takeProfit": "TP", "stopLoss": "SL",
    }
    df.rename(columns=rename, inplace=True)

    # Numéricos
    num_cols = {"Qty", "Entry", "Mark", "uPnl", "Lev", "positionValue", "TP", "SL"}
    for c in num_cols & set(df.columns):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Apenas posições abertas
    df = df[df["Qty"].abs() > 0]
    if df.empty:
        return df

    # Investido
    if {"positionValue", "Lev"} <= set(df.columns):
        df["Investido (USDT)"] = (df["positionValue"] / df["Lev"].replace(0, np.nan)).round(2)
    else:
        df["Investido (USDT)"] = (df["Entry"] * df["Qty"]).round(2)

    # uPnl valor + %
    df["uPnlPct"] = np.where(
        df["Investido (USDT)"] != 0,
        (df["uPnl"] / df["Investido (USDT)"] * 100).round(2),
        np.nan,
    )
    def fmt_money(v):
        return f"${v:,.2f}"
    df["uPnl"] = df.apply(
        lambda r: f"{fmt_money(r['uPnl'])} ({r['uPnlPct']:.2f} %)" if pd.notna(r["uPnl"]) else "",
        axis=1,
    )

    # Side + leverage
    def fmt_side(row):
        side = str(row["Side"]).capitalize()
        lev = row.get("Lev", np.nan)
        if pd.notna(lev) and lev != 0:
            lev_str = f"{int(lev)}x" if float(lev).is_integer() else f"{lev}x"
            return f"{side} {lev_str}"
        return side
    df["Side"] = df.apply(fmt_side, axis=1)
    df.drop(columns=["Lev"], inplace=True, errors="ignore")

    return df

# ---------------------------------------------------------------------------
# 4. Agregador
# ---------------------------------------------------------------------------
SYMBOLS_TO_CHECK = [
    "SOLUSDT","JTOUSDT","NEARUSDT","ONDOUSDT","AAVEUSDT","UNIUSDT","PENDLEUSDT","JUPUSDT",
    "LINKUSDT","COOKIEUSDT","TRXUSDT","VIRTUALUSDT","SYRUPUSDT","AEROUSDT","AIXBTUSDT","HYPEUSDT",
    "MORPHOUSDT","HBARUSDT","BTCUSDT","ETHUSDT"
]
def fetch_all_open_positions(symbols: list[str], category: str="linear") -> pd.DataFrame:
    dfs = [fetch_position_symbol(s, category) for s in symbols]
    dfs = [d for d in dfs if not d.empty]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# ---------------------------------------------------------------------------
# 5. Interface
# ---------------------------------------------------------------------------
extra = st.sidebar.text_input("Adicionar símbolos (vírgula)", value="")
user_syms = [s.strip().upper() for s in extra.split(",") if s.strip()]
SYMS = SYMBOLS_TO_CHECK + user_syms

df = fetch_all_open_positions(SYMS, category=cat)
if df.empty:
    st.warning("🚨 Nenhuma posição aberta na subconta.")
    st.stop()

df["Symbol"] = pd.Categorical(df["Symbol"], categories=SYMS, ordered=True)
df.sort_values("Symbol", inplace=True, ignore_index=True)
df.rename(columns={"Entry": "Preço de Compra"}, inplace=True)

# Remove TP/SL vazios
for _c in ["TP", "SL"]:
    if _c in df.columns and df[_c].notna().sum() == 0:
        df.drop(columns=[_c], inplace=True)

# Ordem final
base_order = ["Symbol","Side","Investido (USDT)","Preço de Compra","Mark","uPnl"] \
             + [c for c in ["TP","SL"] if c in df.columns]
cols = [c for c in base_order if c in df.columns]

# Formatos com $
fmt = {
    "Investido (USDT)": "${:,.2f}",
    "Preço de Compra" : "${:,.4f}",
    "Mark"            : "${:,.4f}",
    "TP"              : "${:,.4f}",
    "SL"              : "${:,.4f}",
}
for k in fmt:
    if k in df.columns:
        df[k] = pd.to_numeric(df[k], errors="coerce")

# --- Coloração correta ------------------------------------------------------
def _clr(val: str):
    """Verde se positivo, vermelho se negativo."""
    if not isinstance(val, str) or val.strip() == "":
        return ""
    return "color:#e05d5d;" if "-" in val else "color:#16c172;"

styled = (
    df[cols]
    .style
    .applymap(_clr, subset=["uPnl"] if "uPnl" in df.columns else [])
    .format(fmt, na_rep="-")
)

row_h, head_h = 60, 60
st.dataframe(
    styled,
    hide_index=True,
    use_container_width=True,
    height=head_h + row_h * len(df),
)
