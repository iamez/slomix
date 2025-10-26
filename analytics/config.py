"""
FIVEEYES Analytics Configuration
Safe, modular configuration with feature flags
"""

import os
import json
from pathlib import Path
from typing import Dict, Any

# Default configuration
DEFAULT_CONFIG = {
    "synergy_analytics": {
        "enabled": False,  # Disabled by default - safety first!
        "min_games_threshold": 10,  # Minimum games together for valid synergy
        "cache_results": True,  # Cache synergy queries in memory
        "auto_recalculate": False,  # Auto-recalculate synergies daily
        "max_team_size": 6,  # Maximum team size for team_builder
        "commands": {
            "synergy": True,
            "best_duos": True,
            "team_builder": True,
            "player_impact": True
        }
    },
    "performance": {
        "query_timeout": 5,  # Seconds before query timeout
        "max_concurrent_queries": 3,
        "cache_ttl": 3600  # Cache time-to-live in seconds
    },
    "error_handling": {
        "fail_silently": True,  # Don't crash bot on analytics errors
        "log_errors": True,
        "notify_admin_on_error": False,
        "admin_channel_id": None
    }
}

class FiveEyesConfig:
    """Configuration manager for FIVEEYES analytics"""
    
    def __init__(self, config_path: str = "fiveeyes_config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    user_config = json.load(f)
                # Merge with defaults
                config = DEFAULT_CONFIG.copy()
                config.update(user_config)
                return config
            except Exception as e:
                print(f"Warning: Could not load config from {self.config_path}: {e}")
                print("Using default configuration")
                return DEFAULT_CONFIG.copy()
        else:
            # Create default config file
            self._save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
    
    def _save_config(self, config: Dict[str, Any]):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save config to {self.config_path}: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value using dot notation"""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self._save_config(self.config)
    
    def is_enabled(self) -> bool:
        """Check if synergy analytics is enabled"""
        return self.get('synergy_analytics.enabled', False)
    
    def is_command_enabled(self, command: str) -> bool:
        """Check if specific command is enabled"""
        if not self.is_enabled():
            return False
        return self.get(f'synergy_analytics.commands.{command}', False)
    
    def enable(self):
        """Enable synergy analytics"""
        self.set('synergy_analytics.enabled', True)
        print("✅ FIVEEYES synergy analytics ENABLED")
    
    def disable(self):
        """Disable synergy analytics"""
        self.set('synergy_analytics.enabled', False)
        print("⚠️  FIVEEYES synergy analytics DISABLED")


# Global config instance
config = FiveEyesConfig()


# Helper functions
def is_enabled() -> bool:
    """Quick check if analytics is enabled"""
    return config.is_enabled()


def is_command_enabled(command: str) -> bool:
    """Quick check if command is enabled"""
    return config.is_command_enabled(command)
