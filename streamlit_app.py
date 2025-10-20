
import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Patient Dashboard (GAS Backend)", page_icon="🩺", layout="centered")

# =========================
# CONFIG
# =========================
# Put your deployed Google Apps Script Web App URL here (the one ending with /exec)
# Example: https://script.google.com/macros/s/AKfycb.../exec
GAS_WEBAPP_URL = st.secrets.get("gas", {}).get("webapp_url", "")

ALLOWED_L = ["Minor", "Delayed", "Immediate", "Decreased"]

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

def gas_get_row(row: int, token: str = "") -> dict:
    params = {"action": "get", "row": str(row)}
    if token:
        params["token"] = token
    r = requests.get(GAS_WEBAPP_URL, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def gas_update_L(row: int, value: str, token: str = "") -> dict:
    payload = {"action": "update", "row": str(row), "value": value}
    if token:
        payload["token"] = token
    r = requests.post(GAS_WEBAPP_URL, data=payload, timeout=20)
    r.raise_for_status()
    return r.json()

st.markdown("### 🩺 Patient Dashboard — GAS Backend")

if not GAS_WEBAPP_URL:
    st.error("Missing GAS web app URL. Add it to secrets as:\n\n[gas]\nwebapp_url = \"https://script.google.com/macros/s/XXX/exec\"")
    st.stop()

qp = get_query_params()
row_str = qp.get("row", "1")
mode = qp.get("mode", "edit")
token = st.secrets.get("gas", {}).get("token", "")  # optional shared secret

try:
    row = int(row_str)
    if row < 1:
        row = 1
except ValueError:
    row = 1

# Fetch row via GAS
try:
    data = gas_get_row(row=row, token=token)
except Exception as e:
    st.error(f"Failed to fetch row via GAS: {e}")
    st.stop()

if data.get("status") != "ok":
    st.error(f"GAS error: {data}")
    st.stop()

df_ak = pd.DataFrame([data.get("A_K", {})])
df_al = pd.DataFrame([data.get("A_L", {})])
max_row = data.get("max_rows", 1)

def show_table(df, caption=""):
    st.dataframe(df, hide_index=True, use_container_width=True)
    if caption:
        st.caption(caption)

if mode == "view":
    st.subheader("Selected Row (A–L)")
    show_table(df_al, caption=f"Data row #{row} (A–L)")
    if st.button("Edit this row again"):
        set_query_params(row=str(row), mode="edit")
        st.rerun()
else:
    st.subheader("Selected Row (A–K)")
    show_table(df_ak, caption=f"Data row #{row} (A–K)")

    current_L = data.get("current_L", "")
    idx = ALLOWED_L.index(current_L) if current_L in ALLOWED_L else 0
    with st.form("update_l_form", border=True):
        st.markdown("#### Update column **L** (Treatment category)")
        new_L = st.selectbox("Select a value for column L", ALLOWED_L, index=idx)
        submitted = st.form_submit_button("Submit")
        if submitted:
            try:
                res = gas_update_L(row=row, value=new_L, token=token)
                if res.get("status") == "ok":
                    set_query_params(row=str(row), mode="view")
                    st.rerun()
                else:
                    st.error(f"Update failed: {res}")
            except Exception as e:
                st.error(f"Failed to update via GAS: {e}")

with st.expander("Quick row navigation", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        new_row = st.number_input("Go to row (1-based, data row under header)", min_value=1, max_value=max_row, value=row, step=1)
    with col2:
        if st.button("Go"):
            set_query_params(row=str(new_row), mode="edit")
            st.rerun()

st.markdown("""
<small>
Use <code>?row=1</code> to pick the data row (1 = first row under header).<br/>
Use <code>&mode=view</code> to show A–L without form, or <code>&mode=edit</code> for A–K + form.
</small>
""", unsafe_allow_html=True)
