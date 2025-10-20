# Streamlit Row-by-Row Dashboard with Lock Mode (FIXED)
# ------------------------------------------------
# Features:
# - View one row at a time from a Google Sheet (CSV export)
# - URL params: ?row=, ?id=&id_col=
# - Locked mode via ?lock=1 => hides sidebar & navigation; shows only the specified row
# - Default dataset = your Google Sheet; override with ?sheet= (disabled in lock mode)
# - Download selected row as JSON/CSV
#
# Examples:
#   - Normal view:             ?row=5
#   - Locked single-row:       ?row=5&lock=1
#   - Locked by key:           ?id=ABC123&id_col=PatientID&lock=1

import io
import json
import math
import re
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import streamlit as st


def get_query_params() -> dict:
    try:
        return dict(st.query_params)
    except Exception:
        return {k: v[0] if isinstance(v, list) else v for k, v in st.experimental_get_query_params().items()}


def set_query_params(**params):
    try:
        st.query_params.clear()
        for k, v in params.items():
            if v is None:
                continue
            st.query_params[k] = str(v)
    except Exception:
        st.experimental_set_query_params(**{k: v for k, v in params.items() if v is not None})


def looks_like_image_url(x: str) -> bool:
    if not isinstance(x, str):
        return False
    return bool(re.search(r"\.(png|jpg|jpeg|gif|webp)(\?.*)?$", x, re.IGNORECASE))


def coerce_int(x, default=None):
    try:
        return int(str(x))
    except Exception:
        return default


@st.cache_data(show_spinner=False, ttl=300)
def load_csv(url: str) -> pd.DataFrame:
    df = pd.read_csv(url)
    df.columns = [str(c) for c in df.columns]
    return df


# Page config + lock mode
q_pre = get_query_params()
LOCKED = str(q_pre.get("lock", "")).lower() in ("1", "true", "yes", "on")
st.set_page_config(page_title="Row Dashboard", layout="wide", initial_sidebar_state=("collapsed" if LOCKED else "auto"))
st.title("🔎 Row-by-Row Dashboard (Google Sheet)")


q = q_pre

# Default sheet
DEFAULT_SHEET = "https://docs.google.com/spreadsheets/d/1oaQZ6OwxJUti4AIf620Hp_bCjmKwu8AF9jYTv4vs7Hc/export?format=csv&gid=0"

# In locked mode, ignore override
if LOCKED:
    sheet = DEFAULT_SHEET
else:
    sheet = q.get("sheet") or DEFAULT_SHEET

sheet_id = q.get("sheet_id")
gid = q.get("gid")

if not LOCKED and (not q.get("sheet") and sheet_id):
    gid_val = gid if gid is not None else "0"
    sheet = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_val}"

# Sidebar (hidden in locked mode)
if not LOCKED:
    with st.sidebar:
        st.subheader("Data Source")
        csv_url = st.text_input(
            "Public Google Sheet CSV URL",
            value=sheet or "",
            placeholder="https://docs.google.com/spreadsheets/d/.../export?format=csv&gid=0",
            help=(
                "Use the Google Sheet CSV export URL. Your sheet must be shared as 'Anyone with the link (Viewer)'.\n"
                "You can also specify ?sheet_id=...&gid=... in the URL instead of pasting here."
            ),
        )
        st.caption("Tip: The app can also open a row by key via ?id= and ?id_col=")
else:
    # Hide sidebar
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {display: none !important;}
        [data-testid="collapsedControl"] {display: none !important;}
        </style>
        """,
        unsafe_allow_html=True
    )
    csv_url = sheet

# Load data
try:
    df = load_csv(csv_url) if csv_url else load_csv(sheet)
except Exception as e:
    st.error(f"โหลดข้อมูลจาก CSV ไม่สำเร็จ: {e}")
    st.stop()

if df.empty:
    st.warning("ตารางว่าง (No data rows). Please check your sheet.")
    st.stop()

# Resolve target row
row_param = coerce_int(q.get("row"), default=None)
id_value = q.get("id")
id_col = q.get("id_col")

selected_idx = None
if id_value and id_col and id_col in df.columns:
    matches = df.index[df[id_col].astype(str) == str(id_value)].tolist()
    if matches:
        selected_idx = matches[0]
elif row_param is not None:
    base = max(1, row_param)
    base = min(base, len(df))
    selected_idx = base - 1
else:
    if LOCKED:
        st.error("Locked mode ต้องระบุพารามิเตอร์ ?row= หรือ ?id= & id_col=")
        st.stop()
    selected_idx = 0

selected_idx = max(0, min(selected_idx, len(df) - 1))
row = df.iloc[selected_idx]

# Header metrics
left, mid, right = st.columns([1, 1, 2])
with left:
    st.metric("Total Rows", len(df))
with mid:
    st.metric("Selected Row", selected_idx + 1)
with right:
    if id_col and id_col in df.columns:
        st.metric("Key", f"{id_col} = {row.get(id_col)}")

# Navigation (hidden in LOCKED)
if not LOCKED:
    c1, c2, c3, c4 = st.columns([1, 1, 2, 3])
    with c1:
        prev_idx = max(0, selected_idx - 1)
        st.link_button("⬅️ Previous", "?" + urlencode({**{k:v for k,v in q.items() if k!='row'}, **{'row': prev_idx + 1}}), use_container_width=True)
    with c2:
        next_idx = min(len(df) - 1, selected_idx + 1)
        st.link_button("Next ➡️", "?" + urlencode({**{k:v for k,v in q.items() if k!='row'}, **{'row': next_idx + 1}}), use_container_width=True)
    with c3:
        st.write("")
    with c4:
        st.caption("Permalink to this row:")
        st.code("?" + urlencode({**{k:v for k,v in q.items() if k!='row'}, **{'row': selected_idx + 1}}), language="text")
else:
    st.caption("🔒 Locked single-row view")

st.divider()

# Determine display types
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
image_like_cols = [c for c in df.columns if df[c].astype(str).map(looks_like_image_url).any()]

# Layout
left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Row Details")
    if numeric_cols:
        metric_cols = st.columns(min(3, len(numeric_cols)))
        for i, col in enumerate(numeric_cols[:6]):
            with metric_cols[i % len(metric_cols)]:
                val = row[col]
                if pd.isna(val):
                    display = "-"
                else:
                    try:
                        display = f"{val:,.0f}" if float(val).is_integer() else f"{val:,.2f}"
                    except Exception:
                        display = str(val)
                st.metric(col, display)

    # Image preview (first image-like column)
    for col in image_like_cols:
        val = str(row[col])
        if looks_like_image_url(val):
            st.image(val, caption=col, use_container_width=True)
            break

    st.dataframe(row.to_frame().T, use_container_width=True)

with right_col:
    st.subheader("Quick Actions")
    row_dict = {k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k, v in row.to_dict().items()}

    json_bytes = json.dumps(row_dict, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("Download JSON", data=json_bytes, file_name=f"row_{selected_idx+1}.json", mime="application/json")

    import io as _io
    csv_buf = _io.StringIO()
    row.to_frame().T.to_csv(csv_buf, index=False)
    st.download_button("Download CSV", data=csv_buf.getvalue().encode("utf-8"), file_name=f"row_{selected_idx+1}.csv", mime="text/csv")

    if not LOCKED:
        st.caption("Jump to row…")
        jump_to = st.number_input("Row #", min_value=1, max_value=len(df), value=selected_idx + 1, step=1)
        new_q = {**{k:v for k,v in q.items() if k!='row'}, **{'row': int(jump_to)}}
        st.link_button("Go", "?" + urlencode(new_q), use_container_width=True)

        st.caption("Find by ID (if your sheet has an ID column)")
        cols = list(df.columns)
        idcol_q = q.get('id_col') or ''
        default_index = cols.index(idcol_q) if idcol_q in cols else 0
        id_col_input = st.selectbox("ID Column", options=cols, index=default_index, key="idcol")

        # SAFE default for ID value
        if q.get("id_col") and q.get("id_col") in df.columns:
            default_val = str(row.get(q.get("id_col"), ""))
        else:
            default_val = ""
        id_val_input = st.text_input("ID Value", value=default_val)

        if st.button("Open by ID", use_container_width=True):
            params = get_query_params()
            params.pop("row", None)
            set_query_params(**{**params, "id": id_val_input, "id_col": id_col_input})
            st.rerun()

# Footer/help
if not LOCKED:
    with st.expander("ℹ️ How to connect your Google Sheet"):
        st.markdown(
            """
            **Step 1 — Make your Google Sheet public (Viewer)**  
            Share → General access → *Anyone with the link* → Viewer.

            **Step 2 — CSV export URL**  
            Format:  
            `https://docs.google.com/spreadsheets/d/`**SHEET_ID**`/export?format=csv&gid=`**GID**

            **Step 3 — Open with parameters**  
            - By row number: `?row=10`  
            - By ID: `?id=ABC123&id_col=PatientID`
            """
        )

st.caption(("🔒 Locked view" if LOCKED else "URL navigation supports ?sheet=, ?row=, ?id= & ?id_col=") + " • Cached 5 minutes")
