# Deployment Guide

## Streamlit Cloud Deployment

### DOCX File Downloads ✅
**Yes, DOCX downloads will work perfectly on Streamlit Cloud.** The download button functionality is built into Streamlit and works seamlessly in cloud environments.

### Important Configuration for Production

#### 1. Files & Storage
- **Local Files**: Reports are saved in the `uploads/` directory
- **Streamlit Cloud**: Files persist in the mounted `uploads/` folder, so downloads will work
- **Temporary Files**: All temporary files are cleaned up after each session

#### 2. Environment Variables (.env)
Make sure these are set in Streamlit Cloud Secrets:
```
WHITELISTED_EMAILS=email1@example.com, email2@example.com
SENDER_EMAIL=your-gmail@gmail.com
SENDER_PASSWORD=your-16-char-app-password
SECRETARY_EMAIL=secretary@example.com
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
OAUTH_REDIRECT_URI=https://your-app.streamlit.app
GROQ_API_KEY=your-groq-api-key
```

#### 3. Credentials Files
- `google_credentials.json`: Upload to repository (sensitive - consider environment secrets)
- `roles.json`: Will be auto-created/updated
- `reports_store.json`: Persists reports locally

#### 4. Deployment Steps

```bash
# 1. Push to GitHub
git add .
git commit -m "Ready for deployment"
git push

# 2. Go to https://streamlit.io/cloud
# 3. Click "New app"
# 4. Connect GitHub repo
# 5. Set Main file path: app.py
# 6. Go to Settings → Secrets and add your .env variables
# 7. Deploy!
```

#### 5. IMPORTANT: Secrets Management
- **Never commit .env or google_credentials.json to public repo**
- Use Streamlit Cloud Secrets for all sensitive data
- `.gitignore` should include:
  ```
  .env
  google_credentials.json
  __pycache__/
  *.pyc
  uploads/
  reports_store.json
  ```

### Features That Work on Streamlit Cloud

✅ Google OAuth login
✅ DOCX report generation & download
✅ Report preview (read in-browser)
✅ Email sending (via SMTP)
✅ Admin member management
✅ Role-based access control
✅ File persistence in uploads folder

### Potential Issues & Solutions

**Issue**: Files disappear after redeploy
- **Solution**: Use persistent mount points or cloud storage

**Issue**: Email sending fails
- **Solution**: Ensure SENDER_EMAIL uses Gmail with App Password (not regular password)

**Issue**: Google OAuth fails
- **Solution**: Update OAUTH_REDIRECT_URI to your Streamlit Cloud URL in Google Cloud Console

### File Structure for Cloud
```
your-repo/
├── app.py
├── dashboard.py
├── auth.py
├── report_handler.py
├── docx_builder.py
├── email_service.py
├── sheets_service.py
├── utils.py
├── requirements.txt
├── roles.json (will be created)
├── reports_store.json (will be created)
├── uploads/ (created on first report)
├── pages/
├── assets/
└── .gitignore
```

---

**Note**: The Report Preview feature extracts text from DOCX files using python-docx. Formatting (colors, images) won't display in preview, but full DOCX download preserves all formatting.
