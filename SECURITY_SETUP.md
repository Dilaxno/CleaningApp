# Security Settings Setup Guide

## Overview
The security module provides comprehensive 2FA and password management features for production use.

## Features Implemented

### 1. Password Management
- ✅ Change password with current password verification
- ✅ Firebase Authentication integration
- ✅ Real-time password strength validation
- ✅ Re-authentication before password change

### 2. Two-Factor Authentication (2FA)

#### TOTP Authenticator App
- ✅ QR code generation for easy setup
- ✅ Manual entry key provided
- ✅ Works with Google Authenticator, Authy, Microsoft Authenticator, etc.
- ✅ 6-digit verification codes
- ✅ Automatic backup codes generation

#### SMS 2FA
- ✅ Phone number verification
- ✅ SMS code sending (via Twilio - needs configuration)
- ✅ Enable/disable functionality

#### Recovery Email
- ✅ Secondary email verification
- ✅ Email-based verification codes
- ✅ Must be different from primary email

#### Backup Codes
- ✅ 10 cryptographically secure backup codes
- ✅ One-time use codes
- ✅ Encrypted storage in database
- ✅ Copy individual or all codes
- ✅ Regeneration capability

## Installation

### 1. Install Dependencies

```bash
cd backend
pip install pyotp==2.9.0 qrcode[pil]==7.4.2 twilio==9.0.0 cryptography==42.0.5
```

### 2. Run Database Migration

```bash
# Connect to your PostgreSQL database
psql -U your_user -d your_database -f migrations/add_2fa_fields.sql
```

Or using Python/SQLAlchemy:
```python
from app.database import engine, Base
Base.metadata.create_all(bind=engine)
```

### 3. Configure Environment Variables

Add to your `.env` file:

```env
# Required - Used for encrypting backup codes
SECRET_KEY=your-secret-key-here

# Optional - For SMS 2FA
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# Email service (already configured via Resend)
RESEND_API_KEY=your-resend-key
```

## API Endpoints

### Security Status
```http
GET /security/status
Authorization: Bearer <token>
```

### TOTP Setup
```http
POST /security/totp/setup
Authorization: Bearer <token>
```
Returns QR code and secret.

```http
POST /security/totp/verify
Authorization: Bearer <token>
Content-Type: application/json

{
  "verification_code": "123456"
}
```

```http
POST /security/totp/disable
Authorization: Bearer <token>
```

### SMS 2FA
```http
POST /security/phone/send-verification
Authorization: Bearer <token>
Content-Type: application/json

{
  "method": "phone",
  "target": "+1234567890"
}
```

```http
POST /security/phone/verify
Authorization: Bearer <token>
Content-Type: application/json

{
  "phone_number": "+1234567890",
  "verification_code": "123456"
}
```

```http
POST /security/phone/disable
Authorization: Bearer <token>
```

### Recovery Email
```http
POST /security/recovery-email/send-verification
Authorization: Bearer <token>
Content-Type: application/json

{
  "method": "email",
  "target": "recovery@example.com"
}
```

```http
POST /security/recovery-email/verify
Authorization: Bearer <token>
Content-Type: application/json

{
  "recovery_email": "recovery@example.com",
  "verification_code": "123456"
}
```

```http
POST /security/recovery-email/disable
Authorization: Bearer <token>
```

### Backup Codes
```http
POST /security/backup-codes/generate
Authorization: Bearer <token>
```

```http
GET /security/backup-codes/view
Authorization: Bearer <token>
```

```http
DELETE /security/backup-codes
Authorization: Bearer <token>
```

```http
POST /security/backup-codes/verify
Authorization: Bearer <token>
Content-Type: application/json

{
  "code": "ABCD-1234"
}
```

## SMS Configuration (Optional)

To enable SMS 2FA, configure Twilio:

1. Sign up at [Twilio](https://www.twilio.com/)
2. Get your Account SID and Auth Token
3. Purchase a phone number
4. Update `security.py` to use Twilio:

```python
from twilio.rest import Client
from ..config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER

# In send_phone_verification endpoint:
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
message = client.messages.create(
    body=f"Your CleanEnroll verification code is: {otp}",
    from_=TWILIO_PHONE_NUMBER,
    to=request.target
)
```

## Frontend Usage

The SecuritySettings component is already integrated. Navigate to:
```
Settings → Security
```

Features available:
- Change password with strength indicator
- Setup TOTP with QR code
- Setup SMS 2FA
- Setup recovery email
- Generate/view backup codes

## Security Best Practices

1. **Backup Codes**: Always encourage users to save backup codes
2. **Multiple 2FA Methods**: Allow users to enable multiple methods
3. **Rate Limiting**: Consider adding rate limiting to verification endpoints
4. **Audit Logs**: Log all security-related actions
5. **Session Management**: Consider requiring re-authentication for sensitive changes

## Testing

### Test TOTP Setup
1. Navigate to Settings → Security
2. Click "Setup" on Authenticator App
3. Scan QR code with Google Authenticator
4. Enter 6-digit code to verify
5. Save backup codes

### Test Phone 2FA
1. Click "Setup" on Phone Number
2. Enter phone number
3. Click "Send verification code"
4. Check logs for OTP (or SMS if Twilio configured)
5. Enter code to verify

### Test Recovery Email
1. Click "Setup" on Secondary Email
2. Enter email address
3. Click "Send verification code"
4. Check email inbox
5. Enter code to verify

## Troubleshooting

### QR Code Not Showing
- Check backend logs for errors
- Ensure `pyotp` and `qrcode` are installed
- Verify API endpoint is accessible

### SMS Not Sending
- Check Twilio configuration
- Verify phone number format (+1234567890)
- Check Twilio dashboard for errors

### Backup Codes Not Decrypting
- Ensure `SECRET_KEY` hasn't changed
- Check `cryptography` library is installed
- Verify database column is JSON type

## Production Checklist

- [ ] Database migration applied
- [ ] All dependencies installed
- [ ] Environment variables configured
- [ ] SMS provider configured (if using SMS 2FA)
- [ ] Email service working
- [ ] Frontend build tested
- [ ] Security endpoints tested
- [ ] Rate limiting configured
- [ ] Audit logging enabled
- [ ] Backup codes tested
- [ ] Password change tested
- [ ] 2FA setup flows tested

## Support

For issues or questions, check:
- Backend logs: Check FastAPI console
- Frontend logs: Check browser console
- Database: Verify migration applied correctly
- Email delivery: Check Resend dashboard
- SMS delivery: Check Twilio dashboard (if configured)
