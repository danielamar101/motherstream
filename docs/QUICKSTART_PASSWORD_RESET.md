# Password Reset - Quick Start Guide

## TL;DR - Get It Working in 5 Minutes

### 1. Apply Database Migration

```bash
# Option A: Apply the SQL migration
psql -U postgres -d motherstream_prod -f migrations/create_password_reset_tokens.sql

# Option B: Let SQLAlchemy create it on app startup (if you use create_all())
```

### 2. Configure Gmail SMTP (Easiest)

**Create Gmail App Password:**
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification
3. Go to "App Passwords" → Generate for "Mail"
4. Copy the 16-digit password

**Add to your `.env` file:**
```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx  # Your 16-digit app password
SMTP_FROM_EMAIL=noreply@motherstream.live
DOMAIN=motherstream.live  # or localhost:3000 for dev
```

### 3. Restart Your Application

```bash
# The password reset routes are now active!
```

### 4. Test It

**Frontend test:**
1. Go to `/login`
2. Click "Forgot Password?"
3. Enter your email
4. Check your inbox
5. Click the reset link
6. Set new password
7. Login with new password ✅

**API test:**
```bash
# Request reset
curl -X POST "http://localhost:8483/api/v1/password-recovery/user@example.com"

# You should receive an email with a token
# Then reset password:
curl -X POST "http://localhost:8483/api/v1/reset-password/" \
  -H "Content-Type: application/json" \
  -d '{"token": "TOKEN_FROM_EMAIL", "new_password": "newPassword123"}'
```

## What If Emails Aren't Sending?

### Quick Debug Checklist:

```bash
# 1. Check env vars are loaded
echo $SMTP_SERVER
echo $SMTP_USER

# 2. Test with the test email endpoint
curl -X POST "http://localhost:8483/api/v1/test-email/?email_to=your-email@gmail.com"

# 3. Check application logs for SMTP errors
tail -f logs/app.log  # or wherever your logs are
```

### Common Fixes:

| Problem | Solution |
|---------|----------|
| "Authentication failed" | Use App Password, not regular Gmail password |
| "Connection refused" | Check firewall isn't blocking port 587 |
| "SMTP not configured" | Env vars not loaded - restart app after adding them |
| Email goes to spam | Use proper domain email or SendGrid/AWS SES |

## Production Recommendations

### For Gmail:
- ✅ Free
- ✅ Easy setup
- ⚠️ 500 emails/day limit
- ⚠️ May go to spam
- **Best for:** Development, small deployments

### For SendGrid (Recommended):
```bash
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_FROM_EMAIL=noreply@motherstream.live
```
- ✅ Free tier: 100 emails/day
- ✅ Better deliverability
- ✅ Professional
- **Best for:** Production

### For AWS SES:
- ✅ Very cheap ($0.10 per 1,000 emails)
- ✅ Highly scalable
- ⚠️ More complex setup
- **Best for:** High volume production

## API Endpoints

### Request Password Reset
```http
POST /api/v1/password-recovery/{email}
```
Returns: Always 200 OK (security - no email enumeration)

### Reset Password
```http
POST /api/v1/reset-password/
Content-Type: application/json

{
  "token": "token-from-email",
  "new_password": "yourNewPassword"
}
```

## Files Changed

- ✅ `app/db/models.py` - Added PasswordResetToken model
- ✅ `app/db/crud.py` - Token management functions
- ✅ `app/db/email.py` - Email sending with HTML template
- ✅ `app/db/routes/password_reset.py` - New API routes
- ✅ `app/db/schemas.py` - Added schema
- ✅ `app/app.py` - Registered router
- ✅ `setup-env-files.sh` - SMTP config template

## Security Features

✅ 24-hour token expiration
✅ One-time use tokens
✅ Secure token generation
✅ Email enumeration prevention
✅ Old tokens invalidated on new request
✅ Comprehensive logging

## That's It! 🎉

Your password reset is now fully functional. Users who get locked out can now recover their accounts via email.

Need more details? See `PASSWORD_RESET_SETUP.md`

