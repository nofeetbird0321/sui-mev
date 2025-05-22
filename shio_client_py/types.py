# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Python type definitions mirroring the Rust structs and enums in crates/shio/src/types.rs.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, List, Union

# Assumed field names in Python will use snake_case.
# If JSON field names are camelCase (e.g., txDigest), deserialization logic
# (outside this file) would need to handle the mapping.

@dataclass
class ShioEventId:
    """Mirrors Rust ShioEventId struct."""
    event_seq: str # u64 in Rust, typically string in JSON
    tx_digest: str

    @classmethod
    def from_dict(cls, data: dict) -> 'ShioEventId':
        # Assuming JSON keys match attribute names (e.g., event_seq, tx_digest)
        # Rust serde might use camelCase (eventSeq, txDigest)
        # For this example, we'll assume direct mapping or that the input dict is already snake_case
        return cls(
            event_seq=str(data.get("event_seq", data.get("eventSeq", ""))), # Handle potential camelCase
            tx_digest=data.get("tx_digest", data.get("txDigest", ""))
        )

@dataclass
class ShioEvent:
    """Mirrors Rust ShioEvent struct."""
    event_type: str
    bcs: str
    event_id: ShioEventId
    package_id: str
    parsed_json: Optional[Any] # Value in Rust is Option<Value>
    sender: str
    transaction_module: str

    @classmethod
    def from_dict(cls, data: dict) -> 'ShioEvent':
        return cls(
            event_type=data.get("event_type", data.get("eventType", "")),
            bcs=data.get("bcs", ""),
            event_id=ShioEventId.from_dict(data.get("event_id", data.get("eventId", {}))),
            package_id=data.get("package_id", data.get("packageId", "")),
            parsed_json=data.get("parsed_json", data.get("parsedJson")), # Optional
            sender=data.get("sender", ""),
            transaction_module=data.get("transaction_module", data.get("transactionModule", ""))
        )

@dataclass
class ShioObjectContent:
    """Mirrors Rust ShioObjectContent struct."""
    data_type: str # e.g., "moveObject"
    has_public_transfer: bool

    @classmethod
    def from_dict(cls, data: dict) -> 'ShioObjectContent':
        return cls(
            data_type=data.get("data_type", data.get("dataType", "")),
            has_public_transfer=data.get("has_public_transfer", data.get("hasPublicTransfer", False))
        )

@dataclass
class ShioObject:
    """Mirrors Rust ShioObject struct."""
    id: str
    object_type: str # Type_ in Rust, often String for object type tags
    owner: Any # Owner in Rust is complex (AddressOwner, ObjectOwner, Shared, Immutable)
               # Using Any here to accommodate diverse JSON structures.
    content: ShioObjectContent
    object_bcs: str # Base64 encoded BCS bytes

    @classmethod
    def from_dict(cls, data: dict) -> 'ShioObject':
        return cls(
            id=data.get("id", data.get("objectId", "")), # Common alternative name
            object_type=data.get("object_type", data.get("objectType", "")),
            owner=data.get("owner", {}), # Keep as dict/Any
            content=ShioObjectContent.from_dict(data.get("content", {})),
            object_bcs=data.get("object_bcs", data.get("bcs", "")) # Common alternative name
        )

@dataclass
class SideEffects:
    """Mirrors Rust SideEffects struct."""
    created_objects: List[ShioObject] = field(default_factory=list)
    mutated_objects: List[ShioObject] = field(default_factory=list)
    gas_usage: int = 0 # Assuming u64 maps to int
    events: List[ShioEvent] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> 'SideEffects':
        return cls(
            created_objects=[ShioObject.from_dict(obj_data) for obj_data in data.get("created_objects", data.get("createdObjects", []))],
            mutated_objects=[ShioObject.from_dict(obj_data) for obj_data in data.get("mutated_objects", data.get("mutatedObjects", []))],
            gas_usage=int(data.get("gas_usage", data.get("gasUsage", 0))),
            events=[ShioEvent.from_dict(event_data) for event_data in data.get("events", [])]
        )

# Base class for ShioItem variants
@dataclass
class ShioItem:
    """Base class for different ShioItem types."""

    def tx_digest(self) -> str:
        """Returns the transaction digest if applicable, otherwise an empty string."""
        return ""

    def gas_price(self) -> int:
        """Returns the gas price if applicable, otherwise 0."""
        return 0

    def deadline_timestamp_ms(self) -> int:
        """Returns the deadline timestamp in ms if applicable, otherwise 0."""
        return 0
    
    def winning_bid_amount(self) -> int:
        """Returns the winning bid amount if applicable, otherwise 0."""
        return 0

    def events(self) -> List[ShioEvent]:
        """Returns a list of events if applicable, otherwise an empty list."""
        return []

    def created_mutated_objects(self) -> List[ShioObject]:
        """Returns a list of created and mutated objects if applicable, otherwise an empty list."""
        return []

    def type_name(self) -> str:
        """Returns the type name of the ShioItem variant."""
        return self.__class__.__name__

    @classmethod
    def from_json_value(cls, json_val: Any) -> 'ShioItem':
        """
        Factory method to create a ShioItem subclass instance from a JSON value.
        """
        if not isinstance(json_val, dict):
            return DummyShioItem(value=json_val)

        if "auctionStarted" in json_val:
            try:
                return AuctionStarted.from_dict(json_val["auctionStarted"])
            except Exception as e:
                # Log error: print(f"Error parsing AuctionStarted: {e}")
                return DummyShioItem(value=json_val)
        elif "auctionEnded" in json_val:
            try:
                return AuctionEnded.from_dict(json_val["auctionEnded"])
            except Exception as e:
                # Log error: print(f"Error parsing AuctionEnded: {e}")
                return DummyShioItem(value=json_val)
        # Add other ShioItem types here if they exist, e.g.:
        # elif "someOtherType" in json_val:
        #     return SomeOtherType.from_dict(json_val["someOtherType"])
        else:
            # If type is unknown or not directly identifiable by a top-level key
            return DummyShioItem(value=json_val)


@dataclass
class AuctionStarted(ShioItem):
    """Mirrors Rust ShioItem::AuctionStarted variant."""
    tx_digest_val: str # Field name changed to avoid conflict with method
    gas_price_val: int # Field name changed to avoid conflict with method
    deadline_timestamp_ms_val: int # Field name changed to avoid conflict with method
    side_effects: SideEffects

    @classmethod
    def from_dict(cls, data: dict) -> 'AuctionStarted':
        # Assumes keys in data are already snake_case or handled by .get() with fallbacks
        return cls(
            tx_digest_val=data.get("tx_digest", data.get("txDigest", "")),
            gas_price_val=int(data.get("gas_price", data.get("gasPrice", 0))),
            deadline_timestamp_ms_val=int(data.get("deadline_timestamp_ms", data.get("deadlineTimestampMs", 0))),
            side_effects=SideEffects.from_dict(data.get("side_effects", data.get("sideEffects", {})))
        )

    def tx_digest(self) -> str:
        return self.tx_digest_val

    def gas_price(self) -> int:
        return self.gas_price_val

    def deadline_timestamp_ms(self) -> int:
        return self.deadline_timestamp_ms_val

    def events(self) -> List[ShioEvent]:
        return self.side_effects.events if self.side_effects else []

    def created_mutated_objects(self) -> List[ShioObject]:
        if not self.side_effects:
            return []
        # Ensure lists are not None before concatenation
        created = self.side_effects.created_objects or []
        mutated = self.side_effects.mutated_objects or []
        return created + mutated

@dataclass
class AuctionEnded(ShioItem):
    """Mirrors Rust ShioItem::AuctionEnded variant."""
    tx_digest_val: str # Field name changed to avoid conflict with method
    winning_bid_amount_val: int # Field name changed to avoid conflict with method

    @classmethod
    def from_dict(cls, data: dict) -> 'AuctionEnded':
        return cls(
            tx_digest_val=data.get("tx_digest", data.get("txDigest", "")),
            winning_bid_amount_val=int(data.get("winning_bid_amount", data.get("winningBidAmount", 0)))
        )

    def tx_digest(self) -> str:
        return self.tx_digest_val
    
    def winning_bid_amount(self) -> int:
        return self.winning_bid_amount_val


@dataclass
class DummyShioItem(ShioItem):
    """
    Mirrors Rust ShioItem::Dummy variant.
    Used for items that don't match known types or for testing.
    """
    value: Any # To hold the raw JSON value or any other data

# Helper type for deserialization logic (not strictly part of this file's task but good for context)
ShioItemType = Union[AuctionStarted, AuctionEnded, DummyShioItem]


if __name__ == '__main__':
    # Example Usage and Tests

    # ShioEventId
    event_id_data = {"eventSeq": "123", "txDigest": "tx_digest_abc"}
    event_id = ShioEventId.from_dict(event_id_data)
    print(f"Event ID from dict: {event_id}")
    assert event_id.event_seq == "123"
    assert event_id.tx_digest == "tx_digest_abc"


    # ShioEvent
    event_data = {
        "eventType": "0x2::devnet_nft::MintNFTEvent",
        "bcs": "bcs_data_xyz",
        "eventId": event_id_data,
        "packageId": "0xpackage123",
        "parsedJson": {"name": "My NFT", "description": "Awesome NFT"},
        "sender": "0xsender_addr",
        "transactionModule": "devnet_nft"
    }
    event = ShioEvent.from_dict(event_data)
    print(f"Event from dict: {event}")
    assert event.event_type == "0x2::devnet_nft::MintNFTEvent"
    assert event.event_id.tx_digest == "tx_digest_abc"

    # ShioObjectContent
    obj_content_data = {"dataType": "moveObject", "hasPublicTransfer": True}
    obj_content = ShioObjectContent.from_dict(obj_content_data)
    print(f"Object Content from dict: {obj_content}")
    assert obj_content.has_public_transfer is True

    # ShioObject
    obj_data = {
        "id": "0xobject_id_123",
        "objectType": "0x2::coin::Coin<0x2::sui::SUI>",
        "owner": {"AddressOwner": "0xowner_addr"},
        "content": obj_content_data,
        "bcs": "bcs_object_data_abc"
    }
    obj = ShioObject.from_dict(obj_data)
    print(f"Object from dict: {obj}")
    assert obj.id == "0xobject_id_123"
    assert obj.content.data_type == "moveObject"

    # SideEffects
    side_effects_json_data = {
        "createdObjects": [obj_data],
        "mutatedObjects": [],
        "gasUsage": 10000,
        "events": [event_data]
    }
    side_effects_data = SideEffects.from_dict(side_effects_json_data)
    print(f"Side Effects from dict: {side_effects_data}")
    assert len(side_effects_data.created_objects) == 1
    assert side_effects_data.created_objects[0].id == "0xobject_id_123"
    assert side_effects_data.gas_usage == 10000
    assert len(side_effects_data.events) == 1
    assert side_effects_data.events[0].package_id == "0xpackage123"


    # --- Test ShioItem.from_json_value ---
    print("\n--- Testing ShioItem.from_json_value ---")

    # AuctionStarted
    auction_started_json = {
        "auctionStarted": {
            "txDigest": "tx_digest_auction_start",
            "gasPrice": 100,
            "deadlineTimestampMs": 1678886400000,
            "sideEffects": side_effects_json_data
        }
    }
    auction_started_item = ShioItem.from_json_value(auction_started_json)
    print(f"\nAuction Started Item from_json_value: {auction_started_item}")
    assert isinstance(auction_started_item, AuctionStarted)
    assert auction_started_item.tx_digest() == "tx_digest_auction_start"
    assert auction_started_item.gas_price() == 100
    assert auction_started_item.deadline_timestamp_ms() == 1678886400000
    assert len(auction_started_item.events()) == 1
    assert len(auction_started_item.created_mutated_objects()) == 1


    # AuctionEnded
    auction_ended_json = {
        "auctionEnded": {
            "txDigest": "tx_digest_auction_end",
            "winningBidAmount": 5000
        }
    }
    auction_ended_item = ShioItem.from_json_value(auction_ended_json)
    print(f"\nAuction Ended Item from_json_value: {auction_ended_item}")
    assert isinstance(auction_ended_item, AuctionEnded)
    assert auction_ended_item.tx_digest() == "tx_digest_auction_end"
    assert auction_ended_item.winning_bid_amount() == 5000


    # DummyShioItem from unknown type
    dummy_json_unknown = {"unknownType": {"key": "value"}}
    dummy_item_unknown = ShioItem.from_json_value(dummy_json_unknown)
    print(f"\nDummy Item (unknown type) from_json_value: {dummy_item_unknown}")
    assert isinstance(dummy_item_unknown, DummyShioItem)
    assert dummy_item_unknown.value == dummy_json_unknown

    # DummyShioItem from non-dict input
    dummy_item_non_dict = ShioItem.from_json_value("this is not a dict")
    print(f"\nDummy Item (non-dict) from_json_value: {dummy_item_non_dict}")
    assert isinstance(dummy_item_non_dict, DummyShioItem)
    assert dummy_item_non_dict.value == "this is not a dict"
    
    # DummyShioItem from parsing error (e.g. AuctionStarted missing required field if we made them strict)
    # For now, from_dict methods are lenient with .get, so this is harder to trigger
    # without adding stricter checks or required fields.
    # Example: If "txDigest" was absolutely required and missing, it might error.
    # auction_started_bad_json = {"auctionStarted": {"gasPrice": 100}} # Missing txDigest
    # dummy_item_parse_error = ShioItem.from_json_value(auction_started_bad_json)
    # print(f"\nDummy Item (parse error) from_json_value: {dummy_item_parse_error}")
    # assert isinstance(dummy_item_parse_error, DummyShioItem)
    # assert dummy_item_parse_error.value == auction_started_bad_json


    # --- Original Manual Instantiation Examples (kept for reference, can be removed/commented) ---
    event_id_manual = ShioEventId(event_seq="123", tx_digest="tx_digest_abc")
    print(f"\nManual Event ID: {event_id_manual}")

    event = ShioEvent(
        event_type="0x2::devnet_nft::MintNFTEvent",
        bcs="bcs_data_xyz",
        event_id=event_id_manual,
        package_id="0xpackage123",
        parsed_json={"name": "My NFT", "description": "Awesome NFT"},
        sender="0xsender_addr",
        transaction_module="devnet_nft"
    )
    print(f"Manual Event: {event}")
    # ... (rest of the original manual examples can be tested similarly or removed)

    print("\nAll example usages and tests executed, including from_dict and from_json_value.")
