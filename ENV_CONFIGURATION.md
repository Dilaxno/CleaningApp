# Backend Environment Configuration

This document outlines the required environment variables for the backend application.

## Required Environment Variables

### Database
```env
DATABASE_URL=postgresql://user:password@localhost:5432/cleaningapp
```

### Redis (Rate Limiting)

#### Option 1: Upstash Managed Redis (Recommended for Production)
```env
# Get these from your Upstash Redis dashboard (https://console.upstash.com/)
REDIS_URL=rediss://default:your-password@your-endpoint.upstash.io:6379
```

#### Option 2: Individual Configuration (Alternative)
```env
# For Upstash or self-hosted Redis
REDIS_HOST=your-endpoint.upstash.io
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0
REDIS_SSL=true  # Set to true for Upstash or managed Redis with SSL
```

#### Option 3: Local Development (Docker)
```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=  # Leave empty for local Redis without auth
REDIS_DB=0
REDIS_SSL=false
```

### Firebase
```env
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_API_KEY=your-firebase-api-key
```

### Cloudflare R2 (File Storage)
```env
R2_ACCOUNT_ID=your-r2-account-id
R2_ACCESS_KEY_ID=your-access-key
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET_NAME=your-bucket-name
```

### Email (Resend)
```env
RESEND_API_KEY=your-resend-api-key
FROM_EMAIL=noreply@yourdomain.com
```

### SMS (Twilio)
```env
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1234567890
```

### Google Calendar Integration
```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/google-calendar/callback
```

### Calendly Integration
```env
CALENDLY_CLIENT_ID=your-calendly-client-id
CALENDLY_CLIENT_SECRET=your-calendly-client-secret
CALENDLY_WEBHOOK_SECRET=your-calendly-webhook-secret
```

### Billing (Dodo Payments)
```env
DODO_PAYMENTS_API_KEY=your-dodo-api-key
DODO_PAYMENTS_ENVIRONMENT=test_mode  # or production
DODO_PAYMENTS_WEBHOOK_SECRET=your-dodo-webhook-secret
```

### Cloudflare Turnstile (CAPTCHA for bot prevention)
```env
TURNSTILE_SECRET_KEY=your-turnstile-secret-key
```

### LangCache (Optional - for caching)
```env
LANGCACHE_API_KEY=your-langcache-api-key
```

### Application Settings
```env
FRONTEND_URL=http://localhost:5173
API_URL=http://localhost:8000

# Security - Frontend Origins (comma-separated list for CSP frame-ancestors)
# Add all domains that should be allowed to embed API responses in iframes
# The wildcard *.cleanenroll.com is automatically added to support custom subdomains
FRONTEND_ORIGINS=http://localhost:5173,https://cleanenroll.com,https://www.cleanenroll.com
```

## Rate Limiting Configuration

The application uses Redis for rate limiting with the following defaults:

- **Password Reset**: 5 requests per hour per IP
- **Webhooks (Calendly & Billing)**: 100 requests per minute globally
- **Public Form Submissions**: 
  - 5 submissions per minute per IP
  - 15 submissions per minute globally

These limits are enforced at the application level using Redis sorted sets for sliding window rate limiting.

## Content Security Policy (CSP) Configuration

The backend API includes Content Security Policy headers to prevent security vulnerabilities. The `frame-ancestors` directive controls which domains can embed API responses in iframes.

### Default Configuration

By default, the following origins are allowed:
- The configured `FRONTEND_URL`
- `https://cleanenroll.com`
- `https://www.cleanenroll.com`
- `https://*.cleanenroll.com` (wildcard for all subdomains)

### Adding Custom Origins

If you need to allow additional domains to embed API responses (e.g., for custom client subdomains or partner integrations), add them to the `FRONTEND_ORIGINS` environment variable as a comma-separated list:

```env
FRONTEND_ORIGINS=http://localhost:5173,https://cleanenroll.com,https://www.cleanenroll.com,https://custom-domain.com
```

### CSP Error Troubleshooting

If you see a CSP error like:
```
Framing 'https://api.cleanenroll.com/' violates the following Content Security Policy directive: "frame-ancestors ..."
```

This means a domain is trying to embed the API in an iframe but isn't in the allowed list. To fix:

1. Identify the domain that needs access
2. Add it to the `FRONTEND_ORIGINS` environment variable
3. Restart the backend server
4. The wildcard `*.cleanenroll.com` automatically covers all cleanenroll subdomains

## Setting up Redis

### Upstash Redis (Recommended for Production)

1. **Create an Upstash account**: Visit [https://console.upstash.com/](https://console.upstash.com/)
2. **Create a new Redis database**:
   - Choose your region (select one close to your backend server)
   - Enable TLS/SSL (recommended)
   - Free tier available with 10,000 commands/day
3. **Get your connection details**:
   - Copy the **Redis URL** from the dashboard (starts with `rediss://`)
   - Format: `rediss://default:YOUR_PASSWORD@YOUR_ENDPOINT.upstash.io:6379`
4. **Add to your `.env` file**:
   ```env
   REDIS_URL=rediss://default:your-password@your-endpoint.upstash.io:6379
   ```

### Local Development (Docker)
```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

Then use:
```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_SSL=false
```

### Other Managed Options
- **Redis Cloud**: [https://redis.com/redis-enterprise-cloud/](https://redis.com/redis-enterprise-cloud/)
- **AWS ElastiCache**: [https://aws.amazon.com/elasticache/](https://aws.amazon.com/elasticache/)
- **DigitalOcean Managed Redis**: [https://www.digitalocean.com/products/managed-databases-redis](https://www.digitalocean.com/products/managed-databases-redis)

## Environment File Example

Create a `.env` file in the `backend` directory:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/cleaningapp

# Redis - Upstash (Recommended)
REDIS_URL=rediss://default:your-password@your-endpoint.upstash.io:6379

# Redis - Alternative (Local/Self-hosted)
# REDIS_HOST=localhost
# REDIS_PORT=6379
# REDIS_PASSWORD=
# REDIS_DB=0
# REDIS_SSL=false

# Firebase
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_API_KEY=your-api-key

# R2
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET_NAME=your-bucket

# Email
RESEND_API_KEY=re_your_key
FROM_EMAIL=noreply@yourdomain.com

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxx
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890

# Google Calendar
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/google-calendar/callback

# Calendly
CALENDLY_CLIENT_ID=your-client-id
CALENDLY_CLIENT_SECRET=your-secret
CALENDLY_WEBHOOK_SECRET=your-webhook-secret

# Billing
DODO_PAYMENTS_API_KEY=sk_test_xxxxx
DODO_PAYMENTS_ENVIRONMENT=test_mode
DODO_PAYMENTS_WEBHOOK_SECRET=whsec_xxxxx

# LangCache (Optional)
LANGCACHE_API_KEY=your-langcache-key

# URLs
FRONTEND_URL=http://localhost:5173
API_URL=http://localhost:8000
```
