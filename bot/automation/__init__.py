"""
Automation Module - SSH and Stats File Processing

This module handles automated tasks like:
- SSH file operations (list, download)
- Stats file tracking
- Stats import orchestration
"""

from .file_tracker import FileTracker
from .ssh_handler import SSHHandler

__all__ = ['SSHHandler', 'FileTracker']
