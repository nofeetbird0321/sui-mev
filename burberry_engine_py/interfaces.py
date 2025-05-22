# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Abstract Base Classes (ABCs) defining the interfaces for components
within the Burberry event processing engine.
"""

import abc
from typing import Generic, TypeVar, AsyncIterator, Any # Any for dummy implementations

# --- Type Variables ---
EventType = TypeVar('EventType')
ActionType = TypeVar('ActionType')


# --- Interfaces (ABCs) ---

class CollectorInterface(abc.ABC, Generic[EventType]):
    """
    Interface for event collectors.
    Collectors are responsible for sourcing events from various inputs.
    """

    @abc.abstractmethod
    def name(self) -> str:
        """Returns the name of the collector."""
        ...

    @abc.abstractmethod
    async def get_event_stream(self) -> AsyncIterator[EventType]:
        """
        Returns an asynchronous iterator yielding events.
        """
        # For ABC, no implementation needed.
        # An actual implementation would look like:
        # yield event
        # For it to be an AsyncIterator, it needs to be an async generator.
        # So, the body for an ABC can just be pass, or raise NotImplementedError,
        # or simply ... as it's abstract.
        # To satisfy the type checker that it's an async generator, we can do:
        if False: # This code is unreachable, but makes it a generator
            yield
        ... # Or pass


class ActionSubmitterInterface(abc.ABC, Generic[ActionType]):
    """
    Interface for submitting actions that result from strategy processing.
    This interface decouples strategies from the direct execution of actions.
    """

    @abc.abstractmethod
    async def submit(self, action: ActionType) -> None:
        """
        Submits an action for execution.
        """
        ...


class StrategyInterface(abc.ABC, Generic[EventType, ActionType]):
    """
    Interface for event processing strategies.
    Strategies define the logic for how to react to incoming events.
    """

    @abc.abstractmethod
    def name(self) -> str:
        """Returns the name of the strategy."""
        ...

    @abc.abstractmethod
    async def sync_state(self, submitter: ActionSubmitterInterface[ActionType]) -> None:
        """
        Allows the strategy to synchronize its internal state.
        This might involve fetching current on-chain data or performing initial setup.
        Actions can be submitted during state synchronization if needed.
        """
        ...

    @abc.abstractmethod
    async def process_event(self, event: EventType, submitter: ActionSubmitterInterface[ActionType]) -> None:
        """
        Processes a single event and potentially submits actions.
        """
        ...


class ExecutorInterface(abc.ABC, Generic[ActionType]):
    """
    Interface for action executors.
    Executors are responsible for carrying out the actions submitted by strategies.
    """

    @abc.abstractmethod
    def name(self) -> str:
        """Returns the name of the executor."""
        ...

    @abc.abstractmethod
    async def execute(self, action: ActionType) -> None:
        """
        Executes a given action.
        """
        ...


if __name__ == '__main__':
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    # --- Dummy Event and Action Types for Demonstration ---
    @dataclasses.dataclass # Using dataclasses for dummy types
    class DummyEvent:
        data: str

    @dataclasses.dataclass
    class DummyAction:
        instruction: str

    # --- Dummy Concrete Implementations for Demonstration ---

    class MyDummyCollector(CollectorInterface[DummyEvent]):
        def name(self) -> str:
            return "MyDummyCollector"

        async def get_event_stream(self) -> AsyncIterator[DummyEvent]:
            logger.info(f"{self.name()}: Starting event stream...")
            for i in range(3):
                await asyncio.sleep(0.1) # Simulate async event arrival
                event = DummyEvent(data=f"Event number {i+1}")
                logger.info(f"{self.name()}: Yielding event: {event}")
                yield event
            logger.info(f"{self.name()}: Event stream finished.")
            # No explicit return needed for async generator if it just ends

    class MyDummyActionSubmitter(ActionSubmitterInterface[DummyAction]):
        def __init__(self, executor_name: str):
            self.executor_name = executor_name # Just for logging context

        async def submit(self, action: DummyAction) -> None:
            logger.info(f"MyDummyActionSubmitter (for {self.executor_name}): Action submitted: {action.instruction}")
            # In a real system, this might put the action on a queue for an executor.

    class MyDummyStrategy(StrategyInterface[DummyEvent, DummyAction]):
        def name(self) -> str:
            return "MyDummyStrategy"

        async def sync_state(self, submitter: ActionSubmitterInterface[DummyAction]) -> None:
            logger.info(f"{self.name()}: Syncing state...")
            await asyncio.sleep(0.1) # Simulate async work
            await submitter.submit(DummyAction(instruction="Initial sync action from strategy"))
            logger.info(f"{self.name()}: State synced.")

        async def process_event(self, event: DummyEvent, submitter: ActionSubmitterInterface[DummyAction]) -> None:
            logger.info(f"{self.name()}: Processing event: {event.data}")
            await asyncio.sleep(0.05) # Simulate processing
            action = DummyAction(instruction=f"Action for {event.data}")
            await submitter.submit(action)
            logger.info(f"{self.name()}: Event processed, action submitted.")


    class MyDummyExecutor(ExecutorInterface[DummyAction]):
        def name(self) -> str:
            return "MyDummyExecutor"

        async def execute(self, action: DummyAction) -> None:
            logger.info(f"{self.name()}: Executing action: {action.instruction}")
            await asyncio.sleep(0.2) # Simulate async execution
            logger.info(f"{self.name()}: Action '{action.instruction}' executed.")

    # --- Demonstration Logic ---
    async def main_demo():
        logger.info("--- Burberry Engine Interfaces Demonstration ---")

        # Setup components
        collector = MyDummyCollector()
        executor = MyDummyExecutor()
        
        # In a real engine, the submitter might be more complex, e.g., connected to a queue
        # or directly calling the executor if the model is simple.
        # For this demo, the submitter will just log.
        # If we wanted submitter to actually call executor, it would need a reference to it.
        # Let's make a submitter that can call our dummy executor for a more complete demo.
        class DirectCallActionSubmitter(ActionSubmitterInterface[DummyAction]):
            def __init__(self, actual_executor: ExecutorInterface[DummyAction]):
                self.actual_executor = actual_executor

            async def submit(self, action: DummyAction) -> None:
                logger.info(f"DirectCallActionSubmitter: Submitting action '{action.instruction}' to {self.actual_executor.name()}")
                await self.actual_executor.execute(action) # Directly call execute

        action_submitter = DirectCallActionSubmitter(actual_executor=executor)
        strategy = MyDummyStrategy()

        # Demonstrate Strategy's sync_state
        logger.info("\n--- Demonstrating Strategy Sync State ---")
        await strategy.sync_state(action_submitter)

        # Demonstrate Collector and Strategy event processing
        logger.info("\n--- Demonstrating Event Collection and Processing ---")
        event_count = 0
        async for event_item in collector.get_event_stream():
            event_count +=1
            await strategy.process_event(event_item, action_submitter)
        
        logger.info(f"\nProcessed {event_count} events.")
        logger.info("--- Demonstration Finished ---")

    # Need to import dataclasses for the dummy types if not already done
    import dataclasses # Add this if not at the top of the file

    if __name__ == '__main__': # Double check, standard practice
        asyncio.run(main_demo())
