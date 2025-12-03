"""
Data Access Layer - Repository Pattern

Repositories encapsulate data access logic and provide a clean interface
for the business layer to interact with the database.

Architecture:
- FileRepository: Manages processed_files table queries
- Future: Could add PlayerRepository, RoundRepository, etc.
"""

from bot.repositories.file_repository import FileRepository

__all__ = ["FileRepository"]
