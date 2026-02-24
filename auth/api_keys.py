import hashlib
import secrets


def generate_api_key(agent_name: str) -> tuple[str, str, str]:
    """
    Generate an API key for an agent.
    Returns: (full_key, key_hash, key_prefix)

    Format: ak_{agent_name}_{32_hex_chars}
    """
    random_part = secrets.token_hex(16)
    full_key = f"ak_{agent_name}_{random_part}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = full_key[:20]
    return full_key, key_hash, key_prefix


def hash_api_key(key: str) -> str:
    """Hash a raw API key for DB comparison."""
    return hashlib.sha256(key.encode()).hexdigest()
