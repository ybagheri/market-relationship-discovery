from functools import lru_cache

from market_relationship_discovery.config.settings import Settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
