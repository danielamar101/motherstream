# Password Reset Setup Guide

## Overview

The password reset mechanism has been fully implemented for Motherstream. Users can now request a password reset via email, and they'll receive a secure link to create a new password.

## What Was Implemented

### Backend Changes

1. **Database Model** (`app/db/models.py`)
   - Added `PasswordResetToken` table to store reset tokens
   - Includes token expiration (24 hours) and one-time use tracking
   - Foreign key relationship to User table

2. **CRUD Functions** (`app/db/crud.py`)
   - `create_password_reset_token()` - Generates secure tokens
   - `get_password_reset_token()` - Validates tokens
   - `mark_token_as_used()` - Prevents token reuse
   - `reset_user_password()` - Updates user password
   - `cleanup_expired_tokens()` - Maintenance function

3. **Email Service** (`app/db/email.py`)
   - Professional HTML email template
   - Environment-based SMTP configuration
   - Proper error handling and logging

4. **API Routes** (`app/db/routes/password_reset.py`)
   - `POST /api/v1/password-recovery/{email}` - Request reset
   - `POST /api/v1/reset-password/` - Reset password with token
   - Security: Prevents email enumeration attacks

5. **Schema** (`app/db/schemas.py`)
   - Added `PasswordRecoveryRequest` schema

### Frontend
- Already implemented! The frontend pages work with the new backend.

## Setup Instructions

### Step 1: Database Migration

The new `password_reset_tokens` table needs to be created in your database.

**Option A: Let SQLAlchemy create it automatically**
```bash
# When you start the application, if using create_all(), it will create the table
# Check your database initialization code
```

**Option B: Manual SQL (if needed)**
```sql
CREATE TABLE password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    token VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_password_reset_token ON password_reset_tokens(token);
CREATE INDEX idx_password_reset_user_id ON password_reset_tokens(user_id);
```

### Step 2: Configure SMTP Settings

You need to set up email sending. Choose one of these options:

#### Option 1: Gmail (Free - Recommended for Development)

1. Enable 2-Factor Authentication on your Gmail account
2. Generate an App Password:
   - Go to Google Account Settings → Security → 2-Step Verification → App Passwords
   - Generate a new app password for "Mail"
3. Update your `.env` file:

```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-digit-app-password  # NOT your regular password!
SMTP_FROM_EMAIL=noreply@motherstream.live
DOMAIN=motherstream.live  # or localhost for testing
```

**Gmail Limits:** 500 emails/day (perfect for password resets)

#### Option 2: SendGrid (Free - Recommended for Production)

1. Sign up at https://sendgrid.com (free tier: 100 emails/day)
2. Create an API key
3. Update your `.env` file:

```bash
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey  # literally the word "apikey"
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_FROM_EMAIL=noreply@motherstream.live
DOMAIN=motherstream.live
```

#### Option 3: AWS SES (Cheapest for High Volume)

```bash
SMTP_SERVER=email-smtp.us-east-1.amazonaws.com  # Your region
SMTP_PORT=587
SMTP_USER=your-smtp-username
SMTP_PASSWORD=your-smtp-password
SMTP_FROM_EMAIL=noreply@motherstream.live
DOMAIN=motherstream.live
```

### Step 3: Regenerate Environment Files

If you want to use the updated template:

```bash
bash setup-env-files.sh
```

Then edit `.env.prod` and `.env.staging` with your actual SMTP credentials.

### Step 4: Test the Setup

1. **Test email configuration:**
```bash
# Use the existing test endpoint
curl -X POST "http://localhost:8483/api/v1/test-email/?email_to=your-email@example.com"
```

2. **Test password reset request:**
```bash
curl -X POST "http://localhost:8483/api/v1/password-recovery/user@example.com"
```

3. **Check logs for any errors:**
```bash
# Look for SMTP errors or token creation issues
```

### Step 5: Verify Frontend Integration

1. Go to `/recover-password` on your frontend
2. Enter an email address
3. Check that you receive the reset email
4. Click the link and verify you can reset the password
5. Try logging in with the new password

## How It Works

### User Flow

1. **User clicks "Forgot Password"** on login page
2. **Enters email** on recovery page
3. **System generates token** and sends email (takes ~2-5 seconds)
4. **User receives email** with reset link
5. **User clicks link** → Redirected to reset password page with token in URL
6. **User enters new password**
7. **System validates token** and updates password
8. **User can now log in** with new password

### Security Features

✅ **Email Enumeration Prevention** - Always returns success message
✅ **Secure Token Generation** - Uses `secrets.token_urlsafe(32)`
✅ **Token Expiration** - 24-hour validity
✅ **One-time Use** - Tokens invalidated after use
✅ **Old Token Invalidation** - New requests invalidate previous tokens
✅ **Password Hashing** - Argon2 hashing maintained
✅ **Comprehensive Logging** - All attempts logged for security audit

## API Documentation

### Request Password Reset

```http
POST /api/v1/password-recovery/{email}
```

**Response:** Always returns 200 OK (security)
```json
{
  "message": "If that email exists, a password reset link has been sent"
}
```

### Reset Password

```http
POST /api/v1/reset-password/
Content-Type: application/json

{
  "token": "secure-token-from-email",
  "new_password": "newSecurePassword123"
}
```

**Success Response:**
```json
{
  "message": "Password has been reset successfully"
}
```

**Error Response (Invalid Token):**
```json
{
  "detail": "Invalid or expired password reset token"
}
```

## Troubleshooting

### Email Not Sending

**Check logs for SMTP errors:**
```bash
# Common issues:
# 1. Wrong SMTP credentials
# 2. Need App Password (Gmail)
# 3. Port blocked by firewall
# 4. SMTP_SERVER not set
```

**Verify environment variables are loaded:**
```python
import os
print(os.environ.get('SMTP_SERVER'))
print(os.environ.get('SMTP_USER'))
```

### Token Not Working

**Check token hasn't expired:**
```sql
SELECT * FROM password_reset_tokens 
WHERE token = 'your-token' 
AND used = FALSE 
AND expires_at > NOW();
```

**Check database table exists:**
```sql
SELECT * FROM information_schema.tables 
WHERE table_name = 'password_reset_tokens';
```

### Email Goes to Spam

**Solutions:**
- Use a verified domain email (not Gmail personal)
- Set up SPF, DKIM, DMARC records
- Use a dedicated email service (SendGrid, AWS SES)
- Ensure SMTP_FROM_EMAIL matches your domain

## Maintenance

### Clean Up Expired Tokens (Optional)

Add a periodic cleanup job:

```python
# In a scheduled task or cron job
from app.db import crud
from app.db.main import SessionLocal

db = SessionLocal()
deleted_count = crud.cleanup_expired_tokens(db)
print(f"Cleaned up {deleted_count} expired tokens")
db.close()
```

### Monitor Usage

```sql
-- Check password reset activity
SELECT 
    COUNT(*) as total_requests,
    COUNT(CASE WHEN used = TRUE THEN 1 END) as completed_resets,
    COUNT(CASE WHEN expires_at < NOW() THEN 1 END) as expired_tokens
FROM password_reset_tokens;
```

## Production Checklist

Before deploying to production:

- [ ] SMTP credentials configured in production `.env`
- [ ] Database migration applied
- [ ] Test email sending from production server
- [ ] Verify emails don't go to spam
- [ ] Check DOMAIN environment variable is correct
- [ ] Test complete flow end-to-end
- [ ] Monitor logs for first few days
- [ ] Set up rate limiting (optional, future enhancement)
- [ ] Configure email monitoring/alerts

## Future Enhancements (Optional)

Consider adding these later:
- Rate limiting on password reset requests (3 per hour per IP)
- Email notification when password is changed
- Account lockout after multiple failed attempts
- Custom email templates per user language
- Password strength requirements
- 2FA integration

## Support

If you encounter issues:
1. Check the logs in your application
2. Verify all environment variables are set
3. Test SMTP connection separately
4. Ensure database table was created
5. Check firewall rules for SMTP ports

## Summary

✅ **Database models created**
✅ **CRUD functions implemented**
✅ **Email service configured**
✅ **API routes created and registered**
✅ **Security measures in place**
✅ **Environment configuration updated**
✅ **Frontend already compatible**

**Next Steps:**
1. Configure SMTP credentials
2. Run/apply database migrations
3. Test the flow
4. Deploy and monitor

🎉 **Your password reset mechanism is ready to use!**

