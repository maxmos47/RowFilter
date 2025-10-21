import streamlit as st
import pandas as pd
import requests
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from typing import Dict, Any
import streamlit.components.v1 as components

st.set_page_config(page_title="Patient Dashboard", page_icon="🩺", layout="centered")

# =========================
# CONFIG
# =========================
# Put your deployed Google Apps Script Web App URL in .streamlit/secrets.toml
# [gas]
# webapp_url = "https://script.google.com/macros/s/AKfycb.../exec"
# token = "MY_SHARED_SECRET"     # (optional, only if you set TOKEN in GAS)
GAS_WEBAPP_URL = st.secrets.get("gas", {}).get("webapp_url", "")
TOKEN = st.secrets.get("gas", {}).get("token", "")  # optional shared secret; used to sign timer token

ALLOWED_L = ["Minor", "Delayed", "Immediate", "Decreased"]
SECONDARY_APP_BASE = "https://eprj-mci-secondarytriage.streamlit.app/"

# =========================
# Helpers
# =========================
def get_query_params() -> Dict[str, str]:
    try:
        q = st.query_params
        return {k: v for k, v in q.items()}
    except Exception:
        return {k: v[0] for k, v in st.experimental_get_query_params().items()}


def set_query_params(**kwargs):
    try:
        st.query_params.clear()
        st.query_params.update(kwargs)
    except Exception:
        st.experimental_set_query_params(**kwargs)


def utc_now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


# ---- Token helpers (HMAC-SHA256, URL-safe) ----
# Payload example: {"row": 1, "t0": 1730000000, "origin": 120, "exp": 1730086400}
# Encoded token format: base64url(json).base64url(signature)

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_json(obj: Dict[str, Any]) -> str:
    data = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    return _b64url(data)


def sign_token(payload: Dict[str, Any], secret: str) -> str:
    json_part = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    key = (secret or "dev-only").encode()
    sig = hmac.new(key, json_part, hashlib.sha256).digest()
    return f"{_b64url(json_part)}.{_b64url(sig)}"


# =========================
# GAS calls
# =========================
def gas_get_row(row: int) -> dict:
    params = {"action": "get", "row": str(row)}
    if TOKEN:
        params["token"] = TOKEN
    r = requests.get(GAS_WEBAPP_URL, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def gas_update_L(row: int, value: str) -> dict:
    payload = {"action": "update", "row": str(row), "value": value}
    if TOKEN:
        payload["token"] = TOKEN
    r = requests.post(GAS_WEBAPP_URL, data=payload, timeout=20)
    r.raise_for_status()
    return r.json()


# =========================
# Card UI (mobile-friendly)
# =========================
st.markdown(
    """
<style>
.kv-card{border:1px solid #e5e7eb;padding:12px;border-radius:14px;margin-bottom:10px;box-shadow:0 1px 4px rgba(0,0,0,0.06);background:#fff;}
.kv-label{font-size:0.9rem;color:#6b7280;margin-bottom:2px;}
.kv-value{font-size:1.05rem;font-weight:600;word-break:break-word;}
.countdown{border:1px dashed #94a3b8;padding:12px;border-radius:12px;background:#f8fafc}
.badge{font-size:0.8rem;background:#e2e8f0;border-radius:999px;padding:4px 10px;color:#334155;margin-right:10px}
.digits{font-weight:800;letter-spacing:1px;line-height:1}
.digits.big{font-size:2.8rem}
@media (max-width: 640px){
  .kv-card{padding:12px;}
  .kv-value{font-size:1.06rem;}
  .digits.big{font-size:2.2rem}
}
</style>
""",
    unsafe_allow_html=True,
)


def _pairs_from_row(df_one_row: pd.DataFrame) -> list[tuple[str, str]]:
    s = df_one_row.iloc[0]
    pairs = []
    for col in df_one_row.columns:
        val = s[col]
        if pd.isna(val):
            val = ""
        pairs.append((str(col), str(val)))
    return pairs


def render_kv_grid(df_one_row: pd.DataFrame, title: str = "", cols: int = 2):
    if title:
        st.subheader(title)
    items = _pairs_from_row(df_one_row)
    n = len(items)
    # Render in chunks of `cols`
    for i in range(0, n, cols):
        row_items = items[i : i + cols]
        col_objs = st.columns(len(row_items))
        for c, (label, value) in zip(col_objs, row_items):
            with c:
                st.markdown(
                    f"""
                    <div class=\"kv-card\">
                      <div class=\"kv-label\">{label}</div>
                      <div class=\"kv-value\">{value if value!='' else '-'}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# =========================
# Main UI
# =========================
st.markdown("### 🩺 Patient Information")

if not GAS_WEBAPP_URL:
    st.error(
        """Missing GAS web app URL. Add it to secrets as:

[gas]
webapp_url = "https://script.google.com/macros/s/XXX/exec"
token = "MY_SHARED_SECRET"
"""
    )
    st.stop()


[gas]
webapp_url = \"https://script.google.com/macros/s/XXX/exec\""
    )
    st.stop()

qp = get_query_params()
row_str = qp.get("row", "1")
mode = qp.get("mode", "edit")  # "edit" or "view"

try:
    row = int(row_str)
    if row < 1:
        row = 1
except ValueError:
    row = 1

# Fetch row via GAS
try:
    data = gas_get_row(row=row)
except Exception as e:
    st.error(f"Failed to fetch row via GAS: {e}")
    st.stop()

if data.get("status") != "ok":
    st.error(f"GAS error: {data}")
    st.stop()

# Build DataFrames from GAS response
# Expecting the backend to include A–K (summary view) and A–L (detailed)
# For timer in column Q, the backend may expose one of these keys:
#   - "current_Q" (string/integer seconds)
#   - "timer_seconds" (integer seconds)
#   - an object "A_Q" with key "Q" (string/integer seconds)
# The code below is defensive and supports all three.

df_ak = pd.DataFrame([data.get("A_K", {})])
df_al = pd.DataFrame([data.get("A_L", {})])
A_Q = data.get("A_Q", {}) or {}

max_row = data.get("max_rows", 1)
current_L = data.get("current_L", "")

# --------- TIMER from Column Q (seconds) ---------
raw_q = (
    A_Q.get("Q")
    or data.get("current_Q")
    or data.get("timer_seconds")
)

try:
    timer_from_gsheet = int(str(raw_q).strip()) if raw_q is not None and str(raw_q).strip() != "" else 0
except Exception:
    timer_from_gsheet = 0

# Session-state countdown that continues locally between reruns
ss_key_state = f"row{row}_timer_state"
if ss_key_state not in st.session_state or st.session_state[ss_key_state].get("origin") != timer_from_gsheet:
    st.session_state[ss_key_state] = {
        "origin": timer_from_gsheet,   # seconds as read from sheet
        "t0": utc_now_ts(),           # epoch when we latched the origin
    }

latched = st.session_state[ss_key_state]
elapsed = max(0, utc_now_ts() - int(latched.get("t0", utc_now_ts())))
remaining = max(0, int(latched.get("origin", 0)) - elapsed)
origin_seconds = int(latched.get("origin", 0))

# --------- Visual countdown (client-side JS to avoid server reruns) ---------
# Renders big HH:MM:SS digits + HTML progress bar that updates every second.

def _hms(secs: int) -> str:
    secs = max(0, int(secs))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

initial_digits = _hms(remaining)
progress_value = max(0, origin_seconds - remaining)
progress_max = max(1, origin_seconds if origin_seconds > 0 else 1)

components.html(
    f"""
    <div class=\"countdown\">
      <span class=\"badge\">⏳ Column Q</span>
      <span id=\"digits\" class=\"digits big\">{initial_digits}</span>
      <div style=\"margin-top:10px\">
        <progress id=\"pg\" max=\"{progress_max}\" value=\"{progress_value}\" style=\"width:100%\"></progress>
      </div>
    </div>
    <script>
      (function() {{
        let remaining = {remaining};
        const origin = {origin_seconds};
        const digits = document.getElementById('digits');
        const pg = document.getElementById('pg');
        function fmt(n) {{ return String(n).padStart(2,'0'); }}
        function render() {{
          let s = Math.max(0, Math.floor(remaining));
          let h = Math.floor(s/3600);
          let m = Math.floor((s%3600)/60);
          let ss = s%60;
          digits.textContent = `${{fmt(h)}}:${{fmt(m)}}:${{fmt(ss)}}`;
          if (origin > 0) {{
            pg.max = origin;
            pg.value = Math.min(origin, Math.max(0, origin - s));
          }}
        }}
        render();
        const intv = setInterval(() => {{
          remaining -= 1;
          if (remaining <= 0) {{ remaining = 0; render(); clearInterval(intv); return; }}
          render();
        }}, 1000);
      }})();
    </script>
    """,
    height=140,
)

# Prepare a signed token so the secondary triage app can continue the countdown.
# Token includes latched origin seconds and t0, plus an expiry (24h by default).
exp = utc_now_ts() + 24 * 3600
payload = {"row": row, "origin": int(latched["origin"]), "t0": int(latched["t0"]), "exp": exp}
countdown_token = sign_token(payload, TOKEN)

# Deep-link to the secondary app with the timer token
sec_params = {"row": str(row), "lock": "1", "timer_token": countdown_token}
sec_qs = "&".join([f"{k}={v}" for k, v in sec_params.items()])
secondary_url = f"{SECONDARY_APP_BASE}?{sec_qs}"

with st.expander("⛳ Hand off timer to Secondary triage app", expanded=True):
    st.write("This link carries a signed timer token so the next app can continue the countdown safely.")
    st.link_button("Open Secondary Triage", secondary_url, use_container_width=True)
    st.code(countdown_token, language="text")

# --------- UI based on mode ---------
if mode == "view":
    render_kv_grid(df_al, title="Patient", cols=2)
    st.success("Triage เรียบร้อย")
    if st.button("Edit this row again"):
        set_query_params(row=str(row), mode="edit")
        st.rerun()
else:
    render_kv_grid(df_ak, title="Patient", cols=2)

    idx = ALLOWED_L.index(current_L) if current_L in ALLOWED_L else 0
    with st.form("update_l_form", border=True):
        st.markdown("### Primary triage")
        new_L = st.selectbox(
            "Select a value for triage",
            ALLOWED_L,
            index=idx,
            help="Allowed: Minor, Delayed, Immediate, Decreased",
        )
        submitted = st.form_submit_button("Submit")
        if submitted:
            try:
                res = gas_update_L(row=row, value=new_L)
                if res.get("status") == "ok":
                    set_query_params(row=str(row), mode="view")
                    st.rerun()
                else:
                    st.error(f"Update failed: {res}")
            except Exception as e:
                st.error(f"Failed to update via GAS: {e}")

# =========================
# Notes for the Secondary App (decoder snippet)
# =========================
# In your secondary app, use the following to decode token and compute remaining:
#
# import json, hmac, hashlib, base64, time
# def b64url_decode(s: str) -> bytes:
#     pad = '=' * (-len(s) % 4)
#     return base64.urlsafe_b64decode(s + pad)
# def verify_and_load(token: str, secret: str):
#     json_b64, sig_b64 = token.split('.')
#     data = b64url_decode(json_b64)
#     expected = hmac.new((secret or 'dev-only').encode(), data, hashlib.sha256).digest()
#     if not hmac.compare_digest(expected, b64url_decode(sig_b64)):
#         raise ValueError('bad signature')
#     payload = json.loads(data)
#     if int(payload.get('exp', 0)) < int(time.time()):
#         raise ValueError('token expired')
#     return payload
# # remaining = max(0, payload['origin'] - (now - payload['t0']))
