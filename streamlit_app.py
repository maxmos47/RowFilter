
# Patient Data — Mobile-First One-Row Viewer
# ------------------------------------------
# URL params: ?row=, ?id=&id_col=, ?lock=1

import re
import pandas as pd
import streamlit as st

DEFAULT_SHEET_CSV = "https://docs.google.com/spreadsheets/d/1oaQZ6OwxJUti4AIf620Hp_bCjmKwu8AF9jYTv4vs7Hc/export?format=csv&gid=0"

def get_query_params() -> dict:
    try:
        return dict(st.query_params)
    except Exception:
        return {k: v[0] if isinstance(v, list) else v for k, v in st.experimental_get_query_params().items()}

def coerce_int(x, default=None):
    try:
        return int(str(x))
    except Exception:
        return default

def looks_like_image_url(x: str) -> bool:
    if not isinstance(x, str):
        return False
    return bool(re.search(r"\.(png|jpg|jpeg|gif|webp)(\?.*)?$", x, re.IGNORECASE))

@st.cache_data(show_spinner=False, ttl=300)
def load_csv(url: str) -> pd.DataFrame:
    df = pd.read_csv(url)
    df.columns = [str(c) for c in df.columns]
    return df

q_pre = get_query_params()
LOCKED = str(q_pre.get("lock", "")).lower() in ("1", "true", "yes", "on")
st.set_page_config(page_title="Patient data", layout="centered", initial_sidebar_state=("collapsed" if LOCKED else "auto"))

hide_css = "" if not LOCKED else '''
[data-testid='stSidebar'] {display:none !important;}
[data-testid='collapsedControl'] {display:none !important;}
'''

st.markdown(
    '''
    <style>
      {hide_css}
      .block-container {{padding-top: .25rem; padding-bottom: 1rem; max-width: 760px;}}
      .kv-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: .55rem;
      }}
      @media (max-width: 520px) {{
        .kv-grid {{ grid-template-columns: 1fr; }}
      }}
      .kv-card {{
        border: 1px solid #e5e7eb;
        border-radius: .75rem;
        padding: .65rem .75rem;
        background: #ffffff;
        box-shadow: 0 1px 2px rgba(0,0,0,.04);
      }}
      .kv-label {{ font-size: .82rem; color: #6b7280; margin-bottom: .25rem; line-height: 1.1; }}
      .kv-value {{ font-size: 1.05rem; color: #111827; word-break: break-word; white-space: pre-wrap; line-height: 1.25; }}
      .kv-img {{ width: 100%; height: auto; border-radius: .5rem; }}
      header[data-testid="stHeader"] {{height: 0; visibility: hidden;}}
      .small-cap {{ color:#6b7280; font-size:.85rem; margin-top:.5rem; }}
    </style>
    '''.format(hide_css=hide_css),
    unsafe_allow_html=True,
)

st.subheader("Patient data")

# --- Determine sheet source ---
if LOCKED:
    sheet_csv = DEFAULT_SHEET_CSV
else:
    sheet_csv = q_pre.get("sheet") or DEFAULT_SHEET_CSV
    sid = q_pre.get("sheet_id")
    gid = q_pre.get("gid")
    if (not q_pre.get("sheet")) and sid:
        gid_val = gid if gid is not None else "0"
        sheet_csv = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid_val}"

if not LOCKED:
    with st.sidebar:
        st.caption("Data source (optional override)")
        sheet_csv_input = st.text_input(
            "Google Sheet CSV URL",
            value=sheet_csv,
            placeholder="https://.../export?format=csv&gid=0"
        )
        sheet_csv = sheet_csv_input or sheet_csv

# --- Load data ---
try:
    df = load_csv(sheet_csv)
except Exception as e:
    st.error(f"โหลดข้อมูลจาก CSV ไม่สำเร็จ: {e}")
    st.stop()

if df.empty:
    st.warning("ตารางว่าง (No data rows).")
    st.stop()

# --- Resolve target row / id ---
q = q_pre
row_param = coerce_int(q.get("row"), default=None)
id_value = q.get("id")
id_col = q.get("id_col")

selected_idx = None
if id_value or id_col:
    if not (id_value and id_col):
        st.error("❌ ไม่พบข้อมูล: โปรดระบุทั้ง id= และ id_col=")
        st.stop()
    if id_col not in df.columns:
        st.error(f"❌ ไม่พบคอลัมน์ '{id_col}' ในข้อมูล")
        st.stop()
    matches = df.index[df[id_col].astype(str) == str(id_value)].tolist()
    if matches:
        selected_idx = matches[0]
    else:
        st.error("❌ ไม่พบข้อมูลตาม ID ที่ระบุ")
        st.stop()
elif row_param is not None:
    if 1 <= row_param <= len(df):
        selected_idx = row_param - 1
    else:
        st.error(f"❌ ไม่พบข้อมูลในแถวที่ระบุ (row={row_param}) ข้อมูลมีช่วง 1–{len(df)}")
        st.stop()
else:
    if LOCKED:
        st.error("Locked mode ต้องระบุพารามิเตอร์ ?row= หรือ ?id= & id_col=")
        st.stop()
    selected_idx = 0

row = df.iloc[selected_idx]

priority = [c for c in ["HN","PatientID","Name","FullName","Triage","TriageScore","Age","Sex","VisitDate","ChiefComplaint","WaitingTime","Disposition"] if c in df.columns]
others = [c for c in df.columns if c not in priority]
ordered_cols = priority + others

def escape_html(s: str) -> str:
    return (s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))

# --- Render as responsive key–value cards ---
cards = []
for col in ordered_cols:
    val = row[col]
    disp = "" if pd.isna(val) else str(val)
    if looks_like_image_url(disp):
        content = f"<img class='kv-img' src='{disp}' alt='{col}'>"
    else:
        content = escape_html(disp)
    cards.append(
        "<div class='kv-card'>"
        f"<div class='kv-label'>{escape_html(str(col))}</div>"
        f"<div class='kv-value'>{content}</div>"
        "</div>"
    )

grid_html = "<div class='kv-grid'>" + "\n".join(cards) + "</div>"
st.markdown(grid_html, unsafe_allow_html=True)
st.markdown(f"<div class='small-cap'>Showing row {selected_idx+1} of {len(df)}</div>", unsafe_allow_html=True)
