#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# quick start script untuk hybrid processor

import sys
import logging
import os

# fix Windows console encoding
if os.name == 'nt':  # Windows
    try:
        # set console to UTF-8
        os.system('chcp 65001 > nul')
    except:
        pass

# setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger("skyguard")

banner = """
======================================================================
   SKYGUARD HYBRID PROCESSOR
======================================================================
   Combining:
   - NLP Sentiment Analysis (Transformers/RoBERTa)
   - Regional Risk Scoring (Contextual)
   - Time-Window Correlation (2-hour stateful join)
   - Hybrid Alert Logic (YELLOW -> RED confirmation)
======================================================================
"""

print(banner)

try:
    # fix import path - bisa run dari root atau dari dalam folder
    try:
        from computer2_preprocessing.news_intelligence import HybridProcessor
    except ModuleNotFoundError:
        from news_intelligence import HybridProcessor
    
    logger.info("Initializing Hybrid Processor...")
    logger.info("")
    logger.info("Features:")
    logger.info("  1. Contextual Risk Scoring")
    logger.info("     -> Regional sentiment dari news 24h terakhir")
    logger.info("     -> Baseline risk per region (Asia)")
    logger.info("")
    logger.info("  2. Time-Window Confirmation")
    logger.info("     -> Flight anomaly -> YELLOW (wait)")
    logger.info("     -> News arrives within 2h -> RED (confirmed!)")
    logger.info("")
    logger.info("  3. Hybrid Alert Logic")
    logger.info("     -> GREEN: Normal")
    logger.info("     -> YELLOW: Early warning (hot zone OR small anomaly)")
    logger.info("     -> RED: Confirmed threat (anomaly + news)")
    logger.info("")
    
    processor = HybridProcessor()
    processor.start_processing()

except KeyboardInterrupt:
    logger.info("\nShutting down...")
    sys.exit(0)
except Exception as e:
    logger.error(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
