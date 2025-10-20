# Row-by-Row Dashboard (Streamlit)

This mini app shows **one row at a time** from your Google Sheet. It is pre-configured to your sheet:

- CSV URL (already set as default):  
  `https://docs.google.com/spreadsheets/d/1oaQZ6OwxJUti4AIf620Hp_bCjmKwu8AF9jYTv4vs7Hc/export?format=csv&gid=0`

## Quick Start

### Run locally
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
Then open:
```
http://localhost:8501/?row=1
```
(You can also override the sheet with: `?sheet=https://docs.google.com/spreadsheets/d/1oaQZ6OwxJUti4AIf620Hp_bCjmKwu8AF9jYTv4vs7Hc/export?format=csv&gid=0`)

### Deploy on Streamlit Cloud
1. Push these files to a new GitHub repo.
2. Create a new Streamlit Cloud app from that repo.
3. Open the app and use URL params:
   - `?row=1` (by row number)
   - `?id=ABC123&id_col=PatientID` (by key column)

## Notes
- Make sure your Google Sheet is shared as **Anyone with the link → Viewer**.
- If your sheet has multiple tabs, use the correct `gid` in the CSV export URL.
- Images are auto-previewed if the cell contains a direct image URL (jpg, png, gif, webp).
