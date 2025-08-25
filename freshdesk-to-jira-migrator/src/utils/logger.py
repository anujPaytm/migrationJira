#!/usr/bin/env python3
"""
Comprehensive logging system for the Freshdesk to Jira migration.
"""

import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
import threading

class MigrationLogger:
    """
    Custom logger for migration operations with timestamp and formatting.
    """
    
    def __init__(self, log_file: Optional[str] = None, log_level: str = "INFO"):
        """
        Initialize the migration logger.
        
        Args:
            log_file: Path to log file (optional)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.logger = logging.getLogger('migration')
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Create formatters
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | [%(threadName)s] | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (if specified)
        if log_file:
            # Ensure log directory exists
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)  # File gets all logs
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        
        # Thread safety
        self._lock = threading.Lock()
    
    def _log_with_emoji(self, level: str, emoji: str, message: str, *args, **kwargs):
        """Log message with emoji prefix."""
        with self._lock:
            formatted_message = f"{emoji} {message}"
            if level == 'DEBUG':
                self.logger.debug(formatted_message, *args, **kwargs)
            elif level == 'INFO':
                self.logger.info(formatted_message, *args, **kwargs)
            elif level == 'WARNING':
                self.logger.warning(formatted_message, *args, **kwargs)
            elif level == 'ERROR':
                self.logger.error(formatted_message, *args, **kwargs)
            elif level == 'CRITICAL':
                self.logger.critical(formatted_message, *args, **kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message."""
        self._log_with_emoji('DEBUG', '🔍', message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message."""
        self._log_with_emoji('INFO', 'ℹ️', message, *args, **kwargs)
    
    def success(self, message: str, *args, **kwargs):
        """Log success message."""
        self._log_with_emoji('INFO', '✅', message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message."""
        self._log_with_emoji('WARNING', '⚠️', message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message."""
        self._log_with_emoji('ERROR', '❌', message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log critical message."""
        self._log_with_emoji('CRITICAL', '🚨', message, *args, **kwargs)
    
    def progress(self, current: int, total: int, ticket_id: Optional[int] = None, status: str = ""):
        """Log progress with percentage."""
        percentage = (current / total) * 100 if total > 0 else 0
        ticket_info = f" (Ticket {ticket_id})" if ticket_id else ""
        status_info = f" - {status}" if status else ""
        message = f"Progress: {current}/{total} ({percentage:.1f}%){ticket_info}{status_info}"
        self._log_with_emoji('INFO', '📋', message)
    
    def migration_start(self, ticket_id: int):
        """Log migration start for a ticket."""
        self._log_with_emoji('INFO', '🔄', f"Starting migration for ticket {ticket_id}")
    
    def migration_success(self, ticket_id: int, jira_key: str):
        """Log successful migration."""
        self._log_with_emoji('INFO', '✅', f"Successfully migrated ticket {ticket_id} to {jira_key}")
    
    def migration_failed(self, ticket_id: int, error: str):
        """Log failed migration."""
        self._log_with_emoji('ERROR', '❌', f"Failed to migrate ticket {ticket_id}: {error}")
    
    def attachment_upload(self, ticket_id: int, count: int, successful: int):
        """Log attachment upload results."""
        self._log_with_emoji('INFO', '📎', f"Ticket {ticket_id}: Uploaded {successful}/{count} attachments")
    
    def setup_validation(self, component: str, status: bool, details: str = ""):
        """Log setup validation results."""
        emoji = "✅" if status else "❌"
        level = "INFO" if status else "ERROR"
        message = f"Setup validation - {component}: {'PASS' if status else 'FAIL'}"
        if details:
            message += f" - {details}"
        self._log_with_emoji(level, emoji, message)
    
    def summary(self, stats: dict):
        """Log migration summary."""
        self._log_with_emoji('INFO', '📊', "Migration Summary:")
        self._log_with_emoji('INFO', '   ', f"Total tickets: {stats.get('total_tickets', 0)}")
        self._log_with_emoji('INFO', '   ', f"Successful: {stats.get('successful_migrations', 0)}")
        self._log_with_emoji('INFO', '   ', f"Failed: {stats.get('failed_migrations', 0)}")
        self._log_with_emoji('INFO', '   ', f"Success rate: {stats.get('success_rate', 0):.2%}")
        self._log_with_emoji('INFO', '   ', f"Total attachments: {stats.get('total_attachments', 0)}")
        self._log_with_emoji('INFO', '   ', f"Successful attachments: {stats.get('successful_attachments', 0)}")
        self._log_with_emoji('INFO', '   ', f"Failed attachments: {stats.get('failed_attachments', 0)}")
        self._log_with_emoji('INFO', '   ', f"Attachment success rate: {stats.get('attachment_success_rate', 0):.2%}")


# Global logger instance
_migration_logger = None

def get_logger(log_file: Optional[str] = None, log_level: str = "INFO") -> MigrationLogger:
    """
    Get or create the global migration logger instance.
    
    Args:
        log_file: Path to log file (optional)
        log_level: Logging level
        
    Returns:
        MigrationLogger instance
    """
    global _migration_logger
    if _migration_logger is None:
        _migration_logger = MigrationLogger(log_file, log_level)
    return _migration_logger
