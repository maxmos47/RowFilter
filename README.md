
# GAS Backend + Streamlit Frontend

This variant uses a **Google Apps Script (GAS) Web App** as a tiny API.

## Deploy GAS
1. Open https://script.google.com/ → New project.
2. Paste `Code.gs` into the editor.
3. Set `SHEET_ID` (and optionally `SHEET_NAME`, `TOKEN`).
4. Deploy → New deployment → Type: **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone with the link** (or your domain)
5. Copy the Web App URL (ends with `/exec`).

## Streamlit
- Put the URL into `.streamlit/secrets.toml`:

```toml
[gas]
webapp_url = "https://script.google.com/macros/s/AKfycb.../exec"
# token = "MY_SHARED_SECRET"   # if you set TOKEN in GAS
```

- Run `streamlit run streamlit_app_gas.py`.
- Use `?row=1&mode=edit`. On submit, the app updates column **L** via GAS and switches to `mode=view` to show **A–L**.

## API
- GET  .../exec?action=get&row=1[&token=...]
- POST .../exec  with form fields: action=update&row=1&value=Minor[&token=...]

Allowed L values: `Minor, Delayed, Immediate, Decreased`.
