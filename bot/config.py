"""
Bot Configuration System
Supports both SQLite and PostgreSQL with environment variables or config file.
"""
import os
import json
import logging
from typing import Optional, Dict, Any

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file into environment variables
except ImportError:
    pass  # python-dotenv not installed, skip

logger = logging.getLogger('BotConfig')


class BotConfig:
    """
    Centralized bot configuration supporting multiple database backends.
    
    Configuration Priority:
    1. Environment variables
    2. bot_config.json file
    3. Default values (SQLite fallback)
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize bot configuration.
        
        Args:
            config_file: Optional path to JSON config file
        """
        self.config_file = config_file or "bot_config.json"
        self._config_data = {}
        
        # Load config file if exists
        if os.path.exists(self.config_file):
            self._load_config_file()
        
        # Database configuration (default to PostgreSQL for production)
        self.database_type = self._get_config('DATABASE_TYPE', 'postgresql')
        
        # SQLite settings
        self.sqlite_db_path = self._get_config('SQLITE_DB_PATH', 'bot/etlegacy_production.db')
        
        # PostgreSQL settings
        self.postgres_host = self._get_config('POSTGRES_HOST', 'localhost')
        self.postgres_port = int(self._get_config('POSTGRES_PORT', '5432'))
        self.postgres_database = self._get_config('POSTGRES_DATABASE', 'etlegacy_stats')
        self.postgres_user = self._get_config('POSTGRES_USER', 'etlegacy')
        self.postgres_password = self._get_config('POSTGRES_PASSWORD', '')
        # Increased pool size for 14 cogs + 4 background tasks
        self.postgres_min_pool = int(self._get_config('POSTGRES_MIN_POOL', '10'))
        self.postgres_max_pool = int(self._get_config('POSTGRES_MAX_POOL', '30'))
        
        # Discord settings (maintain backward compatibility)
        self.discord_token = self._get_config('DISCORD_BOT_TOKEN', '')
        self.discord_guild_id = self._get_config('DISCORD_GUILD_ID', '')
        self.discord_stats_channel_id = self._get_config('DISCORD_STATS_CHANNEL_ID', '')
        
        # Stats parsing settings
        self.stats_directory = self._get_config('STATS_DIRECTORY', 'local_stats')
        self.backup_directory = self._get_config('BACKUP_DIRECTORY', 'processed_stats')
        
        logger.info(f"🔧 Configuration loaded: database_type={self.database_type}")
    
    def _load_config_file(self):
        """Load configuration from JSON file."""
        try:
            with open(self.config_file, 'r') as f:
                self._config_data = json.load(f)
            logger.info(f"📄 Config file loaded: {self.config_file}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load config file {self.config_file}: {e}")
            self._config_data = {}
    
    def _get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with priority: ENV > config file > default.
        
        Args:
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Configuration value
        """
        # 1. Check environment variables
        env_value = os.getenv(key)
        if env_value is not None:
            return env_value
        
        # 2. Check config file
        if key in self._config_data:
            return self._config_data[key]
        
        # 3. Return default
        return default
    
    def get_database_adapter_kwargs(self) -> Dict[str, Any]:
        """
        Get kwargs for creating database adapter.
        
        Returns:
            Dictionary of parameters for create_adapter()
        """
        if self.database_type.lower() == 'sqlite':
            return {
                'db_type': 'sqlite',
                'db_path': self.sqlite_db_path
            }
        elif self.database_type.lower() in ('postgresql', 'postgres'):
            return {
                'db_type': 'postgresql',
                'host': self.postgres_host,
                'port': self.postgres_port,
                'database': self.postgres_database,
                'user': self.postgres_user,
                'password': self.postgres_password,
                'min_pool_size': self.postgres_min_pool,
                'max_pool_size': self.postgres_max_pool
            }
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")
    
    def get_postgres_connection_url(self) -> str:
        """
        Build PostgreSQL connection URL.
        
        Returns:
            PostgreSQL connection string
        """
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        )
    
    def save_example_config(self, output_path: str = "bot_config.example.json"):
        """
        Save example configuration file with all available options.
        
        Args:
            output_path: Path to save example config
        """
        example = {
            "DATABASE_TYPE": "sqlite",
            "SQLITE_DB_PATH": "bot/etlegacy_production.db",
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DATABASE": "etlegacy_stats",
            "POSTGRES_USER": "etlegacy",
            "POSTGRES_PASSWORD": "your_secure_password_here",
            "POSTGRES_MIN_POOL": "5",
            "POSTGRES_MAX_POOL": "20",
            "DISCORD_BOT_TOKEN": "your_discord_bot_token_here",
            "DISCORD_GUILD_ID": "your_guild_id_here",
            "DISCORD_STATS_CHANNEL_ID": "your_stats_channel_id_here",
            "STATS_DIRECTORY": "local_stats",
            "BACKUP_DIRECTORY": "processed_stats"
        }
        
        with open(output_path, 'w') as f:
            json.dump(example, f, indent=2)
        
        logger.info(f"📝 Example config saved: {output_path}")
    
    def __repr__(self):
        """String representation (hides password)."""
        return (
            f"BotConfig(database_type={self.database_type}, "
            f"sqlite_path={self.sqlite_db_path}, "
            f"postgres_host={self.postgres_host}:{self.postgres_port})"
        )


# Convenience function for quick config loading
def load_config(config_file: Optional[str] = None) -> BotConfig:
    """
    Load bot configuration.
    
    Args:
        config_file: Optional path to config file
        
    Returns:
        BotConfig instance
    """
    return BotConfig(config_file)
