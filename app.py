import os, time, hmac, hashlib, urllib.parse as up
import numpy as np
import pandas as pd
import requests, streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh



# ---------------------------------------------------------------------------
# 1. Configurações básicas
# ---------------------------------------------------------------------------
load_dotenv()
API_KEY    = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
SUB_UID    = os.getenv("SUBACCOUNT_ID", "")
BASE_URL   = os.getenv("BASE_URL", "https://api.bybit.com")
RECV_WIN   = "5000"
REFRESH_MS = 28000  # 28 segundos em milissegundos

st.set_page_config(page_title="Trades abertas - Vault", layout="wide")

# Configurar atualização automática a cada 28 segundos
st_autorefresh(interval=28000, key="refresh", limit=None)

# Centralizar o título
st.markdown(
    """
    <div style="text-align: center; margin-bottom: 1px; margin-top: -20px;">
        <h1 style="font-size: 3.2em; font-weight: bold; color: white;">Subaccount Vault </h1>
    </div>
    """,
    unsafe_allow_html=True
)


# --- Estilo da tabela ------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Evitar efeitos visuais durante atualização */
    .stApp {
        transition: none !important;
    }
    
    .stDataFrame {
        transition: none !important;
    }
    
    /* Reduzir espaçamento da página */
    .main .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }
    
    /* Reduzir margem do título */
    .stMarkdown {
        margin-bottom: 0.5rem !important;
    }
    
    /* Estilo para retângulos de totais */
    .total-box {
        background: linear-gradient(135deg, #2c3e50, #34495e);
        border: 2px solid #3498db;
        border-radius: 10px;
        padding: 10px 6px;
        margin: 10px 2px;
        text-align: center;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        color: white;
        font-weight: bold;
        min-width: 130px;
    }
    
    .total-label {
        font-size: 14px;
        color: #bdc3c7;
        margin-bottom: 5px;
    }
    
    .total-value {
        font-size: 20px;
        color: #ecf0f1;
    }
    
    .total-profit {
        color: #16c172 !important;
    }
    
    .total-loss {
        color: #e05d5d !important;
    }

    /* Tabela HTML customizada */
    table {
        width: 70%;
        border-collapse: collapse;
        font-size: 15px;
        background-color: transparent;
        transition: none !important;
    }
    
    th {
        border: 1px solid #ddd;
        padding: 6px 4px;
        text-align: left;
        background-color: #f2f2f2;
        font-size: 20px;
        font-weight: bold;
        color: #333;
        position: sticky;
        top: 0;
        z-index: 10;
        transition: none !important;
    }
    
    td {
        border: 1px solid #ddd;
        padding: 4px;
        background-color: transparent;
        transition: none !important;
    }
    
    /* Cores para lucro/prejuízo */
    .profit { color: #16c172 !important; }
    .loss { color: #e05d5d !important; }
    
    /* Tamanho da fonte para dataframes normais */
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
    ts  = str(int(time.time() * 1000))
    qs  = up.urlencode(params, doseq=True)
    sig = _sign(ts + API_KEY + RECV_WIN + qs)
    hdrs = {
        "X-BAPI-API-KEY":     API_KEY,
        "X-BAPI-TIMESTAMP":   ts,
        "X-BAPI-RECV-WINDOW": RECV_WIN,
        "X-BAPI-SIGN":        sig,
    }
    if SUB_UID:
        hdrs["X-BAPI-SUB-UID"] = SUB_UID
    url = f"{BASE_URL}{path}?{qs}"
    r   = requests.get(url, headers=hdrs, timeout=10)
    r.raise_for_status()
    return r.json()

def get_account_balance(category: str = "linear") -> float:
    """Buscar saldo total da conta"""
    try:
        raw = bybit_get("/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": "USDT"})
        
        if show_json:
            with st.expander("Account Balance JSON"):
                st.json(raw)
        
        result = raw.get("result", {})
        list_data = result.get("list", [])
        
        if list_data:
            # Pegar o primeiro item (conta principal)
            account = list_data[0]
            total_wallet_balance = account.get("totalWalletBalance", "0")
            return float(total_wallet_balance)
        
        return 0.0
        
    except Exception as e:
        if show_json:
            with st.expander("Erro Account Balance"):
                st.write(str(e))
        return 0.0

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

    # ---- Buscar ordens ativas para TP/SL parciais ---------------------------
    try:
        orders_raw = bybit_get("/v5/order/realtime", {"category": category, "symbol": symbol})
        if show_json:
            with st.expander(f"Orders JSON – {category}/{symbol}"):
                st.json(orders_raw)
        
        orders_data = orders_raw.get("result", {}).get("list", [])
        if orders_data:
            orders_df = pd.DataFrame(orders_data)
            
            # Para cada posição, buscar ordens e pegar triggerPrice/tpLimitPrice
            for idx, row in df.iterrows():
                side = row.get("side", "")
                
                # Buscar TODAS as ordens que tenham triggerPrice ou tpLimitPrice
                for _, order in orders_df.iterrows():
                    trigger_price = order.get("triggerPrice", "")
                    tp_limit_price = order.get("tpLimitPrice", "")
                    
                    # Se encontrou valores válidos, usar
                    if trigger_price != "" and trigger_price != "0":
                        df.loc[idx, "triggerPrice"] = trigger_price
                    if tp_limit_price != "" and tp_limit_price != "0":
                        df.loc[idx, "tpLimitPrice"] = tp_limit_price
                    
                    # Se encontrou ambos, parar de procurar
                    if trigger_price != "" and tp_limit_price != "":
                        break
                    
    except Exception as e:
        if show_json:
            with st.expander(f"Erro Orders – {category}/{symbol}"):
                st.write(str(e))

    # ---- Normalização -------------------------------------------------------
    rename = {
        "symbol": "Symbol",
        "side": "Side",
        "size": "Qty", "qty": "Qty",
        "entryPrice": "Entry",            # manter campo original
        "markPrice": "Mark",
        "unRealisedPnl": "uPnl", "unrealisedPnl": "uPnl",
        "leverage": "Lev",
        "takeProfit": "TP",
        "stopLoss":  "SL",
        "triggerPrice": "TriggerPrice",
        "tpLimitPrice": "TpLimitPrice",
    }
    df.rename(columns=rename, inplace=True)

    # Se avgPrice existir, criar Entry Price
    if "avgPrice" in df.columns:
        df["Entry Price"] = pd.to_numeric(df["avgPrice"], errors="coerce")
    else:
        df["Entry Price"] = np.nan  # coluna vazia se não houver

    # Numéricos
    num_cols = {"Qty", "Entry", "Mark", "uPnl", "Lev",
                "positionValue", "TP", "SL", "Entry Price", "TriggerPrice", "TpLimitPrice"}
    for c in num_cols & set(df.columns):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Apenas posições abertas
    df = df[df["Qty"].abs() > 0]
    if df.empty:
        return df

    # Investido
    if {"positionValue", "Lev"} <= set(df.columns):
        df["Investido (USDT)"] = (
            df["positionValue"] / df["Lev"].replace(0, np.nan)
        ).round(2)
    else:
        df["Investido (USDT)"] = (df["Entry"] * df["Qty"]).round(2)

    # uPnl valor + %
    df["uPnlPct"] = np.where(
        df["Investido (USDT)"] != 0,
        (df["uPnl"] / df["Investido (USDT)"] * 100).round(2),
        np.nan,
    )
    def fmt_money(v): return f"${v:,.2f}"
    df["uPnl"] = df.apply(
        lambda r: f"{fmt_money(r['uPnl'])} ({r['uPnlPct']:.2f} %)" if pd.notna(r["uPnl"]) else "",
        axis=1,
    )

    # Criar coluna TP/SL normais (takeProfit/stopLoss da posição)
    def fmt_tpsl_normal(row):
        tp = row.get("TP", "")
        sl = row.get("SL", "")
        
        tp_str = f"{float(tp):.4f}" if tp != "" and tp != "0" and not pd.isna(tp) else "--"
        sl_str = f"{float(sl):.4f}" if sl != "" and sl != "0" and not pd.isna(sl) else "--"
        
        return f"{tp_str}/{sl_str}"

    df["TP/SL"] = df.apply(fmt_tpsl_normal, axis=1)

    # Criar coluna Partial Position TP/SL (TriggerPrice como TP / TpLimitPrice como SL)
    def fmt_tpsl_partial(row):
        trigger = row.get("TriggerPrice", "")
        tp_limit = row.get("TpLimitPrice", "")
        
        # Converter para float se for string
        try:
            trigger_val = float(trigger) if trigger != "" else 0
            tp_limit_val = float(tp_limit) if tp_limit != "" else 0
        except (ValueError, TypeError):
            trigger_val = 0
            tp_limit_val = 0
        
        # Formatar os valores
        tp_str = f"{trigger_val:.2f}" if trigger_val != 0 else "--"
        sl_str = f"{tp_limit_val:.2f}" if tp_limit_val != 0 else "--"
        
        # Criar HTML com cores específicas
        if tp_str != "--" and sl_str != "--":
            return f'<span style="color:#16c172;">{tp_str}</span>/<span style="color:#e05d5d;">{sl_str}</span>'
        elif tp_str != "--":
            return f'<span style="color:#16c172;">{tp_str}</span>/--'
        elif sl_str != "--":
            return f'--/<span style="color:#e05d5d;">{sl_str}</span>'
        else:
            return "--/--"

    df["Partial Position TP/SL"] = df.apply(fmt_tpsl_partial, axis=1)

    # Garantir que as colunas existam mesmo se não houver dados
    if "TP/SL" not in df.columns:
        df["TP/SL"] = "--/--"
    if "Partial Position TP/SL" not in df.columns:
        df["Partial Position TP/SL"] = "--/--"

    # Criar coluna Contracts (Symbol + Side + Leverage)
    def fmt_contracts(row):
        symbol = str(row["Symbol"])
        side = str(row["Side"]).capitalize()
        lev = row.get("Lev", np.nan)
        if pd.notna(lev) and lev != 0:
            lev_str = f"{int(lev)}x" if float(lev).is_integer() else f"{lev}x"
            return f"{symbol} ({side} {lev_str})"
        return f"{symbol} ({side})"
    
    df["Contracts"] = df.apply(fmt_contracts, axis=1)
    df.drop(columns=["Symbol", "Side", "Lev", "avgPrice"], inplace=True, errors="ignore")

    # Remover TP/SL se estiverem vazios
    for col in ["TP", "SL"]:
        if col in df.columns:
            # Se todos os valores são vazios ou NaN, remover a coluna
            if df[col].isna().all() or (df[col] == "").all() or (df[col] == 0).all():
                df.drop(columns=[col], inplace=True)

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
SYMS      = SYMBOLS_TO_CHECK + user_syms

df = fetch_all_open_positions(SYMS, category=cat)
if df.empty:
    st.warning("🚨 Nenhuma posição aberta na subconta.")
    st.stop()

# Ordenar usando a coluna Contracts (que contém o símbolo)
df["Contracts"] = pd.Categorical(df["Contracts"], categories=[f"{s} (Buy 2x)" for s in SYMS] + [f"{s} (Sell 2x)" for s in SYMS], ordered=True)
df.sort_values("Contracts", inplace=True, ignore_index=True)

# Renomear Mark -> Market Price
df.rename(columns={"Mark": "Market Price", "Entry": "Preço de Compra"}, inplace=True)

# Remover TP/SL vazios
for col in ["TP", "SL"]:
    if col in df.columns and df[col].notna().sum() == 0:
        df.drop(columns=[col], inplace=True)

# Ordem final
order = ["Contracts","Investido (USDT)","Entry Price","Preço de Compra",
         "Market Price","uPnl","TP/SL","Partial Position TP/SL"]
cols  = [c for c in order if c in df.columns]

# Garantir que as colunas apareçam na tabela
for col in ["TP/SL", "Partial Position TP/SL"]:
    if col not in cols:
        cols.append(col)

# Formatos
fmt = {
    "Investido (USDT)": "${:,.2f}",
    "Entry Price"     : "${:,.4f}",
    "Preço de Compra" : "${:,.4f}",
    "Market Price"    : "${:,.4f}",
}
for k in fmt:
    if k in df.columns:
        df[k] = pd.to_numeric(df[k], errors="coerce")

# Coloração de lucro/prejuízo e TP/SL
def _clr(val: str):
    if not isinstance(val, str) or val.strip() == "": return ""
    return "color:#e05d5d;" if "-" in val else "color:#16c172;"

def _clr_tpsl_normal(val: str):
    if not isinstance(val, str) or val.strip() == "" or val == "--/--": return ""
    parts = val.split("/")
    if len(parts) == 2:
        tp, sl = parts
        if tp != "--" and sl != "--":
            return "color:#16c172;"  # Verde para TP
        elif tp != "--":
            return "color:#16c172;"  # Verde para TP
        elif sl != "--":
            return "color:#e05d5d;"  # Vermelho para SL
    return ""





styled = (
    df[cols]
    .style
    .applymap(_clr, subset=["uPnl"] if "uPnl" in df.columns else [])
    .applymap(_clr_tpsl_normal, subset=["TP/SL"] if "TP/SL" in df.columns else [])
    .format(fmt, na_rep="-")
)

row_h, head_h = 60, 60

# Buscar saldo da conta
account_balance = get_account_balance(cat)

# Calcular totais
total_investido = df["Investido (USDT)"].sum() if "Investido (USDT)" in df.columns else 0

# Calcular uPnl total (extrair apenas o valor numérico)
if "uPnl" in df.columns:
    # Extrair valores numéricos do formato "$X,XXX.XX (XX.XX%)"
    upnl_values = []
    for val in df["uPnl"]:
        if isinstance(val, str) and "$" in val:
            # Extrair o valor antes do parêntese
            try:
                numeric_val = val.split("(")[0].replace("$", "").replace(",", "").strip()
                upnl_values.append(float(numeric_val))
            except:
                upnl_values.append(0)
        else:
            upnl_values.append(0)
    total_upnl = sum(upnl_values)
else:
    total_upnl = 0

# Calcular saldo total (conta + uPnl)
total_balance = account_balance + total_upnl

# Calcular saldo livre (conta - investido)
total_livre = account_balance - total_investido

# Criar seção de totais
st.markdown(
    f"""
    <div style="display: flex; justify-content: center; margin-bottom: 20px;">
        <div class="total-box">
            <div class="total-label">Saldo Total</div>
            <div class="total-value">${total_balance:,.2f}</div>
        </div>
        <div class="total-box">
            <div class="total-label">Total Investido</div>
            <div class="total-value">${total_investido:,.2f}</div>
        </div>
        <div class="total-box">
            <div class="total-label">Total Livre</div>
            <div class="total-value">${total_livre:,.2f}</div>
        </div>
        <div class="total-box">
            <div class="total-label">Total uPnl</div>
            <div class="total-value {'total-profit' if total_upnl >= 0 else 'total-loss'}">${total_upnl:,.2f}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Criar tabela HTML customizada
if "Partial Position TP/SL" in df.columns:
    # Criar cabeçalho da tabela
    html_table = "<table style='width:100%; border-collapse: collapse; font-size: 18px;'>"
    html_table += "<thead><tr>"
    for col in cols:
        html_table += f"<th style='border: 1px solid #ddd; padding: 8px; text-align: left; background-color: #f2f2f2;'>{col}</th>"
    html_table += "</tr></thead><tbody>"
    
    # Criar linhas da tabela
    for _, row in df.iterrows():
        html_table += "<tr>"
        for col in cols:
            cell_value = row[col]
            if col == "Partial Position TP/SL":
                # Manter o HTML original
                html_table += f"<td style='border: 1px solid #ddd; padding: 8px;'>{cell_value}</td>"
            elif col == "uPnl":
                # Aplicar cores para uPnl
                if col in fmt:
                    try:
                        cell_value = fmt[col].format(float(cell_value)) if pd.notna(cell_value) else "-"
                    except:
                        cell_value = str(cell_value) if pd.notna(cell_value) else "-"
                
                # Aplicar cor baseada no valor
                if isinstance(cell_value, str) and "-" in cell_value:
                    html_table += f"<td style='border: 1px solid #ddd; padding: 8px; color: #e05d5d;'>{cell_value}</td>"
                elif isinstance(cell_value, str) and cell_value.strip() != "":
                    html_table += f"<td style='border: 1px solid #ddd; padding: 8px; color: #16c172;'>{cell_value}</td>"
                else:
                    html_table += f"<td style='border: 1px solid #ddd; padding: 8px;'>{cell_value}</td>"
            else:
                # Aplicar formatação normal
                if col in fmt:
                    try:
                        cell_value = fmt[col].format(float(cell_value)) if pd.notna(cell_value) else "-"
                    except:
                        cell_value = str(cell_value) if pd.notna(cell_value) else "-"
                html_table += f"<td style='border: 1px solid #ddd; padding: 8px;'>{cell_value}</td>"
        html_table += "</tr>"
    
    html_table += "</tbody></table>"
    
    st.markdown(html_table, unsafe_allow_html=True)
else:
    st.dataframe(
        styled,
        hide_index=True,
        use_container_width=True,
        height=head_h + row_h * len(df),
    )
