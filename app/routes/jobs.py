"""
Job Status Tracking for Background Tasks
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from arq import create_pool
from arq.jobs import JobStatus
from ..worker import get_redis_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class JobStatusResponse(BaseModel):
    jobId: str
    status: str  # queued, in_progress, complete, failed
    result: Optional[dict] = None
    error: Optional[str] = None


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a background job
    Used to check contract generation progress
    """
    try:
        redis_settings = get_redis_settings()
        pool = await create_pool(redis_settings)
        
        job = await pool.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Map ARQ job status to our response
        status_map = {
            JobStatus.deferred: "queued",
            JobStatus.queued: "queued",
            JobStatus.in_progress: "in_progress",
            JobStatus.complete: "complete",
            JobStatus.not_found: "failed"
        }
        
        status = status_map.get(job.status, "unknown")
        
        # Get job result if complete
        result = None
        error = None
        
        if job.status == JobStatus.complete:
            try:
                result = await job.result()
                logger.info(f"✅ Job {job_id} completed successfully")
            except Exception as e:
                error = str(e)
                status = "failed"
                logger.error(f"❌ Job {job_id} failed: {error}")
        
        return JobStatusResponse(
            jobId=job_id,
            status=status,
            result=result,
            error=error
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job status")
