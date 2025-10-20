
import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Patient Dashboard", page_icon="🩺", layout="centered")

# =========================
# CONFIG
# =========================
# Put your deployed Google Apps Script Web App URL in .streamlit/secrets.toml
# [gas]
# webapp_url = "https://script.google.com/macros/s/AKfycb.../exec"
# token = "MY_SHARED_SECRET"     # (optional, only if you set TOKEN in GAS)
GAS_WEBAPP_URL = st.secrets.get("gas", {}).get("webapp_url", "")
TOKEN = st.secrets.get("gas", {}).get("token", "")  # optional shared secret

ALLOWED_L = ["Minor", "Delayed", "Immediate", "Decreased"]

# =========================
# Helpers for query params
# =========================
def get_query_params():
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
st.markdown("""
<style>
.kv-card{border:1px solid #e5e7eb;padding:12px;border-radius:14px;margin-bottom:10px;box-shadow:0 1px 4px rgba(0,0,0,0.06);background:#fff;}
.kv-label{font-size:0.9rem;color:#6b7280;margin-bottom:2px;}
.kv-value{font-size:1.05rem;font-weight:600;word-break:break-word;}
@media (max-width: 640px){
  .kv-card{padding:12px;}
  .kv-value{font-size:1.06rem;}
}
</style>
""", unsafe_allow_html=True)

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
        row_items = items[i:i+cols]
        col_objs = st.columns(len(row_items))
        for c, (label, value) in zip(col_objs, row_items):
            with c:
                st.markdown(
                    f"""
                    <div class="kv-card">
                      <div class="kv-label">{label}</div>
                      <div class="kv-value">{value if value!='' else '-'}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# =========================
# Main UI
# =========================
st.markdown("### 🩺 Patient Information")

if not GAS_WEBAPP_URL:
    st.error("Missing GAS web app URL. Add it to secrets as:\n\n[gas]\nwebapp_url = \"https://script.google.com/macros/s/XXX/exec\"")
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
df_ak = pd.DataFrame([data.get("A_K", {})])
df_al = pd.DataFrame([data.get("A_L", {})])
max_row = data.get("max_rows", 1)
current_L = data.get("current_L", "")

# --------- UI based on mode ---------
if mode == "view":
    render_kv_grid(df_al, title="Patient", cols=2)
    st.success("Showing refreshed data. Form is hidden in view mode.")
    # Button to get back to edit
    if st.button("Edit this row again"):
        set_query_params(row=str(row), mode="edit")
        st.rerun()
else:
    # Edit mode: show A–K + form
    render_kv_grid(df_ak, title="Selected Row (A–K)", cols=2)

    # Form to update L
    idx = ALLOWED_L.index(current_L) if current_L in ALLOWED_L else 0
    with st.form("update_l_form", border=True):
        st.markdown("Primary triage")
        new_L = st.selectbox("Select a value for column L", ALLOWED_L, index=idx, help="Allowed: Minor, Delayed, Immediate, Decreased")
        submitted = st.form_submit_button("Submit")
        if submitted:
            try:
                res = gas_update_L(row=row, value=new_L)
                if res.get("status") == "ok":
                    # After submit -> view mode (no form) and refreshed A–L
                    set_query_params(row=str(row), mode="view")
                    st.rerun()
                else:
                    st.error(f"Update failed: {res}")
            except Exception as e:
                st.error(f"Failed to update via GAS: {e}")

# Quick row navigation (for convenience)
with st.expander("Quick row navigation", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        new_row = st.number_input("Go to row (1-based, data row under header)", min_value=1, max_value=max(1, max_row), value=row, step=1)
    with col2:
        if st.button("Go"):
            set_query_params(row=str(new_row), mode="edit")
            st.rerun()

# Footer: how URL works
st.markdown("""
<small>
<b>URL:</b> <code>?row=1</code> เลือกแถวข้อมูล (1 = แถวแรกใต้หัวตาราง) •
<code>&mode=view</code> แสดง A–L ไม่มีฟอร์ม •
<code>&mode=edit</code> แสดง A–K + ฟอร์ม<br/>
หลัง Submit จะสวิตช์เป็น <code>mode=view</code> ให้อัตโนมัติ
</small>
""", unsafe_allow_html=True)
