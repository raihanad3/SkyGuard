# news intelligence module
# implements hybrid approach: contextual risk + time-window confirmation

from .sentiment_processor import NewsSentimentProcessor
from .hybrid_processor import HybridProcessor
from .spark_correlator import SparkNewsCorrelator, create_spark_session

__all__ = [
    "NewsSentimentProcessor",
    "HybridProcessor", 
    "SparkNewsCorrelator",
    "create_spark_session"
]
