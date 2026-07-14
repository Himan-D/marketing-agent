import asyncio
import logging
from datetime import datetime
from arq import create_pool
from arq.connections import RedisSettings
from app.config import settings
from app.api.deps import async_session
from app.agents.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


async def send_campaign_email(ctx, lead_id, log_id, campaign_id):
    async with async_session() as db:
        orch = Orchestrator(db)
        try:
            success = await orch.process_email(lead_id, log_id)
            if success:
                logger.info("Email sent for lead %s", lead_id)
            else:
                logger.warning("Failed to send email for lead %s", lead_id)
            return success
        finally:
            await orch.close()


class WorkerSettings:
    functions = [send_campaign_email]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    poll_delay = 5
    max_jobs = 10
    job_timeout = 120
    keep_result_seconds = 86400


async def main():
    pool = await create_pool(WorkerSettings.redis_settings)
    logger.info("ARQ worker started, listening for jobs...")
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("Worker shutting down...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
