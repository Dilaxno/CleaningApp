# Background Jobs with ARQ

This application uses **ARQ (Async Redis Queue)** for background job processing to handle long-running tasks like contract PDF generation.

## Why Background Jobs?

- ✅ **Prevents Timeouts**: PDF generation can take 5-30 seconds
- ✅ **Better UX**: Users get immediate response
- ✅ **Concurrency Control**: Max 5 PDFs generating at once
- ✅ **Reliability**: Jobs are retried on failure
- ✅ **Scalability**: Can scale workers independently

## Architecture

```
Client Form Submission
        ↓
    Create Client Record
        ↓
    Queue PDF Generation Job ──→ ARQ Worker (Background)
        ↓                              ↓
    Return Job ID                  Generate PDF
        ↓                              ↓
    Poll Job Status ←──────────── Upload to R2
        ↓                              ↓
    Get PDF URL                   Create Contract Record
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

ARQ requires:
- `arq==0.26.0`
- `redis==5.0.1`

### 2. Configure Environment

Add to your `.env` file:

```env
# Redis (required for both rate limiting and background jobs)
REDIS_URL=rediss://default:password@your-endpoint.upstash.io:6379
```

### 3. Start ARQ Worker

#### Development (Local)

```bash
cd backend
arq app.worker.WorkerSettings
```

#### Production (Systemd Service)

1. **Copy service file:**
```bash
sudo cp arq-worker.service /etc/systemd/system/
```

2. **Update paths in service file** if needed:
```bash
sudo nano /etc/systemd/system/arq-worker.service
```

3. **Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable arq-worker
sudo systemctl start arq-worker
```

4. **Check status:**
```bash
sudo systemctl status arq-worker
sudo journalctl -u arq-worker -f
```

## Available Jobs

### `generate_contract_pdf_task`

Generates contract PDFs asynchronously.

**Parameters:**
- `client_id` (int): Client ID
- `owner_uid` (str): Business owner Firebase UID
- `form_data` (dict): Form data for quote calculation
- `signature` (str, optional): Client signature (base64)

**Returns:**
```python
{
    "contract_id": 123,
    "pdf_url": "https://...",
    "status": "completed"
}
```

**Example:**
```python
from arq import create_pool
from app.worker import get_redis_settings

# Enqueue job
pool = await create_pool(get_redis_settings())
job = await pool.enqueue_job(
    'generate_contract_pdf_task',
    client_id=123,
    owner_uid="firebase-uid-123",
    form_data={"frequency": "Weekly", "rooms": 5},
    signature="data:image/png;base64,..."
)

print(f"Job queued: {job.job_id}")
```

## Job Status API

### Check Job Status

**Endpoint:** `GET /jobs/status/{job_id}`

**Response:**
```json
{
  "jobId": "abc123",
  "status": "complete",
  "result": {
    "contract_id": 123,
    "pdf_url": "https://...",
    "status": "completed"
  },
  "error": null
}
```

**Status Values:**
- `queued`: Job is waiting to be processed
- `in_progress`: Job is currently running
- `complete`: Job finished successfully
- `failed`: Job encountered an error

### Frontend Integration

```typescript
// 1. Submit form and get job ID
const response = await fetch('/clients/public/submit', {
  method: 'POST',
  body: JSON.stringify(formData)
});

const { jobId } = await response.json();

// 2. Poll for job completion
const pollInterval = setInterval(async () => {
  const status = await fetch(`/jobs/status/${jobId}`);
  const { status: jobStatus, result } = await status.json();
  
  if (jobStatus === 'complete') {
    clearInterval(pollInterval);
    console.log('PDF ready:', result.pdf_url);
  } else if (jobStatus === 'failed') {
    clearInterval(pollInterval);
    console.error('PDF generation failed');
  }
}, 2000); // Poll every 2 seconds
```

## Worker Configuration

**File:** `app/worker.py`

```python
class WorkerSettings:
    functions = [generate_contract_pdf_task]
    redis_settings = get_redis_settings()
    max_jobs = 5          # Max 5 concurrent PDF generations
    job_timeout = 300     # 5 minutes timeout per job
    keep_result = 3600    # Keep job results for 1 hour
```

### Adjust Concurrency

To handle more traffic, increase `max_jobs`:

```python
max_jobs = 10  # Allow 10 concurrent PDF generations
```

Or scale horizontally by running multiple worker processes:

```bash
# Terminal 1
arq app.worker.WorkerSettings

# Terminal 2
arq app.worker.WorkerSettings

# Terminal 3
arq app.worker.WorkerSettings
```

## Monitoring

### View Worker Logs

```bash
# Development
arq app.worker.WorkerSettings --verbose

# Production (systemd)
sudo journalctl -u arq-worker -f
```

### Expected Log Output

```
📄 Starting contract PDF generation for client 123
💰 Quote calculated: {...}
📝 HTML generated: 15234 chars
✅ PDF generated: 234567 bytes
✅ Contract created: ID=456, PDF uploaded to R2
```

### Health Check

Workers automatically reconnect to Redis if connection is lost. Monitor logs for:

```
✅ Connected to Redis for ARQ worker
❌ Redis connection failed - retrying...
```

## Troubleshooting

### Job Stuck in Queue

**Check worker is running:**
```bash
sudo systemctl status arq-worker
```

**Check Redis connection:**
```bash
redis-cli -u $REDIS_URL ping
```

### Job Fails Immediately

**Check logs:**
```bash
sudo journalctl -u arq-worker -n 50
```

**Common issues:**
- Missing environment variables (DATABASE_URL, R2 credentials)
- Playwright not installed: `playwright install chromium`
- Database connection issues

### High Memory Usage

PDF generation with Playwright can use 200-500MB per job.

**Solution:** Adjust `max_jobs` based on available memory:
- 2GB RAM: `max_jobs = 3`
- 4GB RAM: `max_jobs = 5`
- 8GB RAM: `max_jobs = 10`

## Performance

**Typical Job Times:**
- Simple contract (1-2 pages): 3-5 seconds
- Complex contract (5+ pages): 10-20 seconds

**Throughput with max_jobs=5:**
- ~15-25 contracts per minute
- ~900-1500 contracts per hour

## Security

- ✅ Jobs can only be created by authenticated endpoints
- ✅ Job results expire after 1 hour
- ✅ Redis connection uses TLS (Upstash)
- ✅ No sensitive data stored in job parameters
