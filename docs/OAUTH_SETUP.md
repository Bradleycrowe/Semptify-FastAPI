# Setting Up OAuth Credentials for Semptify 5.0

Semptify uses cloud storage for authentication. Users connect their Google Drive, Dropbox, or OneDrive to authenticate.

## Quick Start (Choose One Provider)

The easiest to set up is **Google Drive**. You only need ONE provider to get started.

---

## Option 1: Google Drive (Recommended for Development)

### Step 1: Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Name it "Semptify" or similar

### Step 2: Enable Google Drive API
1. Go to **APIs & Services** > **Library**
2. Search for "Google Drive API"
3. Click **Enable**

### Step 3: Create OAuth Credentials
1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. If prompted, configure OAuth consent screen:
   - User Type: External
   - App name: Semptify
   - User support email: Your email
   - Developer contact: Your email
   - Scopes: Add `../auth/drive.file` and `../auth/userinfo.email`
4. Create OAuth client ID:
   - Application type: **Web application**
   - Name: Semptify Local
   - Authorized redirect URIs: `http://localhost:8000/storage/callback/google_drive`

### Step 4: Copy Credentials
Copy the Client ID and Client Secret to your `.env`:
```
GOOGLE_DRIVE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_DRIVE_CLIENT_SECRET=your-client-secret
```

---

## Option 2: Dropbox

### Step 1: Create Dropbox App
1. Go to [Dropbox App Console](https://www.dropbox.com/developers/apps)
2. Click **Create app**
3. Choose:
   - API: Scoped access
   - Type: App folder (more secure, recommended)
   - Name: Semptify

### Step 2: Configure App
1. In app settings, find **OAuth 2** section
2. Add redirect URI: `http://localhost:8000/storage/callback/dropbox`
3. Generate access token type: Offline (for refresh tokens)

### Step 3: Copy Credentials
```
DROPBOX_APP_KEY=your-app-key
DROPBOX_APP_SECRET=your-app-secret
```

---

## Option 3: OneDrive (Microsoft)

### Step 1: Register Azure Application
1. Go to [Azure Portal App Registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps)
2. Click **New registration**
3. Name: Semptify
4. Supported account types: Personal Microsoft accounts only (or multi-tenant)
5. Redirect URI: Web > `http://localhost:8000/storage/callback/onedrive`

### Step 2: Configure API Permissions
1. Go to **API permissions**
2. Add permissions:
   - Microsoft Graph > Delegated:
     - `Files.ReadWrite.AppFolder`
     - `User.Read`
     - `offline_access`

### Step 3: Create Client Secret
1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Copy the secret value (shown only once!)

### Step 4: Copy Credentials
```
ONEDRIVE_CLIENT_ID=your-application-client-id
ONEDRIVE_CLIENT_SECRET=your-client-secret-value
```

---

## Testing Your Setup

1. Start the server:
   ```powershell
   cd C:\Semptify\Semptify-FastAPI
   .\.venv\Scripts\Activate.ps1
   python -m uvicorn app.main:app --reload --port 8000
   ```

2. Check available providers:
   ```
   http://localhost:8000/storage/providers
   ```
   You should see your configured provider(s) listed.

3. Start OAuth flow:
   ```
   http://localhost:8000/storage/auth/google_drive
   ```
   (Replace `google_drive` with your provider)

4. After authorizing, you'll be redirected back with a session cookie.

5. Check your session:
   ```
   http://localhost:8000/storage/session
   ```

---

## Troubleshooting

### "redirect_uri_mismatch" Error
- Make sure the redirect URI in your OAuth app exactly matches:
  - Google: `http://localhost:8000/storage/callback/google_drive`
  - Dropbox: `http://localhost:8000/storage/callback/dropbox`
  - OneDrive: `http://localhost:8000/storage/callback/onedrive`

### "Access blocked" or "App not verified"
- For development, you can click "Advanced" > "Go to Semptify (unsafe)"
- For production, you'll need to verify your app with Google

### Provider not showing in /storage/providers
- Check your `.env` file has the credentials
- Restart the server after changing `.env`
- Check the client ID is not empty

---

## Production Considerations

1. **Use HTTPS**: OAuth requires HTTPS in production
2. **Verify your app**: Get Google/Microsoft verification for production use
3. **Update redirect URIs**: Change `localhost:8000` to your production domain
4. **Secure your secrets**: Use environment variables, not `.env` files in production
