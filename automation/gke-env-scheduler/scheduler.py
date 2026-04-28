"""Scheduler for automated environment management"""

import logging
import os
import sys
import time
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# Add controllers to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from controllers.orchestrator import Orchestrator
from controllers.streamlit_logger import setup_streamlit_logging

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Setup Streamlit logging handler (shared with Streamlit UI)
setup_streamlit_logging()


def main():
    """Main scheduler function"""
    logger.info("========== Starting Dev Environment Scheduler ==========")
    
    # Initialize orchestrator
    orch = Orchestrator()
    environments = orch.list_environments()
    
    if not environments:
        logger.error("No environments configured! Check your .env file.")
        sys.exit(1)
    
    logger.info(f"Managing {len(environments)} environments: {', '.join(environments)}")
    
    # Get schedule configuration
    stop_hour = int(os.getenv('SCHEDULE_STOP_HOUR', 20))
    stop_minute = int(os.getenv('SCHEDULE_STOP_MINUTE', 0))
    start_hour = int(os.getenv('SCHEDULE_START_HOUR', 7))
    start_minute = int(os.getenv('SCHEDULE_START_MINUTE', 30))
    
    # Create scheduler
    timezone = pytz.timezone('Asia/Kuala_Lumpur')
    scheduler = BlockingScheduler(timezone=timezone)
    
    logger.info(f"Timezone: {timezone}")
    logger.info(f"Stop schedule: {stop_hour}:{stop_minute:02d} (Mon-Fri)")
    logger.info(f"Start schedule: {start_hour}:{start_minute:02d} (Mon-Fri)")
    
    # Add stop jobs for each environment
    for env in environments:
        scheduler.add_job(
            func=lambda e=env: stop_environment_job(orch, e),
            trigger=CronTrigger(
                day_of_week='mon-fri',
                hour=stop_hour,
                minute=stop_minute,
                timezone=timezone
            ),
            id=f'stop_{env}',
            name=f'Stop {env}',
            replace_existing=True
        )
        logger.info(f"✅ Scheduled stop job for {env}")
    
    # Add start jobs for each environment
    for env in environments:
        scheduler.add_job(
            func=lambda e=env: start_environment_job(orch, e),
            trigger=CronTrigger(
                day_of_week='mon-fri',
                hour=start_hour,
                minute=start_minute,
                timezone=timezone
            ),
            id=f'start_{env}',
            name=f'Start {env}',
            replace_existing=True
        )
        logger.info(f"✅ Scheduled start job for {env}")
    
    logger.info("🚀 Scheduler is now running. Press Ctrl+C to exit.")
    logger.info(f"Scheduled {len(scheduler.get_jobs())} jobs (stop and start for {len(environments)} environments)")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("\n========== Shutting down scheduler ==========")
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def stop_environment_job(orch: Orchestrator, env_name: str):
    """Job function to stop an environment"""
    logger.info(f"\n{'='*60}")
    logger.info(f"🌙 SCHEDULED STOP TRIGGERED: {env_name}")
    logger.info(f"{'='*60}\n")
    
    try:
        result = orch.stop_environment(env_name)
        
        if result.get('success'):
            logger.info(f"✅ Successfully stopped {env_name}")
        else:
            logger.error(f"❌ Failed to stop {env_name}: {result.get('error')}")
            
        # Log step results
        for step in result.get('steps', []):
            step_name = step['step']
            step_result = step['result']
            if step_result.get('success'):
                logger.info(f"  ✅ {step_name}")
            else:
                logger.error(f"  ❌ {step_name}: {step_result.get('error')}")
                
    except Exception as e:
        logger.error(f"❌ Exception while stopping {env_name}: {e}", exc_info=True)


def start_environment_job(orch: Orchestrator, env_name: str):
    """Job function to start an environment"""
    logger.info(f"\n{'='*60}")
    logger.info(f"🌅 SCHEDULED START TRIGGERED: {env_name}")
    logger.info(f"{'='*60}\n")
    
    try:
        result = orch.start_environment(env_name)
        
        if result.get('success'):
            logger.info(f"✅ Successfully started {env_name}")
        else:
            logger.error(f"❌ Failed to start {env_name}: {result.get('error')}")
            
        # Log step results
        for step in result.get('steps', []):
            step_name = step['step']
            step_result = step['result']
            if step_result.get('success'):
                logger.info(f"  ✅ {step_name}")
            else:
                logger.error(f"  ❌ {step_name}: {step_result.get('error')}")
                
    except Exception as e:
        logger.error(f"❌ Exception while starting {env_name}: {e}", exc_info=True)


if __name__ == '__main__':
    main()
