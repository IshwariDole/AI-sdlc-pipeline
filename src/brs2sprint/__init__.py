"""brs2sprint — BRS document to SRS, design, tickets and a sprint plan."""

__version__ = "0.1.0"

from .config import settings
from .llm import get_client
from .pipeline import PipelineOptions, run_pipeline

__all__ = ["settings", "get_client", "run_pipeline", "PipelineOptions", "__version__"]
