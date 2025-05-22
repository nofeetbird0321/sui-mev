# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Panic handler to send crash reports via Telegram and log them.
"""

import sys
import traceback
import asyncio
import logging
import threading
import os
import shlex
from typing import List, Type

from common_utils_py.telegram_sender import TelegramSender, R2D2_TELEGRAM_BOT_TOKEN, CHAT_TESTING_AND_RELEASES

# Constants for argument redaction, similar to Rust's implementation
_MAX_ARG_LEN = 128
_MAX_TOTAL_ARG_LEN = 1024

logger = logging.getLogger(__name__)

# Global variable to store the TelegramSender instance for the panic hook
_telegram_sender_for_panic: TelegramSender = None # type: ignore

def _format_argv(argv: List[str]) -> str:
    """
    Formats sys.argv, redacting long arguments.
    """
    processed_args = []
    total_len = 0
    for arg in argv:
        if total_len + len(arg) > _MAX_TOTAL_ARG_LEN and processed_args:
            processed_args.append(f"... (truncated {len(argv) - len(processed_args)} args)")
            break
        if len(arg) > _MAX_ARG_LEN:
            processed_args.append(arg[:_MAX_ARG_LEN] + "...")
        else:
            processed_args.append(arg)
        total_len += len(processed_args[-1])
    return " ".join(shlex.quote(arg) for arg in processed_args)


def _custom_except_hook(exc_type: Type[BaseException], exc_value: BaseException, exc_traceback):
    """
    Custom exception hook to log and send messages on unhandled exceptions.
    """
    global _telegram_sender_for_panic

    # Format the traceback
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    tb_text = "".join(tb_lines)

    # Get current thread name
    thread_name = threading.current_thread().name

    # Format command line arguments
    try:
        # In some environments (like certain test runners or embedded interpreters),
        # sys.argv might not exist or might not be what we expect.
        if hasattr(sys, 'argv') and sys.argv:
            program_name = os.path.basename(sys.argv[0])
            args_str = _format_argv(sys.argv)
            full_command = f"{program_name} {args_str}" # Note: This might duplicate program_name if argv[0] is already part of args_str after formatting.
                                                      # The Rust version uses `std::env::current_exe()` and then `args_str`.
                                                      # For simplicity, we'll use sys.argv[0] and the formatted args.
                                                      # A more robust way would be to get executable path and then format args.
        else:
            program_name = "UnknownProgram"
            args_str = "N/A"
            full_command = "Unknown command (sys.argv not available)"
    except Exception as e:
        program_name = "ErrorFormattingArgs"
        args_str = f"Error formatting argv: {e}"
        full_command = args_str


    # Construct the error message for Telegram (HTML formatted)
    # Mimicking the structure from the Rust version
    error_message_html = (
        f"<b>Python script panicked!</b>\n"
        f"<b>Thread:</b> {thread_name}\n"
        f"<b>Program:</b> {program_name}\n" # os.path.basename(sys.argv[0]) might be better
        f"<b>Args:</b> <pre>{args_str}</pre>\n"
        f"<b>Exception:</b> {exc_type.__name__}: {exc_value}\n"
        f"<pre>{tb_text}</pre>"
    )

    # Log the error to standard logging
    # Standard library excepthook prints to sys.stderr, so we can do that too, or use logger.
    logger.critical(f"Unhandled exception on thread {thread_name}:", exc_info=(exc_type, exc_value, exc_traceback))
    logger.critical(f"Command line: {full_command}")


    if _telegram_sender_for_panic:
        try:
            # Running async code from a sync context (excepthook).
            # asyncio.run() is simple but can cause issues if an event loop is already running.
            # TODO: Implement a more robust way to call async from sync,
            # e.g., using asyncio.run_coroutine_threadsafe if an event loop runs in a background thread,
            # or by having TelegramSender manage its own thread for sending.
            # For now, assume no event loop is running or this is the main thread.
            asyncio.run(_telegram_sender_for_panic.send_message(error_message_html, parse_mode="HTML"))
            logger.info("Panic report sent to Telegram.")
        except RuntimeError as e:
            logger.error(f"Could not send panic report to Telegram (RuntimeError: {e}). "
                         "This might happen if an asyncio event loop is already running in this thread.")
        except Exception as e:
            logger.error(f"Failed to send panic report to Telegram: {e}")
    else:
        logger.warning("Telegram sender for panic reports is not configured. Cannot send Telegram notification.")

    # Call the default excepthook as well to ensure standard error output
    # sys.__excepthook__(exc_type, exc_value, exc_traceback)


def setup_panic_hook(telegram_sender_for_panic: TelegramSender):
    """
    Sets up a custom panic hook that sends messages via the provided TelegramSender.

    Args:
        telegram_sender_for_panic: An instance of TelegramSender to use for sending panic reports.
    """
    global _telegram_sender_for_panic
    if not isinstance(telegram_sender_for_panic, TelegramSender):
        raise TypeError("telegram_sender_for_panic must be an instance of TelegramSender")

    logger.info("Setting up custom panic hook for Telegram reporting.")
    _telegram_sender_for_panic = telegram_sender_for_panic
    sys.excepthook = _custom_except_hook


if __name__ == '__main__':
    # Example Usage (requires environment variables for Telegram to actually send)
    # Ensure R2D2_TELEGRAM_BOT_TOKEN and CHAT_TESTING_AND_RELEASES are set.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    if not R2D2_TELEGRAM_BOT_TOKEN or not CHAT_TESTING_AND_RELEASES:
        logger.warning("Skipping panic_handler example: R2D2_TELEGRAM_BOT_TOKEN or CHAT_TESTING_AND_RELEASES not set.")
        logger.warning("To run this example with Telegram reporting, set these environment variables.")
        # Setup a dummy sender if tokens are not set, so the hook still runs (but won't send)
        panic_sender = TelegramSender(bot_token="", chat_id="")
    else:
        panic_sender = TelegramSender(
            bot_token=R2D2_TELEGRAM_BOT_TOKEN,
            chat_id=CHAT_TESTING_AND_RELEASES # Using a general test chat for this example
        )

    setup_panic_hook(panic_sender)

    logger.info("Panic hook setup. Simulating an unhandled exception...")

    # Simulate command line arguments
    sys.argv = ["test_script.py", "arg1", "another_long_argument_that_will_be_truncated_hopefully", "-f", "some_file.txt", "--very-long-option=" + ("X"*200)]
    
    # Example 1: Simple exception
    # raise ValueError("This is a test panic from common_utils_py.panic_handler example!")

    # Example 2: Exception in a different thread (panic hook should still work for main thread's unhandled exceptions)
    # The panic hook set by sys.excepthook is only for the main thread by default.
    # For other threads, threading.excepthook (Python 3.8+) would be needed.
    # This example will only trigger the hook if this main thread panics.
    
    def faulty_function():
        x = 1 / 0
        return x

    try:
        faulty_function()
    except ZeroDivisionError as e:
        # This exception is caught, so it won't trigger the panic hook by itself.
        logger.error(f"Caught an expected error: {e}. This will not trigger the panic hook.")
        logger.info("Now raising an unhandled exception to trigger the panic hook.")
        # Now raise something unhandled
        raise RuntimeError("This is a deliberate unhandled exception for testing the panic hook.")

    # If the script reaches here, the panic hook was not triggered by an unhandled exception
    logger.info("If you see this, the unhandled exception was somehow bypassed.")
