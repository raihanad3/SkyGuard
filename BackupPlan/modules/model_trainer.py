"""
Model Trainer (Placeholder untuk future ML integration)
Saat ini pakai rule-based, tapi structure siap untuk ML model.
"""

import logging
import asyncio

logger = logging.getLogger("skyguard")


class ModelTrainer:
    """Train dan maintain anomaly detection model (future ML)."""
    
    def __init__(self, detector, database):
        self.detector = detector
        self.db = database
        self.running = False
    
    async def initial_training_check(self):
        """Check if model needs initial training."""
        logger.info("📊 Model trainer: Using rule-based detection (no ML training needed)")
        await asyncio.sleep(1)
    
    async def start_periodic_training(self):
        """Periodic retraining (placeholder for future ML)."""
        self.running = True
        
        while self.running:
            await asyncio.sleep(21600)  # 6 hours
            
            if not self.running:
                break
            
            logger.info("📊 Model trainer: Checking for updates (rule-based system)")
    
    def stop(self):
        """Stop trainer."""
        self.running = False
