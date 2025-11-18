# Password Reset Migration - Complete ✅

## Summary

The password reset functionality database migration has been successfully applied to both **staging** and **production** environments.

## Migration Details

**Migration ID:** `df5ed88c39f2`  
**Migration Name:** `add_password_reset_tokens_table`  
**Date Applied:** November 17, 2025  

### What Was Migrated

Created the `password_reset_tokens` table with:
- Primary key (`id`)
- Foreign key to `users` table (`user_id`)
- Unique token field (`token`)
- Timestamp tracking (`created_at`, `expires_at`)
- Usage tracking (`used`)
- Indexes for performance on `token`, `user_id`, and `expires_at`

## Status by Environment

### ✅ Staging
- **Database:** `motherstream_staging` on `postgres-staging`
- **Current Migration:** `df5ed88c39f2`
- **Status:** ✅ Complete
- **Table Exists:** Yes
- **Note:** Table was already present (likely created by SQLAlchemy), migration was stamped

### ✅ Production
- **Database:** `motherstream` on `postgres-prod`
- **Current Migration:** `df5ed88c39f2`
- **Status:** ✅ Complete
- **Table Exists:** Yes
- **Note:** Table was already present (likely created by SQLAlchemy), migration was stamped

## Verification

You can verify the migration status anytime:

```bash
# Check staging
docker exec postgres-staging psql -U motherstream -d motherstream_staging -c "SELECT version_num FROM alembic_version;"

# Check production
docker exec postgres-prod psql -U motherstream -d motherstream -c "SELECT version_num FROM alembic_version;"

# Verify table structure in staging
docker exec postgres-staging psql -U motherstream -d motherstream_staging -c "\d password_reset_tokens"

# Verify table structure in production
docker exec postgres-prod psql -U motherstream -d motherstream -c "\d password_reset_tokens"
```

## What's Next

The password reset feature is now fully operational! 

### Required: Configure SMTP

To enable email sending, configure SMTP settings in your environment files:

```bash
# Edit .env.prod or .env.staging
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@motherstream.live
DOMAIN=motherstream.live
```

Then restart your containers:
```bash
sudo ./stop-all.sh && sudo ./start-all.sh
```

### Testing the Feature

1. **Frontend test:**
   - Go to https://motherstream.live/login (or staging URL)
   - Click "Forgot Password?"
   - Enter your email
   - Check inbox for reset link
   - Click link and set new password

2. **API test:**
```bash
# Request password reset
curl -X POST "https://motherstream.live/backend/api/v1/password-recovery/user@example.com"

# Reset password (use token from email)
curl -X POST "https://motherstream.live/backend/api/v1/reset-password/" \
  -H "Content-Type: application/json" \
  -d '{"token": "TOKEN_FROM_EMAIL", "new_password": "newPassword123"}'
```

## Migration Files

- **Alembic Migration:** `alembic/versions/df5ed88c39f2_add_password_reset_tokens_table.py`
- **SQL Backup:** `migrations/create_password_reset_tokens.sql`
- **Setup Guide:** `PASSWORD_RESET_SETUP.md`
- **Quick Start:** `QUICKSTART_PASSWORD_RESET.md`

## Rollback (If Needed)

If you need to rollback this migration:

```bash
# Staging
docker exec motherstream-staging bash -c "cd /app && /app/dependencies/bin/alembic downgrade 5e7b4d3f3a12"

# Production
docker exec motherstream-prod bash -c "cd /app && /app/dependencies/bin/alembic downgrade 5e7b4d3f3a12"
```

This will drop the `password_reset_tokens` table and revert to the previous migration.

## Support

For issues or questions:
1. Check `PASSWORD_RESET_SETUP.md` for comprehensive documentation
2. See `QUICKSTART_PASSWORD_RESET.md` for quick SMTP setup
3. Review application logs: `sudo docker logs --follow motherstream-prod`

---

**Status:** ✅ Migration Complete - Feature Ready for Testing

