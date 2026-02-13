"""
Job Status Tracking for Background Tasks
"""

import asyncio
import logging
from typing import Optional

from arq import create_pool
from arq.jobs import Job, JobStatus
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..worker import get_redis_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class JobStatusResponse(BaseModel):
    jobId: str
    status: str  # queued, in_progress, complete, failed
    result: Optional[dict] = None
    error: Optional[str] = None


async def get_job_status_with_retry(job_id: str, max_retries: int = 3, retry_delay: float = 1.0):
    """
    Get job status with exponential backoff retry logic
    """
    for attempt in range(max_retries):
        try:
            redis_settings = get_redis_settings()

            # Create pool with timeout
            pool = await asyncio.wait_for(
                create_pool(redis_settings), timeout=20.0  # 20 second timeout for pool creation
            )

            try:
                # Use Job class directly with the pool
                job = Job(job_id, pool)

                # Get job status with timeout
                job_status = await asyncio.wait_for(
                    job.status(), timeout=15.0  # 15 second timeout for status check
                )

                # Map ARQ job status to our response
                status_map = {
                    JobStatus.deferred: "queued",
                    JobStatus.queued: "queued",
                    JobStatus.in_progress: "in_progress",
                    JobStatus.complete: "complete",
                    JobStatus.not_found: "not_found",
                }

                status = status_map.get(job_status, "unknown")

                if job_status == JobStatus.not_found:
                    await pool.close()
                    raise HTTPException(status_code=404, detail="Job not found")

                # Get job result if complete
                result = None
                error = None

                if job_status == JobStatus.complete:
                    try:
                        job_result = await asyncio.wait_for(
                            job.result(), timeout=10.0  # 10 second timeout for result
                        )
                        if isinstance(job_result, dict):
                            result = job_result
                        else:
                            result = {"data": job_result}
                    except asyncio.TimeoutError:
                        logger.warning(f"⏰ Timeout getting result for job {job_id}")
                        error = "Timeout retrieving job result"
                        status = "failed"
                    except Exception as e:
                        error = str(e)
                        status = "failed"
                        logger.error(f"❌ Job {job_id} failed: {error}")

                await pool.close()
                return JobStatusResponse(jobId=job_id, status=status, result=result, error=error)

            finally:
                # Ensure pool is always closed
                try:
                    await pool.close()
                except Exception as e:
                    logger.debug(f"Pool close failed (non-critical): {e}")

        except asyncio.TimeoutError:
            logger.warning(f"⏰ Timeout on attempt {attempt + 1}/{max_retries} for job {job_id}")
            if attempt == max_retries - 1:
                raise HTTPException(
                    status_code=504, detail="Timeout connecting to job queue - please try again"
                ) from None
        except Exception as e:
            logger.warning(f"🔄 Retry {attempt + 1}/{max_retries} for job {job_id}: {str(e)}")
            if attempt == max_retries - 1:
                logger.error(f"❌ All retries failed for job {job_id}: {str(e)}")
                raise HTTPException(
                    status_code=500, detail="Failed to retrieve job status after retries"
                )
        # Exponential backoff
        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay * (2**attempt))


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a background job
    Used to check contract generation progress
    Includes retry logic for Redis connectivity issues
    """
    try:
        return await get_job_status_with_retry(job_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
