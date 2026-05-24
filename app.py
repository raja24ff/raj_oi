import streamlit as st
import streamlit.components.v1 as components
import requests, random, time, os
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DHAN_CLIENT_ID", "").strip()
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "").strip()

st.set_page_config(page_title="Live OI Dashboard", layout="wide")
st.title("Live OI Analysis Dashboard")

INDEX = {
    "NIFTY": {"scrip": 13, "seg": "IDX_I", "step": 50, "atm": 23600},
    "BANK NIFTY": {"scrip": 25, "seg": "IDX_I", "step": 100, "atm": 51000},
    "SENSEX": {"scrip": 51, "seg": "IDX_I", "step": 100, "atm": 77500},
}

st.sidebar.header("Settings")

show_nifty = st.sidebar.checkbox("NIFTY", True)
show_bank = st.sidebar.checkbox("BANK NIFTY", True)
show_sensex = st.sidebar.checkbox("SENSEX", True)

atm_range = st.sidebar.selectbox("ATM Range", list(range(1, 11)), index=2)
demo_mode = st.sidebar.checkbox("Demo Data", False)
auto_refresh = st.sidebar.checkbox("Auto Refresh 2 Minute", False)
show_raw = st.sidebar.checkbox("Show Raw Dhan Response", True)

available = []
if show_nifty:
    available.append("NIFTY")
if show_bank:
    available.append("BANK NIFTY")
if show_sensex:
    available.append("SENSEX")

st.sidebar.subheader("Display Order")

pos1 = st.sidebar.selectbox("1st Position", ["None"] + available, index=1 if len(available) >= 1 else 0)
pos2 = st.sidebar.selectbox("2nd Position", ["None"] + available, index=2 if len(available) >= 2 else 0)
pos3 = st.sidebar.selectbox("3rd Position", ["None"] + available, index=3 if len(available) >= 3 else 0)

selected = []
for x in [pos1, pos2, pos3]:
    if x != "None" and x not in selected:
        selected.append(x)

if st.sidebar.button("Add New Row"):
    st.session_state.add_row = True

if st.sidebar.button("Clear Data"):
    st.session_state.history = {}
    st.session_state.raw_response = {}

if "history" not in st.session_state:
    st.session_state.history = {}

if "raw_response" not in st.session_state:
    st.session_state.raw_response = {}

if "add_row" not in st.session_state:
    st.session_state.add_row = True

def headers():
    return {
        "access-token": ACCESS_TOKEN,
        "client-id": API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def is_weekend():
    return date.today().weekday() in [5, 6]

def color_box(now, prev):
    if prev is None:
        return "#ffffff"
    if now > prev:
        return "#90EE90"
    if now < prev:
        return "#ff7f7f"
    return "#87CEEB"

def get_oi(option_data):
    if not isinstance(option_data, dict):
        return 0

    for key in ["oi", "OI", "open_interest", "openInterest", "openInterestQty"]:
        val = option_data.get(key)
        if val is not None:
            try:
                return int(float(val))
            except:
                return 0

    return 0

def nearest_expiry(index_name):
    cfg = INDEX[index_name]

    url = "https://api.dhan.co/v2/optionchain/expirylist"

    payload = {
        "UnderlyingScrip": cfg["scrip"],
        "UnderlyingSeg": cfg["seg"]
    }

    r = requests.post(url, headers=headers(), json=payload, timeout=15)
    r.raise_for_status()

    data = r.json().get("data", [])

    if isinstance(data, list) and len(data) > 0:
        return data[0]

    raise Exception("Expiry नहीं मिली")

def get_strikes(index_name, atm):
    step = INDEX[index_name]["step"]
    return [int(atm + i * step) for i in range(-atm_range, atm_range + 1)]

def find_strike_data(oc, strike):
    if not isinstance(oc, dict):
        return {}

    possible_keys = [
        str(strike),
        str(float(strike)),
        f"{strike}.0",
        f"{strike}.00",
        f"{strike}.000000"
    ]

    for key in possible_keys:
        if key in oc:
            return oc[key]

    for key, value in oc.items():
        try:
            if int(float(key)) == int(strike):
                return value
        except:
            pass

    return {}

def get_ce_pe(strike_data):
    if not isinstance(strike_data, dict):
        return {}, {}

    ce = (
        strike_data.get("ce")
        or strike_data.get("CE")
        or strike_data.get("call")
        or strike_data.get("CALL")
        or {}
    )

    pe = (
        strike_data.get("pe")
        or strike_data.get("PE")
        or strike_data.get("put")
        or strike_data.get("PUT")
        or {}
    )

    return ce, pe

def demo_row(index_name):
    atm = INDEX[index_name]["atm"]

    row = {
        "TIME": datetime.now().strftime("%H:%M:%S")
    }

    for strike in get_strikes(index_name, atm):
        put = random.randint(10000, 90000)
        call = random.randint(10000, 90000)

        row[f"{strike}_put"] = put
        row[f"{strike}_call"] = call
        row[f"{strike}_dif"] = put - call

    return row

def live_row(index_name):
    cfg = INDEX[index_name]
    expiry = nearest_expiry(index_name)

    url = "https://api.dhan.co/v2/optionchain"

    payload = {
        "UnderlyingScrip": cfg["scrip"],
        "UnderlyingSeg": cfg["seg"],
        "Expiry": expiry
    }

    r = requests.post(url, headers=headers(), json=payload, timeout=15)
    r.raise_for_status()

    raw = r.json()
    st.session_state.raw_response[index_name] = raw

    data = raw.get("data", {})

    oc = data.get("oc", {}) or data.get("option_chain", {}) or data.get("optionChain", {})

    last_price = (
        data.get("last_price")
        or data.get("lastPrice")
        or data.get("underlying_price")
        or data.get("underlyingPrice")
        or cfg["atm"]
    )

    try:
        atm = int(round(float(last_price) / cfg["step"]) * cfg["step"])
    except:
        atm = cfg["atm"]

    INDEX[index_name]["atm"] = atm

    row = {
        "TIME": datetime.now().strftime("%H:%M:%S")
    }

    for strike in get_strikes(index_name, atm):
        strike_data = find_strike_data(oc, strike)
        ce, pe = get_ce_pe(strike_data)

        put = get_oi(pe)
        call = get_oi(ce)

        row[f"{strike}_put"] = put
        row[f"{strike}_call"] = call
        row[f"{strike}_dif"] = put - call

    return row

def add_data(index_name):
    try:
        if demo_mode:
            row = demo_row(index_name)
        else:
            row = live_row(index_name)

    except Exception as e:
        st.error(f"{index_name} error: {e}")
        row = demo_row(index_name)

    if index_name not in st.session_state.history:
        st.session_state.history[index_name] = []

    st.session_state.history[index_name].append(row)

def make_table(index_name):
    history = st.session_state.history.get(index_name, [])

    if not history:
        return "<p>No data</p>"

    latest = history[-1]

    strike_list = sorted([
        int(x.replace("_put", ""))
        for x in latest.keys()
        if x.endswith("_put")
    ])

    html = """
    <style>
    .table-box{
        height:360px;
        overflow-y:scroll;
        overflow-x:auto;
        border:1px solid #cccccc;
    }

    table{
        border-collapse:separate;
        border-spacing:0;
        width:100%;
        font-family:Arial;
        font-size:14px;
        text-align:center;
    }

    th,td{
        border:1px solid #cccccc;
        padding:8px;
        white-space:nowrap;
    }

    th{
        position:sticky;
        z-index:10;
    }

    .top-head{
        top:0;
        background:#dbe8ff;
        font-size:17px;
        font-weight:bold;
    }

    .sub-head{
        top:40px;
        background:#f2f2f2;
        font-weight:bold;
    }

    .time-head{
        top:0;
        background:#f5f5f5;
        z-index:12;
        border-right:4px solid black !important;
    }

    .time{
        background:#f5f5f5;
        font-weight:bold;
        border-right:4px solid black !important;
    }

    .group-end{
        border-right:4px solid black !important;
    }
    </style>

    <div class="table-box">
    <table>
    <tr>
    <th rowspan="2" class="time-head">TIME</th>
    """

    for strike in strike_list:
        html += f"""
        <th colspan="3" class="top-head group-end">
        {strike}
        </th>
        """

    html += "</tr><tr>"

    for strike in strike_list:
        html += """
        <th class="sub-head">PUT OI</th>
        <th class="sub-head">CALL OI</th>
        <th class="sub-head group-end">DIFRENS</th>
        """

    html += "</tr>"

    for i, row in enumerate(history):
        prev = history[i - 1] if i > 0 else None

        html += f"""
        <tr>
        <td class="time">{row['TIME']}</td>
        """

        for strike in strike_list:
            put = row.get(f"{strike}_put", 0)
            call = row.get(f"{strike}_call", 0)
            dif = row.get(f"{strike}_dif", 0)

            prev_put = prev.get(f"{strike}_put") if prev else None
            prev_call = prev.get(f"{strike}_call") if prev else None
            prev_dif = prev.get(f"{strike}_dif") if prev else None

            html += f"""
            <td style="background:{color_box(put, prev_put)}">{put}</td>
            <td style="background:{color_box(call, prev_call)}">{call}</td>
            <td class="group-end" style="background:{color_box(dif, prev_dif)}">{dif}</td>
            """

        html += "</tr>"

    html += "</table></div>"

    return html

if st.session_state.add_row:
    for index_name in selected:
        add_data(index_name)

    st.session_state.add_row = False

for index_name in selected:
    st.subheader(index_name)
    components.html(make_table(index_name), height=430, scrolling=False)

if demo_mode:
    st.warning("Demo Mode ON")
else:
    st.success("Live Dhan API Running")

if show_raw and not demo_mode:
    st.subheader("Raw Dhan Response Debug")
    for key, value in st.session_state.raw_response.items():
        with st.expander(f"{key} Raw Response"):
            st.json(value)

if auto_refresh:
    if not is_weekend():
        time.sleep(120)
        st.session_state.add_row = True
        st.rerun()