# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Core components of the Burberry event processing engine, including the main Engine class.
"""

import asyncio
import logging
from typing import Any, Dict, Generic, List, TypeVar, Optional

from burberry_engine_py.interfaces import (
    ActionSubmitterInterface,
    CollectorInterface,
    ExecutorInterface,
    StrategyInterface,
    EventType, # Re-exporting for convenience if needed by users of Engine
    ActionType # Re-exporting
)

# TypeVars used internally by Engine, can be shadowed by those from interfaces
_EventType = TypeVar('_EventType')
_ActionType = TypeVar('_ActionType')


class ActionSubmitter(ActionSubmitterInterface[_ActionType]):
    """
    Concrete implementation of ActionSubmitterInterface that puts actions onto an asyncio Queue.
    """
    def __init__(self, action_queue: asyncio.Queue[_ActionType]):
        """
        Initializes the ActionSubmitter.

        Args:
            action_queue: The asyncio.Queue to which actions will be submitted.
        """
        self._action_queue = action_queue
        self.logger = logging.getLogger(__name__)

    async def submit(self, action: _ActionType) -> None:
        """
        Puts the given action onto the action queue.
        """
        await self._action_queue.put(action)
        self.logger.debug(f"Action submitted to queue: {action}")


class Engine(Generic[_EventType, _ActionType]):
    """
    The main Burberry engine, orchestrating collectors, strategies, and executors.
    """
    def __init__(self):
        self.collectors: List[CollectorInterface[_EventType]] = []
        self.strategies: List[StrategyInterface[_EventType, _ActionType]] = []
        # Key for executors can be action class type or a string name (e.g., action.__class__)
        self.executors: Dict[Any, ExecutorInterface[_ActionType]] = {}
        
        self.event_queue: asyncio.Queue[_EventType] = asyncio.Queue()
        self.action_queue: asyncio.Queue[_ActionType] = asyncio.Queue()
        
        self.action_submitter: ActionSubmitter[_ActionType] = ActionSubmitter(self.action_queue)
        
        self.logger = logging.getLogger(__name__)
        self._running_tasks: List[asyncio.Task[Any]] = [] # To keep track of background tasks

    def add_collector(self, collector: CollectorInterface[_EventType]) -> None:
        """Adds a collector to the engine."""
        self.collectors.append(collector)
        self.logger.info(f"Added collector: {collector.name()}")

    def add_strategy(self, strategy: StrategyInterface[_EventType, _ActionType]) -> None:
        """Adds a strategy to the engine."""
        self.strategies.append(strategy)
        self.logger.info(f"Added strategy: {strategy.name()}")

    def add_executor(self, action_key: Any, executor: ExecutorInterface[_ActionType]) -> None:
        """
        Registers an executor for a specific action key.
        The action_key is typically the class of the action it handles (e.g., `MyActionClass`).
        """
        if action_key in self.executors:
            self.logger.warning(f"Executor for action key '{action_key}' already exists. Overwriting.")
        self.executors[action_key] = executor
        self.logger.info(f"Added executor '{executor.name()}' for action key '{action_key}'")

    async def _process_collector_stream(self, collector: CollectorInterface[_EventType]) -> None:
        """
        Helper to iterate one collector's event stream and put events onto the engine's event_queue.
        """
        self.logger.info(f"Starting event stream for collector: {collector.name()}")
        try:
            async for event in collector.get_event_stream():
                await self.event_queue.put(event)
                self.logger.debug(f"Event from {collector.name()} put on queue: {event}")
        except Exception as e:
            self.logger.error(f"Error in collector '{collector.name()}': {e}", exc_info=True)
            # Depending on desired behavior, could re-raise or signal engine shutdown.
        finally:
            self.logger.info(f"Collector '{collector.name()}' stream finished or errored.")


    async def _run_collectors(self) -> None:
        """
        Creates and runs tasks for all registered collectors to stream events.
        """
        if not self.collectors:
            self.logger.warning("No collectors registered. Event processing will not occur.")
            return

        collector_tasks = [
            asyncio.create_task(self._process_collector_stream(collector), name=f"Collector-{collector.name()}")
            for collector in self.collectors
        ]
        await asyncio.gather(*collector_tasks, return_exceptions=True)
        # If gather finishes, it means all collectors have completed (or one errored badly enough to stop gather).
        self.logger.info("All collector tasks finished.")


    async def _run_strategies(self) -> None:
        """
        Initializes strategies via sync_state and then continuously processes events from the event_queue.
        """
        if not self.strategies:
            self.logger.warning("No strategies registered. Events will not be processed.")
            return

        self.logger.info("Syncing state for all strategies...")
        sync_tasks = [
            asyncio.create_task(strategy.sync_state(self.action_submitter), name=f"Sync-{strategy.name()}")
            for strategy in self.strategies
        ]
        try:
            await asyncio.gather(*sync_tasks, return_exceptions=True) # Allow all to sync
        except Exception as e: # Should not happen if return_exceptions=True
            self.logger.error(f"Error during strategy state synchronization: {e}", exc_info=True)
            # Decide if engine should stop or continue if a strategy fails to sync.
            # For now, it continues.
        
        self.logger.info("All strategies synced. Starting event processing loop...")
        while True: # Loop indefinitely until this task is cancelled
            try:
                event = await self.event_queue.get()
                self.logger.debug(f"Processing event from queue: {event}")
                
                # Process event with all strategies concurrently
                process_tasks = [
                    asyncio.create_task(strategy.process_event(event, self.action_submitter), name=f"Process-{strategy.name()}-{type(event)}")
                    for strategy in self.strategies
                ]
                await asyncio.gather(*process_tasks, return_exceptions=True) # Allow all to process
                self.event_queue.task_done() # Signal that this event is processed
            except asyncio.CancelledError:
                self.logger.info("Strategy runner task cancelled. Exiting event processing loop.")
                break
            except Exception as e:
                self.logger.error(f"Error in strategy event processing loop: {e}", exc_info=True)
                # Avoid breaking the loop for a single event processing error, log and continue.
                # If event_queue.get() itself fails critically, the loop might break.
                await asyncio.sleep(1) # Avoid tight loop on persistent errors if queue remains problematic


    async def _run_executors(self) -> None:
        """
        Continuously processes actions from the action_queue and dispatches them to registered executors.
        """
        if not self.executors:
            self.logger.warning("No executors registered. Actions will accumulate in queue but not be executed.")
            # We can still run the loop to drain the queue and log, or just return.
            # For now, let it run and log missing executors.

        self.logger.info("Starting action execution loop...")
        while True: # Loop indefinitely until this task is cancelled
            try:
                action = await self.action_queue.get()
                self.logger.debug(f"Processing action from queue: {action} (type: {type(action)})")
                
                action_key = type(action) # Use the class of the action object as the key
                executor = self.executors.get(action_key)
                
                if executor:
                    try:
                        await executor.execute(action)
                        self.logger.debug(f"Action executed by {executor.name()}: {action}")
                    except Exception as e:
                        self.logger.error(f"Executor {executor.name()} failed to execute action {action}: {e}", exc_info=True)
                        # Optionally, implement retry logic or dead-letter queue for actions
                else:
                    self.logger.warning(f"No executor found for action key '{action_key}' (action: {action}). Action dropped.")
                
                self.action_queue.task_done() # Signal that this action is processed
            except asyncio.CancelledError:
                self.logger.info("Executor runner task cancelled. Exiting action processing loop.")
                break
            except Exception as e:
                self.logger.error(f"Error in executor action processing loop: {e}", exc_info=True)
                await asyncio.sleep(1) # Avoid tight loop


    async def start(self) -> None:
        """
        Starts the engine by creating and scheduling tasks for collectors, strategies, and executors.
        """
        self.logger.info("Starting Burberry Engine...")
        if self._running_tasks:
            self.logger.warning("Engine already started or tasks list not empty. Aborting start.")
            return

        self._running_tasks.append(asyncio.create_task(self._run_collectors(), name="Engine-CollectorsRunner"))
        self._running_tasks.append(asyncio.create_task(self._run_strategies(), name="Engine-StrategiesRunner"))
        self._running_tasks.append(asyncio.create_task(self._run_executors(), name="Engine-ExecutorsRunner"))
        
        self.logger.info(f"Engine started with {len(self._running_tasks)} main tasks.")


    async def stop(self) -> None:
        """
        Stops the engine by cancelling all running tasks and waiting for them to finish.
        """
        self.logger.info("Stopping Burberry Engine...")
        if not self._running_tasks:
            self.logger.info("No tasks to stop.")
            return

        for task in self._running_tasks:
            if not task.done():
                task.cancel()
                self.logger.debug(f"Cancelled task: {task.get_name()}")

        results = await asyncio.gather(*self._running_tasks, return_exceptions=True)
        self.logger.info("All engine tasks finished or cancelled.")
        
        for i, result in enumerate(results):
            task_name = self._running_tasks[i].get_name()
            if isinstance(result, asyncio.CancelledError):
                self.logger.debug(f"Task {task_name} was cancelled successfully.")
            elif isinstance(result, Exception):
                self.logger.error(f"Task {task_name} raised an exception during stop: {result}", exc_info=result)
            else:
                 self.logger.debug(f"Task {task_name} completed with result: {result}")


        self._running_tasks.clear()
        self.logger.info("Burberry Engine stopped.")


    async def run_forever(self) -> None:
        """
        Starts the engine and waits for its main tasks to complete or be cancelled.
        This is the primary method to run the engine.
        """
        await self.start()
        if self._running_tasks:
            # Wait for all main tasks to complete.
            # If one task errors out and isn't handled internally to keep it alive,
            # asyncio.gather will propagate the exception here.
            try:
                await asyncio.gather(*self._running_tasks, return_exceptions=False) # Propagate first exception
            except Exception as e:
                self.logger.error(f"A critical engine task failed: {e}", exc_info=True)
                self.logger.info("Engine run_forever loop is terminating due to task failure. Initiating stop...")
                # Ensure other tasks are cleaned up
                await self.stop() 
                raise # Re-raise the critical exception after attempting cleanup
            finally:
                 self.logger.info("Engine run_forever loop completed.")
        else:
            self.logger.warning("Engine run_forever called, but no tasks were started (e.g. no collectors). Engine will not run.")


if __name__ == '__main__':
    import dataclasses
    from typing import AsyncIterator # Needed for dummy collector

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    engine_logger = logging.getLogger("burberry_engine_py.core") # Specific logger for engine
    engine_logger.setLevel(logging.DEBUG)


    # --- Dummy Event and Action Types for Demonstration (Simplified from interfaces.py demo) ---
    @dataclasses.dataclass
    class DemoEvent:
        id: int
        data: str

    @dataclasses.dataclass
    class DemoAction:
        origin_event_id: int
        instruction: str

    # --- Dummy Concrete Implementations ---
    class DemoCollector(CollectorInterface[DemoEvent]):
        def __init__(self, name: str, num_events: int = 3, delay: float = 0.5):
            self._name = name
            self.num_events = num_events
            self.delay = delay
            self.logger = logging.getLogger(f"{__name__}.{self._name}")

        def name(self) -> str:
            return self._name

        async def get_event_stream(self) -> AsyncIterator[DemoEvent]:
            self.logger.info("Starting event stream...")
            for i in range(self.num_events):
                await asyncio.sleep(self.delay)
                event = DemoEvent(id=i, data=f"Event data {i} from {self.name()}")
                self.logger.debug(f"Yielding event: {event}")
                yield event
            self.logger.info("Event stream finished.")

    class DemoStrategy(StrategyInterface[DemoEvent, DemoAction]):
        def __init__(self, name: str):
            self._name = name
            self.logger = logging.getLogger(f"{__name__}.{self._name}")

        def name(self) -> str:
            return self._name

        async def sync_state(self, submitter: ActionSubmitterInterface[DemoAction]) -> None:
            self.logger.info("Syncing state...")
            await asyncio.sleep(0.1)
            await submitter.submit(DemoAction(origin_event_id=-1, instruction="Initial sync action"))
            self.logger.info("State synced.")

        async def process_event(self, event: DemoEvent, submitter: ActionSubmitterInterface[DemoAction]) -> None:
            self.logger.info(f"Processing event: {event}")
            await asyncio.sleep(0.05)
            action = DemoAction(origin_event_id=event.id, instruction=f"Action for event '{event.data}'")
            await submitter.submit(action)
            self.logger.debug(f"Submitted action for event {event.id}")

    class DemoExecutor(ExecutorInterface[DemoAction]):
        def __init__(self, name: str):
            self._name = name
            self.processed_action_count = 0
            self.logger = logging.getLogger(f"{__name__}.{self._name}")

        def name(self) -> str:
            return self._name

        async def execute(self, action: DemoAction) -> None:
            self.logger.info(f"Executing action: {action}")
            await asyncio.sleep(0.2) # Simulate work
            self.processed_action_count += 1
            self.logger.debug(f"Action executed: {action.instruction}")


    async def main_engine_demo():
        engine_logger.info("--- Burberry Engine Core Demonstration ---")

        # Instantiate the engine
        engine = Engine[DemoEvent, DemoAction]()

        # Instantiate and add components
        collector1 = DemoCollector(name="Collector-Alpha", num_events=2, delay=0.3)
        collector2 = DemoCollector(name="Collector-Beta", num_events=3, delay=0.4)
        engine.add_collector(collector1)
        engine.add_collector(collector2)

        strategy1 = DemoStrategy(name="Strategy-Main")
        engine.add_strategy(strategy1)
        
        # Executor for DemoAction type
        executor1 = DemoExecutor(name="Executor-Primary")
        engine.add_executor(DemoAction, executor1) # Registering by class type

        # Start the engine and let it run for a bit
        engine_logger.info("Starting engine via run_forever()...")
        
        engine_run_task = asyncio.create_task(engine.run_forever())

        # Let the engine run for a certain duration for the demo
        # Or wait for a certain number of actions to be processed by the executor
        total_expected_events = collector1.num_events + collector2.num_events
        # Each event -> 1 action. Sync state -> 1 action. Total actions = total_expected_events + 1 (for sync)
        total_expected_actions = total_expected_events + 1 

        try:
            # Wait until the executor has processed enough actions or a timeout
            timeout_seconds = 10.0 
            start_time = asyncio.get_event_loop().time()
            while executor1.processed_action_count < total_expected_actions:
                if (asyncio.get_event_loop().time() - start_time) > timeout_seconds:
                    engine_logger.warning("Demo timeout reached. Stopping engine.")
                    break
                await asyncio.sleep(0.1)
            
            if executor1.processed_action_count >= total_expected_actions:
                engine_logger.info(f"All {total_expected_actions} expected actions processed by executor.")

        except Exception as e:
            engine_logger.error(f"Error during demo execution: {e}", exc_info=True)
        finally:
            engine_logger.info("Stopping engine from demo...")
            await engine.stop() # Gracefully stop the engine
            # Wait for the run_forever task to complete after stop has been called
            # This ensures that if run_forever exited due to an error, we still see it.
            await engine_run_task 
            engine_logger.info("Engine demo finished.")

    asyncio.run(main_engine_demo())
