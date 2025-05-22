# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Python type definitions for the Arb Bot, mirroring enums and structs
from bin/arb/src/types.rs.
"""

import dataclasses
import time
from typing import Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from shio_client_py.types import ShioItem # For type hinting ShioFeedEvent.item

# --- ArbAction Hierarchy ---

@dataclasses.dataclass(frozen=True)
class ArbAction:
    """Base class for actions the Arb Bot can take."""
    pass

@dataclasses.dataclass(frozen=True)
class NotifyViaTelegram(ArbAction):
    """Action to send a notification via Telegram."""
    message_payload: Any # Placeholder for actual message structure/type

@dataclasses.dataclass(frozen=True)
class ExecutePublicTx(ArbAction):
    """Action to execute a public transaction."""
    tx_data: Any # Placeholder for pysui TransactionData or similar

@dataclasses.dataclass(frozen=True)
class ShioSubmitBid(ArbAction):
    """Action to submit a bid to Shio."""
    tx_data: Any # Placeholder for pysui TransactionData or similar
    bid_amount: int
    opp_tx_digest: str


# --- ArbEvent Hierarchy ---

@dataclasses.dataclass(frozen=True)
class ArbEvent:
    """Base class for events processed by the Arb Bot."""
    pass

@dataclasses.dataclass(frozen=True)
class PublicTxEvent(ArbEvent):
    """Event representing a public transaction observed on-chain."""
    effects: Any # Placeholder for SuiTransactionBlockEffects
    sui_events: List[Any] = dataclasses.field(default_factory=list) # Placeholder for SuiEvent list

@dataclasses.dataclass(frozen=True)
class PrivateTxEvent(ArbEvent):
    """Event representing a private transaction (e.g., from a specific builder)."""
    tx_data: Any # Placeholder for transaction data

@dataclasses.dataclass(frozen=True)
class ShioFeedEvent(ArbEvent):
    """Event representing an item received from the Shio feed."""
    item: 'ShioItem'


# --- OpportunitySource Hierarchy ---

@dataclasses.dataclass(frozen=True)
class OpportunitySource:
    """Base class for the source of an arbitrage opportunity."""

    def is_shio(self) -> bool:
        """Returns True if the source is Shio-related."""
        return isinstance(self, (ShioSource, ShioDeadlineMissedSource))

    def get_opp_tx_digest(self) -> Optional[str]:
        """Returns the opportunity transaction digest if applicable."""
        if isinstance(self, ShioSource):
            return self.opp_tx_digest
        return None

    def get_deadline(self) -> Optional[int]:
        """Returns the deadline timestamp in ms if applicable."""
        if isinstance(self, (ShioSource, ShioDeadlineMissedSource)):
            return self.deadline_ms
        return None

    def get_bid_amount(self) -> int:
        """Returns the bid amount if applicable, otherwise 0."""
        if isinstance(self, ShioSource):
            return self.bid_amount
        return 0 # PublicSource and ShioDeadlineMissedSource don't have a bid amount directly

    def with_bid_amount(self, bid_amount: int) -> 'OpportunitySource':
        """
        Returns a new instance with the bid_amount updated.
        Only applicable to ShioSource. Other types return self.
        """
        if isinstance(self, ShioSource):
            # Use dataclasses.replace for frozen dataclasses
            return dataclasses.replace(self, bid_amount=bid_amount)
        # For PublicSource or ShioDeadlineMissedSource, bid_amount is not a direct field,
        # so creating a new instance with it doesn't make sense within this model.
        # The Rust code implies it might transition or hold it temporarily,
        # but Python's frozen dataclasses make this pattern a bit different.
        # For now, returning self for non-ShioSource.
        return self

    def with_arb_found_time(self, arb_found_ms: int) -> 'OpportunitySource':
        """
        Returns a new instance with arb_found_time_ms updated.
        If called on ShioSource, it transitions to ShioDeadlineMissedSource
        if the deadline has passed relative to arb_found_ms.
        """
        current_time_ms = int(time.time() * 1000) # Using time.time() for simplicity

        if isinstance(self, ShioSource):
            # Check if deadline missed based on arb_found_ms
            if arb_found_ms > self.deadline_ms:
                return ShioDeadlineMissedSource(
                    start_time_ms=self.start_time_ms,
                    arb_found_time_ms=arb_found_ms,
                    deadline_ms=self.deadline_ms
                )
            # If not missed, update arb_found_time_ms on a new ShioSource instance
            return dataclasses.replace(self, arb_found_time_ms=arb_found_ms)
        
        elif isinstance(self, ShioDeadlineMissedSource):
            # Update arb_found_time_ms on a new ShioDeadlineMissedSource instance
            return dataclasses.replace(self, arb_found_time_ms=arb_found_ms)
        
        # PublicSource doesn't have these time fields.
        return self
        
    def __str__(self) -> str:
        return self.__class__.__name__ # Default string representation


@dataclasses.dataclass(frozen=True)
class PublicSource(OpportunitySource):
    """Opportunity sourced from public on-chain data."""
    # No extra fields
    pass # __str__ will be "PublicSource" from base

@dataclasses.dataclass(frozen=True)
class ShioSource(OpportunitySource):
    """Opportunity sourced from Shio feed, before deadline."""
    opp_tx_digest: str
    bid_amount: int
    start_time_ms: int
    arb_found_time_ms: int # Time when arbitrage was found by the bot
    deadline_ms: int

    def __str__(self) -> str:
        time_now_ms = int(time.time() * 1000)
        time_to_deadline_ms = self.deadline_ms - time_now_ms
        return (
            f"ShioSource(opp_tx_digest='{self.opp_tx_digest}', bid={self.bid_amount}, "
            f"start_time={self.start_time_ms}, arb_found_time={self.arb_found_time_ms}, "
            f"deadline={self.deadline_ms}, time_to_deadline_ms={time_to_deadline_ms})"
        )

@dataclasses.dataclass(frozen=True)
class ShioDeadlineMissedSource(OpportunitySource):
    """Opportunity sourced from Shio feed, after deadline has passed."""
    start_time_ms: int
    arb_found_time_ms: int
    deadline_ms: int
    
    def __str__(self) -> str:
        return (
            f"ShioDeadlineMissedSource(start_time={self.start_time_ms}, "
            f"arb_found_time={self.arb_found_time_ms}, deadline={self.deadline_ms})"
        )


if __name__ == '__main__':
    from shio_client_py.types import AuctionStarted, SideEffects # For ShioFeedEvent demo

    print("--- Testing ArbAction Hierarchy ---")
    notify_action = NotifyViaTelegram(message_payload={"text": "Hello!"})
    public_tx_action = ExecutePublicTx(tx_data="dummy_tx_data_for_public_exec")
    shio_bid_action = ShioSubmitBid(tx_data="dummy_tx_data_for_shio", bid_amount=100, opp_tx_digest="shio_opp_digest_123")
    
    print(f"Notify Action: {notify_action}")
    print(f"Public Tx Action: {public_tx_action}")
    print(f"Shio Bid Action: {shio_bid_action}")
    assert isinstance(notify_action, ArbAction)

    print("\n--- Testing ArbEvent Hierarchy ---")
    # Dummy ShioItem for ShioFeedEvent
    # In a real scenario, AuctionStarted would have more complex SideEffects
    dummy_shio_item_auction_started = AuctionStarted(
        tx_digest_val="shio_tx_digest", gas_price_val=1000, 
        deadline_timestamp_ms_val=int(time.time() * 1000) + 60000, # Deadline in 60s
        side_effects=SideEffects() # Empty side effects for this dummy
    )

    public_event = PublicTxEvent(effects={"status": "success"}, sui_events=[{"type": "0x2::sui::CoinBalanceChangeEvent"}])
    private_event = PrivateTxEvent(tx_data="private_tx_payload")
    shio_event = ShioFeedEvent(item=dummy_shio_item_auction_started)

    print(f"Public Tx Event: {public_event}")
    print(f"Private Tx Event: {private_event}")
    print(f"Shio Feed Event: item_type='{shio_event.item.type_name()}', tx_digest='{shio_event.item.tx_digest()}'")
    assert isinstance(shio_event, ArbEvent)
    assert public_event.sui_events[0]['type'] == "0x2::sui::CoinBalanceChangeEvent"


    print("\n--- Testing OpportunitySource Hierarchy ---")
    current_ms = int(time.time() * 1000)
    
    public_src = PublicSource()
    shio_src_active = ShioSource(
        opp_tx_digest="shio_opp_abc", 
        bid_amount=100, 
        start_time_ms=current_ms - 10000, # Started 10s ago
        arb_found_time_ms=current_ms - 1000, # Arb found 1s ago
        deadline_ms=current_ms + 20000  # Deadline in 20s
    )
    shio_src_deadline_passed_initially = ShioSource(
        opp_tx_digest="shio_opp_def", 
        bid_amount=150, 
        start_time_ms=current_ms - 30000, # Started 30s ago
        arb_found_time_ms=current_ms - 1000, # Arb found 1s ago
        deadline_ms=current_ms - 5000  # Deadline was 5s ago
    )

    print(f"Public Source: {public_src}, is_shio: {public_src.is_shio()}")
    assert not public_src.is_shio()
    assert public_src.get_opp_tx_digest() is None
    assert public_src.get_deadline() is None
    assert public_src.get_bid_amount() == 0

    print(f"Shio Source (Active): {shio_src_active}, is_shio: {shio_src_active.is_shio()}")
    assert shio_src_active.is_shio()
    assert shio_src_active.get_opp_tx_digest() == "shio_opp_abc"
    assert shio_src_active.get_deadline() == current_ms + 20000
    assert shio_src_active.get_bid_amount() == 100

    # Test with_bid_amount
    shio_src_new_bid = shio_src_active.with_bid_amount(120)
    print(f"Shio Source (New Bid): {shio_src_new_bid}")
    assert shio_src_new_bid.get_bid_amount() == 120 # type: ignore
    assert shio_src_new_bid.opp_tx_digest == shio_src_active.opp_tx_digest # type: ignore

    public_src_new_bid = public_src.with_bid_amount(50) # Should return self
    print(f"Public Source (Try New Bid): {public_src_new_bid}")
    assert public_src_new_bid.get_bid_amount() == 0


    # Test with_arb_found_time and transition to ShioDeadlineMissedSource
    print(f"\nTesting with_arb_found_time transitions:")
    # Scenario 1: ShioSource, arb_found_time is before deadline
    arb_found_early_ms = current_ms + 5000 # Arb found, still 15s to deadline
    shio_src_updated_arb_time = shio_src_active.with_arb_found_time(arb_found_early_ms)
    print(f"  ShioSource (arb_found_early): {shio_src_updated_arb_time}")
    assert isinstance(shio_src_updated_arb_time, ShioSource)
    assert shio_src_updated_arb_time.arb_found_time_ms == arb_found_early_ms # type: ignore

    # Scenario 2: ShioSource, arb_found_time is after deadline -> transitions
    arb_found_late_ms = current_ms + 25000 # Arb found, but 5s after deadline
    shio_src_transitioned = shio_src_active.with_arb_found_time(arb_found_late_ms)
    print(f"  ShioSource (arb_found_late, transitioned): {shio_src_transitioned}")
    assert isinstance(shio_src_transitioned, ShioDeadlineMissedSource)
    assert shio_src_transitioned.arb_found_time_ms == arb_found_late_ms # type: ignore
    assert shio_src_transitioned.deadline_ms == shio_src_active.deadline_ms # type: ignore
    assert shio_src_transitioned.get_opp_tx_digest() is None # DeadlineMissed doesn't carry opp_tx_digest

    # Scenario 3: ShioDeadlineMissedSource, arb_found_time updated
    missed_src_initial = ShioDeadlineMissedSource(
        start_time_ms=current_ms - 20000,
        arb_found_time_ms=current_ms - 1000, # original arb found time
        deadline_ms=current_ms - 5000
    )
    new_arb_found_for_missed = current_ms + 2000 # new arb found time
    missed_src_updated = missed_src_initial.with_arb_found_time(new_arb_found_for_missed)
    print(f"  ShioDeadlineMissedSource (updated arb_found_time): {missed_src_updated}")
    assert isinstance(missed_src_updated, ShioDeadlineMissedSource)
    assert missed_src_updated.arb_found_time_ms == new_arb_found_for_missed # type: ignore


    # Test __str__ for ShioDeadlineMissedSource (implicitly tested above)
    deadline_missed_src = ShioDeadlineMissedSource(
        start_time_ms=current_ms - 30000, 
        arb_found_time_ms=current_ms - 1000, 
        deadline_ms=current_ms - 5000
    )
    print(f"\nShio Deadline Missed Source: {deadline_missed_src}")
    assert deadline_missed_src.is_shio()
    assert deadline_missed_src.get_opp_tx_digest() is None
    assert deadline_missed_src.get_deadline() == current_ms - 5000
    assert deadline_missed_src.get_bid_amount() == 0

    print("\nAll arb_bot.types tests executed.")
