"""
Database Migrations Package
===========================

Database schema migration scripts for the ET:Legacy Discord Bot.

IMPORTANT: Always backup the database before running migrations!
    pg_dump -h localhost -U etlegacy_user -d etlegacy > backup.sql

Migration files follow the naming convention:
    NNNN_description.py (e.g., 0001_add_file_checksums.py)

Usage:
    python -m migrations.0001_add_file_checksums

Note:
    The main database management tool is postgresql_database_manager.py
    which handles schema creation and validation.
"""

__all__ = []
