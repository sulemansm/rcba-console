# Streamlit Cloud Deployment Guide

Complete step-by-step instructions to deploy your RCBA Event Reporter to Streamlit Cloud (Free Tier).

---

## Pre-Deployment Checklist

✅ All code is ready for Streamlit Cloud
✅ Supabase is configured and working
✅ All files are properly committed to GitHub
✅ Google OAuth credentials are available

**Estimated Time: 30-45 minutes**

---

## STEP 1: Prepare Your GitHub Repository

### 1.1 Create a GitHub Account (if you don't have one)
- Go to https://github.com/signup
- Sign up and verify your email
- Create a new repository name: `rcba-event-reporter`

### 1.2 Initialize Git in Your Project
```bash
# Navigate to your project folder
cd c:\Users\Suleman Mathekar\Downloads\rcba-rbac-upgrade\rcba-rbac

# Initialize git
git init
git add .
git commit -m "Initial commit: RCBA Event Reporter with Supabase"
```

### 1.3 Push to GitHub
```bash
# Add your GitHub repository as remote
git remote add origin https://github.com/YOUR_USERNAME/rcba-event-reporter.git

# Rename branch to main if needed
git branch -M main

# Push to GitHub
git push -u origin main
```

**Important:** The `.gitignore` file will automatically prevent `.env`, `google_credentials.json`, and `.streamlit/secrets.toml` from being uploaded. ✅

---

## STEP 2: Set Up Google OAuth for Cloud

Your current OAuth redirect URI is set for `localhost`. You need to update it for Streamlit Cloud.

### 2.1 Get Your Streamlit Cloud URL Format
When you deploy, Streamlit will give you a URL like:
```
https://your-username-rcba-event-reporter.streamlit.app
```

Save this URL (you'll get it after deployment).

### 2.2 Update Google Cloud Console
1. Go to https://console.cloud.google.com
2. Click on your project: **sullzz**
3. Go to **APIs & Services** > **Credentials**
4. Find your OAuth 2.0 Client ID
5. Click the edit icon
6. Under **Authorized redirect URIs**, add:
   ```
   http://localhost:8501/
   https://your-username-rcba-event-reporter.streamlit.app/
   ```
7. Save changes

**Note:** Do this AFTER you get your Streamlit URL (Step 4)

---

## STEP 3: Create Streamlit Cloud Account & Deploy

### 3.1 Sign Up for Streamlit Cloud
1. Go to https://streamlit.io/cloud
2. Click **Sign up for free** or **Sign in** (if you already have an account)
3. Use your GitHub account to sign in (easiest method)
4. Authorize Streamlit to access your GitHub repositories

### 3.2 Deploy Your App
1. Click **Create app**
2. Choose your repository: `rcba-event-reporter`
3. Select branch: `main`
4. Select script: `app.py`
5. Click **Deploy** and wait 2-3 minutes

Your app URL will be: `https://your-username-rcba-event-reporter.streamlit.app`

---

## STEP 4: Add Secrets to Streamlit Cloud

### 4.1 Access Secrets Settings
1. Go to your deployed app
2. Click **⋮ (three dots)** → **Settings**
3. Click **Secrets** on the left sidebar

### 4.2 Add Your Secrets
Copy and paste the following format. Replace values with your actual credentials:

```toml
# Supabase
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-key-here"

# Google OAuth (as JSON string)
GOOGLE_CREDENTIALS_JSON = """{"web": {"client_id": "438422441784-...", "client_secret": "GOCSPX-...", "redirect_uris": ["http://localhost:8501/", "https://your-username-rcba-event-reporter.streamlit.app/"], ...}}"""

# OAuth
OAUTH_REDIRECT_URI = "https://your-username-rcba-event-reporter.streamlit.app/"

# Whitelisted Emails (comma-separated)
WHITELISTED_EMAILS = "sulemansmathekar@gmail.com,admin@example.com"

# Email (optional, for notifications)
SENDER_EMAIL = "your-email@gmail.com"
SENDER_PASSWORD = "your-app-specific-password"
SECRETARY_EMAIL = "secretary@example.com"

# Groq API (optional, for AI features)
GROQ_API_KEY = "gsk_..."
```

**To find your credentials:**

- **SUPABASE_URL & SUPABASE_KEY**: Go to https://app.supabase.com → Project Settings → API
- **GOOGLE_CREDENTIALS_JSON**: Copy from your google_credentials.json file, keeping everything as one JSON string
- **WHITELISTED_EMAILS**: Add emails that can access the app

### 4.3 Save Secrets
Click **Save** and your app will automatically redeploy with the new secrets.

---

## STEP 5: Test Your Deployed App

### 5.1 Open Your App
Click the **Visit app** button or go to:
```
https://your-username-rcba-event-reporter.streamlit.app
```

### 5.2 Test OAuth Login
1. Click **Login with Google**
2. Use an email from WHITELISTED_EMAILS
3. Verify you're logged in

### 5.3 Test Core Features
- [ ] Create a new event report
- [ ] See club members in the dropdown (synced from Supabase)
- [ ] Submit the report (saves to Supabase)
- [ ] View dashboard (loads reports from Supabase)
- [ ] Download DOCX file
- [ ] Add a new member via admin
- [ ] See new member appear in attendance dropdown (within 30 seconds)

---

## STEP 6: Update Google OAuth Redirect URIs (IMPORTANT)

### 6.1 Add Cloud URL to Google Console
1. Go to https://console.cloud.google.com
2. Select project: **sullzz**
3. APIs & Services → Credentials
4. Edit your OAuth 2.0 Client ID
5. Add authorized redirect URI:
   ```
   https://your-username-rcba-event-reporter.streamlit.app/
   ```
6. Save changes

Your app should now work perfectly! ✅

---

## TROUBLESHOOTING

### Issue: "OAuth Error" or "Invalid Redirect URI"
**Solution:** 
- Make sure `OAUTH_REDIRECT_URI` in secrets matches your actual Streamlit URL exactly
- Make sure this URL is added to Google Cloud Console
- Wait 5 minutes for changes to propagate

### Issue: "Supabase Connection Failed"
**Solution:**
- Verify SUPABASE_URL and SUPABASE_KEY are correct
- Check that Supabase project is not paused
- Go to Supabase dashboard → project → Database → check RLS is disabled on tables

### Issue: "Members not loading in attendance dropdown"
**Solution:**
- Wait 30 seconds (cache TTL) after adding members
- Refresh the page manually
- Check Supabase members table directly to verify members exist

### Issue: "Reports not saving"
**Solution:**
- Check Supabase reports table exists and RLS is disabled
- Verify SUPABASE_URL and SUPABASE_KEY are correct
- Check Streamlit Cloud logs: App menu → Manage app → View logs

### Issue: "Google OAuth credentials not found"
**Solution:**
- Ensure GOOGLE_CREDENTIALS_JSON is properly formatted as JSON string in secrets
- Check that all quotes are properly escaped
- Or upload credentials file (less secure)

---

## Regular Maintenance

### Updating Your App
After making code changes:
```bash
git add .
git commit -m "Your message here"
git push origin main
```
Streamlit Cloud will automatically redeploy.

### Monitoring
- Check app logs: App menu → Manage app → View logs
- Monitor Supabase usage: https://app.supabase.com
- Keep secrets secure - never commit them

---

## What's Different on Streamlit Cloud vs. Local?

| Feature | Local | Cloud |
|---------|-------|-------|
| Credentials | `.env` file or google_credentials.json | Streamlit Secrets |
| Members storage | Supabase | Supabase (same) |
| Reports storage | Supabase | Supabase (same) |
| OAuth redirect URI | http://localhost:8501/ | https://your-app.streamlit.app |
| File uploads | /uploads/ folder (local) | Not persisted (use Supabase) |
| Database | Supabase (same) | Supabase (same) |
| Custom domain | N/A | Free: subdomain only |

---

## Free Tier Limitations

Streamlit Cloud free tier has the following limits:
- **Compute**: Shared CPU, limited memory
- **Runtime**: App sleeps after 1 hour of inactivity
- **Data**: No limit (but use Supabase for persistence)
- **Custom domain**: Requires paid plan

For production, consider upgrading to **Streamlit+ team membership** ($99/month).

---

## Support & Resources

- **Streamlit Docs**: https://docs.streamlit.io
- **Streamlit Cloud**: https://streamlit.io/cloud
- **Supabase Docs**: https://supabase.com/docs
- **Google OAuth**: https://developers.google.com/identity

---

## Next Steps

1. ✅ Push code to GitHub
2. ✅ Deploy to Streamlit Cloud
3. ✅ Add secrets via Streamlit dashboard
4. ✅ Update Google OAuth URIs
5. ✅ Test all features
6. ✅ Share the URL with your team!

Your app is now live! 🚀
