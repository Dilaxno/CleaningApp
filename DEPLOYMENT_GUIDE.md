# Deployment Guide - New Features

## Overview

This deployment includes:
1. **Cloudflare Turnstile CAPTCHA** - Bot prevention for public forms
2. **Async Contract Generation** - Background job processing to prevent timeouts
3. **Enhanced Rate Limiting** - Redis-based rate limiting with detailed logging

## Prerequisites

- ✅ Redis (Upstash recommended)
- ✅ Cloudflare Turnstile account (free tier available)
- ✅ Playwright installed on server

## Step 1: Update Dependencies

```bash
cd ~/CleaningApp/backend
source venv/bin/activate
pip install -r requirements.txt
```

**New dependencies:**
- `redis==5.0.1`
- `arq==0.26.0`

## Step 2: Install Playwright Browser

```bash
playwright install chromium
```

## Step 3: Update Environment Variables

Add to `~/CleaningApp/backend/.env`:

```env
# Redis (Required - use Upstash)
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_ENDPOINT.upstash.io:6379

# Cloudflare Turnstile (Get from https://dash.cloudflare.com/turnstile)
TURNSTILE_SECRET_KEY=0x4AAAAAAA...
```

### Get Upstash Redis URL

1. Go to [https://console.upstash.com/](https://console.upstash.com/)
2. Create a new Redis database
3. Copy the "Redis URL" (starts with `rediss://`)
4. Paste into `.env`

### Get Turnstile Secret Key

1. Go to [https://dash.cloudflare.com/](https://dash.cloudflare.com/)
2. Navigate to Turnstile
3. Create a new site
4. Choose "Invisible" widget
5. Add your domain (e.g., `cleanenroll.com`)
6. Copy the **Secret Key** to backend `.env`
7. Copy the **Site Key** to frontend `.env`

## Step 4: Deploy ARQ Worker Service

```bash
# Copy service file from project root (not in git for security)
sudo cp ~/CleaningApp/arq-worker.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable worker to start on boot
sudo systemctl enable arq-worker

# Start the worker
sudo systemctl start arq-worker

# Check status
sudo systemctl status arq-worker
```

## Step 5: Restart Main Application

```bash
sudo systemctl restart cleaningapp
```

## Step 6: Verify Deployment

### Check Redis Connection

```bash
sudo journalctl -u cleaningapp -f
```

Look for:
```
🔄 Initializing Redis connection for rate limiting...
✅ Redis connected successfully via URL - Rate limiting is ACTIVE
📊 Redis connection test: PONG received
✅ Redis rate limiting is ready
```

### Check ARQ Worker

```bash
sudo journalctl -u arq-worker -f
```

Look for:
```
INFO: arq worker started
INFO: Connected to Redis
```

### Test Form Submission

1. Go to your public client form
2. Submit 3 times - should work normally
3. On 4th submission - should show CAPTCHA
4. Complete CAPTCHA - submission should succeed
5. Check backend logs for job queuing:
   ```
   📋 Contract generation job queued: abc123-def456
   ```

## Monitoring

### View Application Logs

```bash
sudo journalctl -u cleaningapp -f
```

### View Worker Logs

```bash
sudo journalctl -u arq-worker -f
```

### View Both Together

```bash
sudo journalctl -u cleaningapp -u arq-worker -f
```

## Rate Limiting Configuration

**Current limits:**
- Password reset: 5 per hour per IP
- Webhooks: 100 per minute globally
- Client forms: 5 per minute per IP, 15 per minute globally
- Contract downloads: 5 per minute per IP, 3 per minute per contract

**CAPTCHA triggers:**
- After 3 form submissions per IP in 24 hours

## Troubleshooting

### Redis Connection Failed

**Error:** `Failed to connect to Redis: Connection refused`

**Solution:**
1. Check `REDIS_URL` in `.env`
2. Ensure URL starts with `rediss://` (double 's' for TLS)
3. Remove `redis-cli --tls -u` if present (that's CLI syntax, not URL)

### ARQ Worker Not Starting

**Error:** Worker exits immediately

**Solution:**
```bash
# Check for errors
sudo journalctl -u arq-worker -n 50

# Common fixes:
# 1. Install Playwright
playwright install chromium

# 2. Check environment file exists
ls -la ~/CleaningApp/backend/.env

# 3. Test Redis connection
redis-cli -u $REDIS_URL ping
```

### PDF Generation Timeouts

**Symptom:** Jobs stuck in "in_progress" status

**Solution:**
1. Increase job timeout in `app/worker.py`:
   ```python
   job_timeout = 600  # 10 minutes instead of 5
   ```

2. Check Playwright installation:
   ```bash
   playwright install --with-deps chromium
   ```

### High Memory Usage

**Symptom:** Server running out of memory

**Solution:**
Reduce concurrent jobs in `app/worker.py`:
```python
max_jobs = 3  # Reduce from 5 to 3
```

## Performance Tuning

### Scale Workers Horizontally

To handle more traffic, run multiple worker processes:

```bash
# Create multiple worker services
sudo cp /etc/systemd/system/arq-worker.service /etc/systemd/system/arq-worker-2.service
sudo systemctl enable arq-worker-2
sudo systemctl start arq-worker-2
```

### Adjust Concurrency

Edit `app/worker.py`:
```python
class WorkerSettings:
    max_jobs = 10  # Increase from 5 to 10
```

Then restart:
```bash
sudo systemctl restart arq-worker
```

## Rollback Plan

If issues occur:

```bash
# Stop ARQ worker
sudo systemctl stop arq-worker

# Revert to previous version
cd ~/CleaningApp/backend
git checkout HEAD~1

# Restart application
sudo systemctl restart cleaningapp
```

## Health Checks

### Redis
```bash
redis-cli -u $REDIS_URL ping
# Expected: PONG
```

### ARQ Worker
```bash
sudo systemctl is-active arq-worker
# Expected: active
```

### Application
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

## Security Notes

- ✅ Turnstile secret key is server-side only
- ✅ Redis uses TLS encryption (Upstash)
- ✅ Job results expire after 1 hour
- ✅ Rate limiting prevents abuse
- ✅ CAPTCHA prevents bot submissions

## Support

If deployment fails:
1. Check logs: `sudo journalctl -u cleaningapp -u arq-worker -n 100`
2. Verify environment variables: `env | grep REDIS`
3. Test Redis connection: `redis-cli -u $REDIS_URL ping`
4. Check Playwright: `playwright --version`
