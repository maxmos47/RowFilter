# Row-by-Row Dashboard (Streamlit) — Locked Mode Ready

Pre-configured to your Google Sheet:

- CSV URL (default):  
  `https://docs.google.com/spreadsheets/d/1oaQZ6OwxJUti4AIf620Hp_bCjmKwu8AF9jYTv4vs7Hc/export?format=csv&gid=0`

## Run locally
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Shareable URLs
- Normal (navigable): `?row=5`
- **Locked single-row**: `?row=5&lock=1`
- Locked by key: `?id=ABC123&id_col=PatientID&lock=1`

> In locked mode: sidebar & navigation are hidden, and overriding the sheet via `?sheet=` is disabled.
