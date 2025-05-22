# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Event collectors for the DEX indexer.
"""

import asyncio
import logging
from typing import AsyncIterator

# Assuming burberry_engine_py is installed or in PYTHONPATH
from burberry_engine_py.interfaces import CollectorInterface

# Relative import for Event type, assuming collectors.py is in dex_indexer_py/
# and types.py is in dex_indexer_py/ (i.e., dex_indexer_py.types)
from .types import Event # Use .types for relative import within the same package level

logger = logging.getLogger(__name__)

class QueryEventCollector(CollectorInterface[Event]):
    """
    A collector that periodically yields a QUERY_EVENT_TRIGGER event.
    This mimics a timer-based trigger for querying data.
    """

    def __init__(self, tick_interval_seconds: float = 10.0):
        """
        Initializes the QueryEventCollector.

        Args:
            tick_interval_seconds: The interval in seconds between yielding
                                   QUERY_EVENT_TRIGGER events.
        """
        if tick_interval_seconds <= 0:
            raise ValueError("tick_interval_seconds must be positive.")
        self.tick_interval_seconds: float = tick_interval_seconds
        logger.info(f"QueryEventCollector initialized with tick interval: {self.tick_interval_seconds}s")

    def name(self) -> str:
        """Returns the name of the collector."""
        return "QueryEventCollector"

    async def get_event_stream(self) -> AsyncIterator[Event]:
        """
        Asynchronously yields QUERY_EVENT_TRIGGER events at the specified interval.
        Includes an initial delay equal to tick_interval_seconds.
        """
        logger.info(f"{self.name()}: Starting event stream. Initial delay of {self.tick_interval_seconds}s...")
        # Initial delay, similar to interval_at behavior in Rust that has an initial delay.
        await asyncio.sleep(self.tick_interval_seconds)
        
        loop_count = 0
        try:
            while True:
                loop_count += 1
                logger.debug(f"{self.name()}: Yielding {Event.QUERY_EVENT_TRIGGER} (Tick #{loop_count})")
                yield Event.QUERY_EVENT_TRIGGER
                logger.debug(f"{self.name()}: Sleeping for {self.tick_interval_seconds}s before next tick.")
                await asyncio.sleep(self.tick_interval_seconds)
        except asyncio.CancelledError:
            logger.info(f"{self.name()}: Event stream cancelled after {loop_count} ticks.")
            # Propagate cancellation if needed, or just exit.
            # For an async generator, allowing it to exit is standard on cancellation.
        except Exception as e:
            logger.error(f"{self.name()}: Error in event stream after {loop_count} ticks: {e}", exc_info=True)
            # Depending on policy, may re-raise or terminate stream.
        finally:
            logger.info(f"{self.name()}: Event stream finished or terminated.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    async def demo_query_event_collector():
        logger.info("--- QueryEventCollector Demonstration ---")
        
        # Test with a short interval for quick demo
        collector = QueryEventCollector(tick_interval_seconds=1.5)
        logger.info(f"Collector Name: {collector.name()}")

        event_count = 0
        max_events_to_collect = 4 # Limit how many events we collect for the demo

        logger.info(f"Starting to collect events (max {max_events_to_collect})...")
        try:
            async for event_item in collector.get_event_stream():
                logger.info(f"Demo: Received event: {event_item} (type: {type(event_item)})")
                event_count += 1
                if event_count >= max_events_to_collect:
                    logger.info(f"Demo: Collected {event_count} events. Stopping.")
                    break
        except Exception as e:
            logger.error(f"Demo: An error occurred during event collection: {e}", exc_info=True)
        
        logger.info(f"--- QueryEventCollector Demonstration Finished (Collected {event_count} events) ---")

    asyncio.run(demo_query_event_collector())
