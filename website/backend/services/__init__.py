"""
Website Backend Services
========================

Service layer for the ET:Legacy Statistics Website.

Available Services:
    WebsiteSessionDataService: Aggregates session data for web display
        - Similar to bot's SessionDataService but optimized for web
        - Returns JSON-serializable data structures
        - Handles pagination for large datasets

Architecture Notes:
    - Services use the local_database_adapter for PostgreSQL access
    - All queries use parameterized SQL to prevent injection
    - Results are cached where appropriate for performance
"""

from website.backend.services.website_session_data_service import WebsiteSessionDataService

__all__ = ['WebsiteSessionDataService']
