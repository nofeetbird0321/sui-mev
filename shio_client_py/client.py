# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
WebSocket client for interacting with the Shio feed.
"""

import asyncio
import json
import logging
import websockets # Add 'websockets' to requirements.txt
import httpx # Add 'httpx' to requirements.txt
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK
from typing import Any, Optional

from shio_client_py.types import ShioItem, DummyShioItem # Assuming types.py is in the same package path

logger = logging.getLogger(__name__)

DEFAULT_SHIO_JSON_RPC_URL = "https://rpc.getshio.com"

class ShioFeedClient:
    """
    A WebSocket client to connect to the Shio feed, send bids, and receive items.
    """

    def __init__(self, wss_url: str, num_retries: int = 3, retry_delay_secs: int = 5):
        """
        Initializes the ShioFeedClient.

        Args:
            wss_url: The WebSocket URL to connect to.
            num_retries: Number of times to retry connection before giving up.
            retry_delay_secs: Delay in seconds between retries.
        """
        self.wss_url = wss_url
        self.num_retries = num_retries
        self.retry_delay_secs = retry_delay_secs

        self.bid_queue: asyncio.Queue = asyncio.Queue()
        self.item_queue: asyncio.Queue = asyncio.Queue() # For ShioItem objects

        self._stop_event = asyncio.Event() # Used to signal client shutdown

    async def _handle_outgoing(self, websocket):
        """
        Handles sending messages from the bid_queue to the WebSocket.
        """
        try:
            while not self._stop_event.is_set():
                try:
                    # Wait for a bid from the queue with a timeout to allow checking _stop_event
                    bid_item = await asyncio.wait_for(self.bid_queue.get(), timeout=1.0)
                    if bid_item is None: # A way to signal shutdown of this handler if needed
                        logger.info("Outgoing handler received None, exiting.")
                        break
                    
                    bid_json = json.dumps(bid_item)
                    await websocket.send(bid_json)
                    logger.debug(f"Sent bid: {bid_json}")
                    self.bid_queue.task_done()
                except asyncio.TimeoutError:
                    continue # Continue to check _stop_event and wait for new items
                except ConnectionClosed:
                    logger.warning("Connection closed while sending message. Attempting to reconnect.")
                    raise # Re-raise to be caught by the run loop for reconnection
                except Exception as e:
                    logger.error(f"Error sending message: {e}")
                    # Depending on the error, may want to break or continue
                    # For now, continue, but critical errors might need to break the loop
                    await asyncio.sleep(1) # Avoid tight loop on persistent errors
        finally:
            logger.info("Outgoing message handler finished.")


    async def _handle_incoming(self, websocket):
        """
        Handles receiving messages from the WebSocket and putting them onto the item_queue.
        """
        try:
            async for message in websocket:
                if self._stop_event.is_set():
                    logger.info("Incoming handler stopping due to stop event.")
                    break
                
                if isinstance(message, str):
                    logger.debug(f"Received raw message: {message[:100]}...") # Log snippet
                    try:
                        json_val = json.loads(message)
                        shio_item = ShioItem.from_json_value(json_val)
                        await self.item_queue.put(shio_item)
                        logger.debug(f"Processed and queued ShioItem: {shio_item.type_name()}")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON: {message[:200]}")
                        # Optionally put raw message or error object on queue
                        await self.item_queue.put(DummyShioItem(value={"error": "JSONDecodeError", "raw_message": message}))
                    except Exception as e:
                        logger.error(f"Error processing message into ShioItem: {e}. Raw message: {message[:200]}")
                        await self.item_queue.put(DummyShioItem(value={"error": str(e), "raw_message": message}))
                elif isinstance(message, bytes):
                    # Handle binary messages if necessary, e.g. Ping/Pong often use bytes
                    # For now, just log if unexpected binary data is received.
                    # websockets library handles Pings automatically by sending Pongs by default.
                    logger.debug("Received binary message (possibly Ping/Pong or other).")
                else:
                    logger.warning(f"Received unexpected message type: {type(message)}")

        except ConnectionClosedOK:
            logger.info("Connection closed normally by server.")
        except ConnectionClosedError as e:
            logger.warning(f"Connection closed with error: {e}. Attempting to reconnect.")
            raise # Re-raise to be caught by the run loop for reconnection
        except websockets.exceptions.PayloadTooBig:
            logger.error("Received message payload too big. This message will be dropped.")
            # Consider how to handle this - maybe a DummyShioItem with error
        except Exception as e:
            logger.error(f"Error in incoming message handler: {e}")
            raise # Re-raise to trigger reconnection for unknown errors
        finally:
            logger.info("Incoming message handler finished.")

    async def run(self):
        """
        Main persistent task for the client. Connects to WebSocket and handles messages.
        """
        self._stop_event.clear()
        retries = 0
        while not self._stop_event.is_set() and (retries <= self.num_retries or self.num_retries == -1): # -1 for infinite retries
            try:
                logger.info(f"Attempting to connect to {self.wss_url} (Attempt {retries + 1})")
                # Adjust ping_interval and ping_timeout as needed.
                # Shio server might have specific expectations.
                async with websockets.connect(
                    self.wss_url,
                    ping_interval=20, # Send a ping every 20 seconds
                    ping_timeout=20   # Wait 20 seconds for a pong response
                ) as websocket:
                    logger.info(f"Successfully connected to {self.wss_url}")
                    retries = 0 # Reset retries on successful connection

                    # Start concurrent handlers for incoming and outgoing messages
                    # If one fails (e.g. due to connection error), asyncio.gather will raise the exception
                    # which will be caught by the outer try/except in this run method.
                    outgoing_task = asyncio.create_task(self._handle_outgoing(websocket))
                    incoming_task = asyncio.create_task(self._handle_incoming(websocket))
                    
                    done, pending = await asyncio.wait(
                        [outgoing_task, incoming_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    for task in pending:
                        task.cancel() # Ensure other task is cancelled if one completes/fails
                    
                    for task in done: # Propagate exceptions from completed tasks
                        if task.exception():
                            raise task.exception() # type: ignore

            except (ConnectionClosed, ConnectionClosedError, ConnectionRefusedError, websockets.exceptions.InvalidURI, OSError) as e:
                logger.warning(f"Connection to {self.wss_url} failed or was lost: {e}")
            except websockets.exceptions.PayloadTooBig as e: # Should be caught by _handle_incoming
                logger.error(f"PayloadTooBig error at connection level: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred in the run loop: {e}", exc_info=True)
            
            if self._stop_event.is_set():
                logger.info("Client run loop stopping due to stop event.")
                break

            if retries >= self.num_retries and self.num_retries != -1:
                logger.error(f"Exhausted all {self.num_retries} retries. Giving up on {self.wss_url}.")
                break # Exit the loop

            retries += 1
            logger.info(f"Retrying in {self.retry_delay_secs} seconds...")
            await asyncio.sleep(self.retry_delay_secs)
        
        logger.info("ShioFeedClient run loop has finished.")
        # Signal any waiting tasks that client is fully stopped (e.g. if queues are used externally)
        # Potentially put sentinel values in queues if external consumers expect them for shutdown.

    async def stop(self):
        """
        Signals the client to shut down gracefully.
        """
        logger.info("ShioFeedClient stop requested.")
        self._stop_event.set()
        # Optionally, put sentinel values in queues to wake up handlers if they are blocked
        # await self.bid_queue.put(None) # If _handle_outgoing checks for None to stop
        # This might be handled by tasks being cancelled when run() loop exits gather

    def get_bid_sender_queue(self) -> asyncio.Queue:
        """Returns the queue for sending bids."""
        return self.bid_queue

    def get_item_receiver_queue(self) -> asyncio.Queue:
        """Returns the queue for receiving ShioItem objects."""
        return self.item_queue

if __name__ == '__main__':
    # Example Usage (requires a running WebSocket server at the specified URL)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Replace with your actual Shio WebSocket URL
    # For testing, you can use a public echo WebSocket server like 'wss://echo.websocket.org'
    # or a local one if you have one for Shio.
    SHIO_WSS_URL = "wss://echo.websocket.org" # Replace with actual Shio URL

    async def example_producer(bid_queue: asyncio.Queue):
        """Simulates sending bids periodically."""
        count = 0
        while True:
            await asyncio.sleep(10) # Send a bid every 10 seconds
            bid = {"type": "bid", "item_id": f"item_{count}", "amount": 100 + count}
            logger.info(f"Example producer: adding bid to queue: {bid}")
            await bid_queue.put(bid)
            count += 1
            if count > 5: # Stop after a few bids for this example
                logger.info("Example producer: finished sending bids.")
                break


    async def example_consumer(item_queue: asyncio.Queue):
        """Simulates receiving and processing items."""
        logger.info("Example consumer: waiting for items...")
        processed_count = 0
        while True:
            try:
                item = await asyncio.wait_for(item_queue.get(), timeout=1.0) # Use timeout to allow periodic checks
                logger.info(f"Example consumer: received item: {item.type_name()} - {item}")
                # Example of accessing specific data:
                if isinstance(item, ShioItem) and not isinstance(item, DummyShioItem):
                    logger.info(f"  TX Digest: {item.tx_digest()}, Gas: {item.gas_price()}")
                item_queue.task_done()
                processed_count += 1
                if processed_count >= 5 and SHIO_WSS_URL == "wss://echo.websocket.org": # Stop after a few for echo server
                    logger.info("Example consumer: processed enough items, stopping.")
                    break
            except asyncio.TimeoutError:
                # This is expected, just means no item was available in the last second
                continue
            except Exception as e:
                logger.error(f"Example consumer: error processing item: {e}")
                break # Stop on error

    async def main_example():
        client = ShioFeedClient(wss_url=SHIO_WSS_URL, num_retries=3, retry_delay_secs=2)

        bid_q = client.get_bid_sender_queue()
        item_q = client.get_item_receiver_queue()

        # Start the client's run loop in the background
        client_task = asyncio.create_task(client.run())

        # Start example producer and consumer
        producer_task = asyncio.create_task(example_producer(bid_q))
        consumer_task = asyncio.create_task(example_consumer(item_q))
        
        # Let them run for a bit or until producer/consumer finish
        # For a real application, client.run() would run indefinitely until stop() is called.
        await asyncio.sleep(60) # Run for 60 seconds in this example

        logger.info("Example: Shutting down client and tasks...")
        await client.stop() # Signal client to stop
        
        # Wait for tasks to complete
        await asyncio.gather(producer_task, consumer_task, client_task, return_exceptions=True)
        logger.info("Example finished.")

    try:
        asyncio.run(main_example())
    except KeyboardInterrupt:
        logger.info("Example interrupted by user.")

# Note: `websockets` library needs to be installed.
# Add 'websockets' to your project's requirements.txt or install with pip.


class ShioWsBidder:
    """
    Sends bids via a WebSocket connection by putting them onto a queue
    consumed by ShioFeedClient's outgoing handler.
    """
    def __init__(self, bid_queue: asyncio.Queue):
        """
        Initializes the ShioWsBidder.

        Args:
            bid_queue: The queue to send bid messages to. This queue is typically
                       obtained from an instance of ShioFeedClient.
        """
        self.bid_queue = bid_queue

    async def send_bid(self, tx_data_b64: str, signature_b64: str, bid_amount: int, opp_tx_digest_b58: str) -> None:
        """
        Constructs a bid and puts it onto the WebSocket send queue.

        Args:
            tx_data_b64: Base64 encoded transaction data.
            signature_b64: Base64 encoded signature.
            bid_amount: The amount of the bid.
            opp_tx_digest_b58: Base58 encoded opportunity transaction digest.
        """
        bid_payload = {
            "oppTxDigest": opp_tx_digest_b58,
            "bidAmount": bid_amount,
            "txData": tx_data_b64,
            "sig": signature_b64
        }
        await self.bid_queue.put(bid_payload)
        logger.info(f"WS Bidder: Queued bid for {opp_tx_digest_b58} with amount {bid_amount}")


class ShioRpcBidder:
    """
    Sends bids via JSON-RPC HTTP requests.
    """
    def __init__(self, rpc_url: str = DEFAULT_SHIO_JSON_RPC_URL, http_client: Optional[httpx.AsyncClient] = None):
        """
        Initializes the ShioRpcBidder.

        Args:
            rpc_url: The JSON-RPC endpoint URL. Defaults to DEFAULT_SHIO_JSON_RPC_URL.
            http_client: Optional. An httpx.AsyncClient instance. If None, a new one is created.
        """
        self.rpc_url = rpc_url
        self.http_client = http_client if http_client is not None else httpx.AsyncClient()

    async def send_bid(self, tx_data_b64: str, signature_b64: str, bid_amount: int, opp_tx_digest_b58: str) -> bool:
        """
        Constructs and sends a bid via JSON-RPC.

        Args:
            tx_data_b64: Base64 encoded transaction data.
            signature_b64: Base64 encoded signature.
            bid_amount: The amount of the bid.
            opp_tx_digest_b58: Base58 encoded opportunity transaction digest.

        Returns:
            True if the HTTP request was successful (status 2xx), False otherwise.
        """
        jrpc_payload = {
            "jsonrpc": "2.0",
            "id": 1, # ID can be any unique value, or incremented
            "method": "shio_submitBid",
            "params": [opp_tx_digest_b58, bid_amount, tx_data_b64, signature_b64]
        }
        
        logger.info(f"RPC Bidder: Sending bid 🧀>> {json.dumps(jrpc_payload)}")
        
        try:
            response = await self.http_client.post(self.rpc_url, json=jrpc_payload)
            logger.info(f"RPC Bidder: Response 🧀<< Status: {response.status_code}, Content: {response.text[:200]}...") # Log snippet of content
            response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx responses
            # Assuming success if no exception is raised by raise_for_status()
            # Further checks on response.json() content might be needed for specific success conditions
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"RPC Bidder: HTTP error for {opp_tx_digest_b58} - Status {e.response.status_code}: {e.response.text}")
            return False
        except httpx.RequestError as e:
            logger.error(f"RPC Bidder: Request error for {opp_tx_digest_b58}: {e}")
            return False
        except Exception as e:
            logger.error(f"RPC Bidder: An unexpected error occurred while sending bid for {opp_tx_digest_b58}: {e}")
            return False

    async def close(self):
        """
        Closes the underlying httpx.AsyncClient.
        Should be called when the bidder is no longer needed, especially if an
        AsyncClient was created internally.
        """
        await self.http_client.aclose()
        logger.info("RPC Bidder: HTTP client closed.")


if __name__ == '__main__':
    # Example Usage (requires a running WebSocket server at the specified URL)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Replace with your actual Shio WebSocket URL
    # For testing, you can use a public echo WebSocket server like 'wss://echo.websocket.org'
    # or a local one if you have one for Shio.
    SHIO_WSS_URL = "wss://echo.websocket.org" # Replace with actual Shio URL
    # For RPC Bidder, you might need a mock server or a real Shio RPC endpoint.
    # Using a public echo service for POST might not work as expected, but we can simulate.
    SHIO_RPC_URL = "https://jsonplaceholder.typicode.com/posts" # Example POST endpoint for testing structure

    async def example_producer(bid_queue: asyncio.Queue):
        """Simulates sending bids periodically via WS Bidder."""
        ws_bidder = ShioWsBidder(bid_queue=bid_queue)
        count = 0
        while True:
            await asyncio.sleep(10) # Send a bid every 10 seconds
            logger.info(f"Example producer: preparing WS bid for item_{count}")
            await ws_bidder.send_bid(
                tx_data_b64="dummy_tx_data_b64",
                signature_b64="dummy_signature_b64",
                bid_amount=100 + count,
                opp_tx_digest_b58=f"opp_tx_digest_ws_{count}"
            )
            count += 1
            if count > 2: # Stop after a few bids for this example
                logger.info("Example producer: finished sending WS bids.")
                break


    async def example_consumer(item_queue: asyncio.Queue):
        """Simulates receiving and processing items."""
        logger.info("Example consumer: waiting for items...")
        processed_count = 0
        while True:
            try:
                item = await asyncio.wait_for(item_queue.get(), timeout=1.0) # Use timeout to allow periodic checks
                logger.info(f"Example consumer: received item: {item.type_name()} - {item}")
                # Example of accessing specific data:
                if isinstance(item, ShioItem) and not isinstance(item, DummyShioItem):
                    logger.info(f"  TX Digest: {item.tx_digest()}, Gas: {item.gas_price()}")
                item_queue.task_done()
                processed_count += 1
                if processed_count >= 2 and SHIO_WSS_URL == "wss://echo.websocket.org": # Stop after a few for echo server
                    logger.info("Example consumer: processed enough items, stopping.")
                    break
            except asyncio.TimeoutError:
                # This is expected, just means no item was available in the last second
                continue
            except Exception as e:
                logger.error(f"Example consumer: error processing item: {e}")
                break # Stop on error

    async def example_rpc_bids():
        """Simulates sending bids via RPC Bidder."""
        rpc_bidder = ShioRpcBidder(rpc_url=SHIO_RPC_URL) # Using example POST endpoint
        logger.info("Example RPC Bidder: starting...")
        for i in range(2):
            success = await rpc_bidder.send_bid(
                tx_data_b64=f"rpc_tx_data_b64_{i}",
                signature_b64=f"rpc_signature_b64_{i}",
                bid_amount=200 + i,
                opp_tx_digest_b58=f"opp_tx_digest_rpc_{i}"
            )
            logger.info(f"Example RPC Bidder: Bid for opp_tx_digest_rpc_{i} successful: {success}")
            await asyncio.sleep(1)
        await rpc_bidder.close() # Important to close the client
        logger.info("Example RPC Bidder: finished.")


    async def main_example():
        client = ShioFeedClient(wss_url=SHIO_WSS_URL, num_retries=1, retry_delay_secs=1) # Reduced retries for example

        bid_q = client.get_bid_sender_queue()
        item_q = client.get_item_receiver_queue()

        # Start the client's run loop in the background
        client_task = asyncio.create_task(client.run())

        # Start example producer (for WS bids) and consumer
        producer_task = asyncio.create_task(example_producer(bid_q))
        consumer_task = asyncio.create_task(example_consumer(item_q))
        
        # Start example RPC bids
        rpc_task = asyncio.create_task(example_rpc_bids())

        # Let them run for a bit or until producer/consumer finish
        # For a real application, client.run() would run indefinitely until stop() is called.
        await asyncio.sleep(30) # Run for 30 seconds in this example

        logger.info("Example: Shutting down client and tasks...")
        await client.stop() # Signal client to stop
        
        # Wait for tasks to complete
        # Ensure producer_task and consumer_task are awaited correctly if they might finish early.
        # Cancelling them might be an option if they are meant to run indefinitely until main_example ends.
        # For this example, they have conditions to break their loops.
        await asyncio.gather(producer_task, consumer_task, rpc_task, client_task, return_exceptions=True)
        logger.info("Example finished.")

    try:
        asyncio.run(main_example())
    except KeyboardInterrupt:
        logger.info("Example interrupted by user.")

# Note: `websockets` and `httpx` libraries need to be installed.
# Add them to your project's requirements.txt or install with pip.
