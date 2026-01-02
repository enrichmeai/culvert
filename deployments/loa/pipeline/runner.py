"""
LOA Pipeline Runner.

Entry point for running LOA Beam pipelines.
"""

import logging
from datetime import datetime

from .loa_pipeline import run_loa_pipeline
from .options import LOAPipelineOptions

logger = logging.getLogger(__name__)


def run(argv=None):
    """
    Run the LOA ODP load pipeline.

    This is the main entry point for the LOA pipeline.
    After completion, FDP transformation can be triggered immediately
    (no dependency wait - single entity).

    Args:
        argv: Command-line arguments
    """
    run_loa_pipeline(argv)


def main():
    """Main entry point when run as script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    run()


if __name__ == '__main__':
    main()

