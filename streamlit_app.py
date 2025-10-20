# Streamlit Row-by-Row Dashboard for Google Sheets (User-Ready)
# ------------------------------------------------
# This version is preconfigured to your Google Sheet as the default data source.
# You can still override by adding ?sheet=<CSV_URL> in the URL.
#
# URL Examples:
# - By row number:   ?row=1
# - By key column:   ?id=ABC123&id_col=PatientID
#
# Tip: Share your Google Sheet as "Anyone with the link → Viewer"


import io
import json
import math
import re
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

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


st.set_page_config(page_title="Row Dashboard", layout="wide")
st.title("🔎 Row-by-Row Dashboard (Google Sheet)")

q = get_query_params()

# Default to the user's sheet unless overridden via ?sheet= or ?sheet_id=&gid=
DEFAULT_SHEET = "https://docs.google.com/spreadsheets/d/1oaQZ6OwxJUti4AIf620Hp_bCjmKwu8AF9jYTv4vs7Hc/export?format=csv&gid=0"

sheet = q.get("sheet") or DEFAULT_SHEET
sheet_id = q.get("sheet_id")
gid = q.get("gid")

if not q.get("sheet") and sheet_id:
    gid_val = gid if gid is not None else "0"
    sheet = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_val}"

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

try:
    df = load_csv(csv_url) if csv_url else load_csv(DEFAULT_SHEET)
except Exception as e:
    st.error(f"โหลดข้อมูลจาก CSV ไม่สำเร็จ: {e}")
    st.stop()

if df.empty:
    st.warning("ตารางว่าง (No data rows). Please check your sheet.")
    st.stop()

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
    selected_idx = 0

selected_idx = max(0, min(selected_idx, len(df) - 1))
row = df.iloc[selected_idx]

def make_link(**updates):
    keep = {"sheet": None, "sheet_id": None, "gid": None, "id": None, "id_col": None}
    for k in list(keep.keys()):
        if q.get(k):
            keep[k] = q.get(k)
    # ensure we always keep the DEFAULT_SHEET if nothing provided
    if not keep.get("sheet") and not keep.get("sheet_id"):
        keep["sheet"] = DEFAULT_SHEET
    keep.update(updates)
    keep = {k: v for k, v in keep.items() if v is not None}
    return "?" + urlencode(keep)

left, mid, right = st.columns([1, 1, 2])
with left:
    st.metric("Total Rows", len(df))
with mid:
    st.metric("Selected Row", selected_idx + 1)
with right:
    if id_col and id_col in df.columns:
        st.metric("Key", f"{id_col} = {row.get(id_col)}")

c1, c2, c3, c4 = st.columns([1, 1, 2, 3])
with c1:
    prev_idx = max(0, selected_idx - 1)
    st.link_button("⬅️ Previous", make_link(row=prev_idx + 1), use_container_width=True)
with c2:
    next_idx = min(len(df) - 1, selected_idx + 1)
    st.link_button("Next ➡️", make_link(row=next_idx + 1), use_container_width=True)
with c3:
    st.write("")
with c4:
    st.caption("Permalink to this row:")
    st.code(make_link(row=selected_idx + 1), language="text")

numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
image_like_cols = [c for c in df.columns if df[c].astype(str).map(looks_like_image_url).any()]

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
                    display = f"{val:,.0f}" if float(val).is_integer() else f"{val:,.2f}"
                st.metric(col, display)

    shown_image = False
    for col in image_like_cols:
        val = str(row[col])
        if looks_like_image_url(val):
            st.image(val, caption=col, use_container_width=True)
            shown_image = True
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

    st.caption("Jump to row…")
    jump_to = st.number_input("Row #", min_value=1, max_value=len(df), value=selected_idx + 1, step=1)
    st.link_button("Go", make_link(row=int(jump_to)), use_container_width=True)

    st.caption("Find by ID (if your sheet has an ID column)")
    id_col_input = st.selectbox("ID Column", options=list(df.columns), index=0 if id_col in df.columns else 0, key="idcol")
    id_val_input = st.text_input("ID Value", value=str(row.get(id_col)) if id_col and id_col in df.columns else "")
    if st.button("Open by ID", use_container_width=True):
        params = get_query_params()
        params.pop("row", None)
        set_query_params(**{**params, "id": id_val_input, "id_col": id_col_input})
        st.rerun()

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

        **Tip**  
        - Header row should be the first row. Avoid merged cells.
        - For image preview, put a direct image URL in a column.
        """
    )

st.caption("URL navigation supports ?sheet=, ?row=, ?id= & ?id_col= • Cached 5 minutes")
