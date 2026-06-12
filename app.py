# Raj Live OI Dashboard
# Final Formula: DIFFERENCE = PUT OI - CALL OI

import time
import json
import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Raj Live OI Dashboard", layout="wide")

BASE_URL = "https://api.dhan.co/v2"
AUTO_SECONDS = 120
API_GAP_SECONDS = 3.5
LOGIN_FILE = "dhan_login.json"

INDICES = {
    "NIFTY": {"UnderlyingScrip": 13, "UnderlyingSeg": "IDX_I"},
    "BANK NIFTY": {"UnderlyingScrip": 25, "UnderlyingSeg": "IDX_I"},
    "SENSEX": {"UnderlyingScrip": 51, "UnderlyingSeg": "IDX_I"},
}

st.markdown("""
<style>
.block-container {padding-top: 0.45rem; padding-bottom: 0.25rem;}
.title {font-size: 26px; font-weight: 800; margin-bottom: 4px;}
.box {background: #f5f7fa; padding: 5px; border-radius: 8px; margin: 3px 0; font-size: 12px;}
.index-title {font-size: 18px; font-weight: 800; margin-top: 5px; margin-bottom: 2px;}

.wrap {
    width: 100%;
    height: 520px;
    overflow-x: auto;
    overflow-y: auto;
    border: 1px solid #999;
    border-radius: 8px;
    display: block;
    margin-bottom: 8px;
}

table {
    border-collapse: separate;
    border-spacing: 0;
    width: max-content;
    min-width: 100%;
    text-align: center;
    font-size: 11px;
}

th, td {
    border: 1px solid #999;
    padding: 3px 3px;
    min-width: 62px;
    max-width: 74px;
    background: white;
    white-space: nowrap;
}

td {
    font-size: 11px;
    line-height: 1.08;
}

th {
    position: sticky;
    z-index: 5;
    font-weight: 800;
}

.h1 th {
    top: 0;
    background: #e8eef7;
    z-index: 8;
    font-size: 14px;
    height: 30px;
}

.h2 th {
    top: 30px;
    background: #fff5cc;
    z-index: 7;
    font-size: 11px;
    height: 30px;
}

.time {
    position: sticky;
    left: 0;
    background: white;
    z-index: 6;
    font-weight: 700;
    min-width: 64px!important;
    max-width: 68px!important;
}

.htime {
    position: sticky!important;
    left: 0;
    z-index: 20!important;
    min-width: 64px!important;
    max-width: 68px!important;
}

.sep {border-left: 4px solid #111!important;}
.up {background: #d9f7d9!important; font-weight: 700;}
.down {background: #ffd6d6!important; font-weight: 700;}
.same {background: #d9f0ff!important; font-weight: 700;}

.diff-head {background: #fff2b3!important; font-weight: 800;}
.diff-up {background: #006400!important; color: white!important; font-weight: 900;}
.diff-down {background: #8B0000!important; color: white!important; font-weight: 900;}
.diff-same {background: #00008B!important; color: white!important; font-weight: 900;}

.pct {display: block; font-size: 9px; color: inherit; margin-top: 1px;}
.stButton button {height: 34px;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">📊 Raj Live OI Dashboard</div>', unsafe_allow_html=True)

def load_login():
    try:
        if os.path.exists(LOGIN_FILE):
            with open(LOGIN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("client_id", ""), data.get("access_token", "")
    except:
        pass
    return "", ""

def save_login(client_id, access_token):
    with open(LOGIN_FILE, "w", encoding="utf-8") as f:
        json.dump({"client_id": client_id.strip(), "access_token": access_token.strip()}, f)

def clear_login_file():
    try:
        if os.path.exists(LOGIN_FILE):
            os.remove(LOGIN_FILE)
    except:
        pass

if "snapshots" not in st.session_state:
    st.session_state.snapshots = {}
if "last_auto" not in st.session_state:
    st.session_state.last_auto = 0
if "last_api_time" not in st.session_state:
    st.session_state.last_api_time = 0
if "expiry_cache" not in st.session_state:
    st.session_state.expiry_cache = {}
if "login_loaded" not in st.session_state:
    cid, tok = load_login()
    st.session_state.saved_client_id = cid
    st.session_state.saved_access_token = tok
    st.session_state.login_loaded = True
if "saved_client_id" not in st.session_state:
    st.session_state.saved_client_id = ""
if "saved_access_token" not in st.session_state:
    st.session_state.saved_access_token = ""

st.sidebar.header("Dhan Login")

client_id_input = st.sidebar.text_input("Dhan Client ID", value=st.session_state.saved_client_id, type="password")
access_token_input = st.sidebar.text_input("Dhan Access Token", value=st.session_state.saved_access_token, type="password")

if st.sidebar.button("🔐 Login Save", use_container_width=True):
    st.session_state.saved_client_id = client_id_input.strip()
    st.session_state.saved_access_token = access_token_input.strip()
    save_login(st.session_state.saved_client_id, st.session_state.saved_access_token)
    st.sidebar.success("Login laptop में save हो गया।")
    st.rerun()

if st.sidebar.button("🚪 Clear Login", use_container_width=True):
    st.session_state.saved_client_id = ""
    st.session_state.saved_access_token = ""
    st.session_state.expiry_cache = {}
    clear_login_file()
    st.sidebar.success("Login clear हो गया।")
    st.rerun()

client_id = st.session_state.saved_client_id or client_id_input.strip()
access_token = st.session_state.saved_access_token or access_token_input.strip()

st.sidebar.header("Settings")
selected_indices = st.sidebar.multiselect("Index चुनें", list(INDICES.keys()), default=["NIFTY"])
atm_range = st.sidebar.selectbox("ATM ± Range", list(range(1, 11)), index=2)
auto_add = st.sidebar.checkbox("Auto Add Row हर 2 मिनट", value=False)
st.sidebar.caption("Formula: DIFFERENCE = PUT OI - CALL OI")

def headers():
    return {
        "Content-Type": "application/json",
        "access-token": access_token.strip(),
        "client-id": client_id.strip(),
    }

def safe_wait():
    now = time.time()
    gap = now - st.session_state.last_api_time
    if gap < API_GAP_SECONDS:
        time.sleep(API_GAP_SECONDS - gap)

def post_api(path, payload):
    safe_wait()
    r = requests.post(BASE_URL + path, headers=headers(), json=payload, timeout=20)
    st.session_state.last_api_time = time.time()
    if r.status_code == 429:
        raise Exception("HTTP 429: Dhan API limit लगी है। 2-3 मिनट बाद फिर कोशिश करें।")
    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}: {r.text[:500]}")
    return r.json()

def fmt(v):
    try:
        n = float(v)
        sign = "-" if n < 0 else ""
        n_abs = abs(n)

        if n_abs >= 10000000:
            val = n_abs / 10000000
            txt = f"{val:.2f}".rstrip("0").rstrip(".")
            return f"{sign}{txt} Cr"

        if n_abs >= 100000:
            val = n_abs / 100000
            txt = f"{val:.2f}".rstrip("0").rstrip(".")
            return f"{sign}{txt} L"

        return f"{sign}{int(n_abs):,}"
    except:
        return "0"

def pct(now, old):
    if old is None or old == 0:
        return ""
    p = ((now - old) / abs(old)) * 100
    sign = "+" if p > 0 else ""
    return f"<span class='pct'>{sign}{p:.2f}%</span>"

def cls(now, old):
    if old is None:
        return ""
    if now > old:
        return "up"
    if now < old:
        return "down"
    return "same"

def diff_change_cls(now, old):
    if old is None:
        return "diff-same"
    if now > old:
        return "diff-up"
    if now < old:
        return "diff-down"
    return "diff-same"

def ist_time():
    return datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S")

def get_expiry(index_name):
    if index_name in st.session_state.expiry_cache:
        return st.session_state.expiry_cache[index_name]
    cfg = INDICES[index_name]
    data = post_api("/optionchain/expirylist", cfg)
    expiries = data.get("data", [])
    if not expiries:
        raise Exception("Expiry list खाली आई।")
    nearest_expiry = expiries[0]
    st.session_state.expiry_cache[index_name] = nearest_expiry
    return nearest_expiry

def get_chain(index_name, expiry):
    cfg = INDICES[index_name]
    payload = {
        "UnderlyingScrip": cfg["UnderlyingScrip"],
        "UnderlyingSeg": cfg["UnderlyingSeg"],
        "Expiry": expiry,
    }
    return post_api("/optionchain", payload)

def parse_chain(raw):
    data = raw.get("data", {})
    spot = data.get("last_price")
    oc = data.get("oc", {})
    rows = []
    for strike_key, val in oc.items():
        try:
            strike = float(strike_key)
        except:
            continue
        ce = val.get("ce", {}) or {}
        pe = val.get("pe", {}) or {}
        call_oi = int(ce.get("oi", 0) or 0)
        put_oi = int(pe.get("oi", 0) or 0)
        rows.append({"strike": strike, "call": call_oi, "put": put_oi, "diff": put_oi - call_oi})
    df = pd.DataFrame(rows)
    if df.empty:
        raise Exception("Option chain data खाली आया।")
    return df.sort_values("strike").reset_index(drop=True), spot

def atm_strike(df, spot):
    strikes = df["strike"].tolist()
    try:
        spot = float(spot)
        return min(strikes, key=lambda x: abs(x - spot))
    except:
        return strikes[len(strikes) // 2]

def filter_range(df, atm):
    strikes = sorted(df["strike"].unique().tolist())
    atm = min(strikes, key=lambda x: abs(x - atm))
    i = strikes.index(atm)
    selected = strikes[max(0, i - atm_range): i + atm_range + 1]
    return df[df["strike"].isin(selected)].copy()

def make_snapshot(index_name):
    expiry = get_expiry(index_name)
    raw = get_chain(index_name, expiry)
    df, spot = parse_chain(raw)
    atm = atm_strike(df, spot)
    df = filter_range(df, atm)
    snap = {"time": ist_time(), "expiry": expiry, "spot": spot, "atm": atm, "strikes": {}}
    for _, r in df.iterrows():
        strike = int(r["strike"])
        snap["strikes"][strike] = {
            "call": int(r["call"]),
            "put": int(r["put"]),
            "diff": int(r["diff"]),
        }
    return snap

def add_rows(source="manual"):
    errors = []
    for index_name in selected_indices:
        try:
            snap = make_snapshot(index_name)
            st.session_state.snapshots.setdefault(index_name, []).append(snap)
        except Exception as e:
            errors.append(f"{index_name}: {e}")
    if errors:
        st.error("Error:")
        st.code("\\n".join(errors))
    else:
        st.success("Auto row add हो गई।" if source == "auto" else "New row add हो गई।")

def render(index_name):
    data = st.session_state.snapshots.get(index_name, [])
    if not data:
        st.info(f"{index_name}: अभी data नहीं है। Add New Row दबाइए।")
        return

    latest = data[-1]
    strikes = list(latest["strikes"].keys())

    st.markdown(f"<div class='index-title'>{index_name}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='box'><b>{index_name}</b> | Expiry: <b>{latest['expiry']}</b> | "
        f"Spot: <b>{latest['spot']}</b> | ATM: <b>{int(latest['atm'])}</b> | "
        f"Difference: <b>PUT - CALL</b></div>",
        unsafe_allow_html=True
    )

    html = "<div class='wrap'><table>"
    html += "<tr class='h1'><th class='htime'>Time</th>"
    for s in strikes:
        html += f"<th colspan='3' class='sep'>Strike {s}</th>"
    html += "</tr>"

    html += "<tr class='h2'><th class='htime'></th>"
    for _ in strikes:
        html += "<th class='sep'>CALL OI</th><th>PUT OI</th><th class='diff-head'>DIFFERENCE<br><small>PUT-CALL</small></th>"
    html += "</tr>"

    for i in range(len(data) - 1, -1, -1):
        snap = data[i]
        prev = data[i - 1] if i > 0 else None
        html += f"<tr><td class='time'>{snap['time']}</td>"

        for s in strikes:
            nowv = snap["strikes"].get(s, {"call": 0, "put": 0, "diff": 0})
            oldv = prev["strikes"].get(s) if prev else None

            old_call = oldv["call"] if oldv else None
            old_put = oldv["put"] if oldv else None
            old_diff = oldv["diff"] if oldv else None

            html += f"<td class='sep {cls(nowv['call'], old_call)}'>{fmt(nowv['call'])}{pct(nowv['call'], old_call)}</td>"
            html += f"<td class='{cls(nowv['put'], old_put)}'>{fmt(nowv['put'])}{pct(nowv['put'], old_put)}</td>"
            html += f"<td class='{diff_change_cls(nowv['diff'], old_diff)}'>{fmt(nowv['diff'])}{pct(nowv['diff'], old_diff)}</td>"

        html += "</tr>"

    html += "</table></div>"
    st.markdown(html, unsafe_allow_html=True)

if not client_id.strip() or not access_token.strip():
    st.warning("पहले Dhan Client ID और Access Token डालिए।")
    st.stop()

if not selected_indices:
    st.warning("कम से कम 1 index चुनिए।")
    st.stop()

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    if st.button("➕ Add New Row", use_container_width=True):
        add_rows("manual")
with c2:
    if st.button("🧹 Clear Data", use_container_width=True):
        st.session_state.snapshots = {}
        st.success("Data clear हो गया।")
with c3:
    st.caption("Auto ON करने पर हर 2 मिनट में row add होगी।")

if auto_add:
    now = time.time()
    if now - st.session_state.last_auto >= AUTO_SECONDS:
        st.session_state.last_auto = now
        add_rows("auto")
    st.markdown(f"<meta http-equiv='refresh' content='{AUTO_SECONDS}'>", unsafe_allow_html=True)

for idx in selected_indices:
    render(idx)
