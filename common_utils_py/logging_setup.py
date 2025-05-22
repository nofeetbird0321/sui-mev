# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Logging setup utility."""

import logging
import logging.handlers
import sys # For StreamHandler to output to stdout

def setup_logging(
    log_level=logging.INFO,
    log_to_console: bool = True,
    log_file_path: str = "app.log",
    log_to_file: bool = False,
    rolling_interval_type: str = "H",
    rolling_interval_value: int = 1,
    backup_count: int = 7
):
    """
    Configures logging for the application.

    Args:
        log_level: The minimum logging level (e.g., logging.INFO, logging.DEBUG).
        log_to_console: If True, logs will be output to the console.
        log_file_path: Path to the log file if log_to_file is True.
        log_to_file: If True, logs will be output to a timed rotating file.
        rolling_interval_type: Type of interval for log rotation (e.g., 'S', 'M', 'H', 'D', 'W0'-'W6').
        rolling_interval_value: Value of the interval for log rotation.
        backup_count: Number of backup log files to keep.
    """
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Create a log formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s')

    # Clear any existing handlers to avoid duplicate logging if called multiple times
    # This is important if setup_logging might be invoked more than once.
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    if log_to_console:
        # Create a StreamHandler for console output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if log_to_file:
        # Create a TimedRotatingFileHandler for file output
        try:
            file_handler = logging.handlers.TimedRotatingFileHandler(
                filename=log_file_path,
                when=rolling_interval_type,
                interval=rolling_interval_value,
                backupCount=backup_count,
                encoding='utf-8' # Good practice to specify encoding
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # Fallback to console logging if file handler setup fails
            logging.error(f"Failed to set up file logging for {log_file_path}: {e}. Logging to console only (if enabled).")
            if not log_to_console: # If console logging wasn't originally enabled, enable it as a fallback.
                console_handler_fallback = logging.StreamHandler(sys.stdout)
                console_handler_fallback.setFormatter(formatter)
                if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
                    root_logger.addHandler(console_handler_fallback)


if __name__ == '__main__':
    # Example usage:
    print("Setting up logging with console and file output (app_example.log)...")
    setup_logging(
        log_level=logging.DEBUG,    # Log DEBUG and higher messages
        log_to_console=True,
        log_to_file=True,
        log_file_path="app_example.log",
        rolling_interval_type="S",  # Rotate every 5 seconds for testing
        rolling_interval_value=5,
        backup_count=3              # Keep 3 backup files
    )

    # Get a logger for the current module
    logger = logging.getLogger(__name__)

    # Log some test messages
    logger.debug("This is a debug message. (Should appear in console and file)")
    logger.info("This is an info message. (Should appear in console and file)")
    logger.warning("This is a warning message. (Should appear in console and file)")
    logger.error("This is an error message. (Should appear in console and file)")
    logger.critical("This is a critical message. (Should appear in console and file)")

    print("\nLogging setup complete. Check 'app_example.log' and console output.")
    print("If you run this script multiple times quickly, you might see log rotation.")

    # Demonstrate logging from another module (simulated)
    other_module_logger = logging.getLogger("my_other_module")
    other_module_logger.info("Info message from 'my_other_module'.")
    other_module_logger.debug("Debug message from 'my_other_module'. (Should be visible due to root level)")

    # Example to test file handler failure (e.g. permission denied if app_example.log is not writable)
    # print("\nTesting logging setup with a non-writable log file path (simulated)...")
    # setup_logging(
    #     log_level=logging.INFO,
    #     log_to_console=True, # Keep console on to see the error
    #     log_to_file=True,
    #     log_file_path="/root/cannot_write_here.log" # Assuming this path is not writable
    # )
    # logger.info("This message might only go to console if file logging failed.")
