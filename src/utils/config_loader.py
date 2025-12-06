"""Configuration loader utilities with validation."""

import json
import os
from typing import Dict, Any


def load_user_needs(config_path: str = "data/user_needs.json") -> Dict[str, Any]:
    """
    Load and validate user needs configuration.

    Args:
        config_path: Path to user_needs.json file

    Returns:
        Dictionary containing usage_profile and standard_costs

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is malformed or missing required keys
        json.JSONDecodeError: If file contains invalid JSON
    """
    # Resolve relative path from project root
    if not os.path.isabs(config_path):
        # Get project root (2 levels up from this file)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, config_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"User needs configuration file not found: {config_path}\n"
            f"Please create data/user_needs.json with usage_profile and standard_costs."
        )

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in {config_path}: {e.msg}",
            e.doc,
            e.pos
        )

    # Validate required top-level keys
    required_keys = ['usage_profile', 'standard_costs']
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(
            f"Missing required keys in {config_path}: {missing_keys}\n"
            f"Required keys: {required_keys}"
        )

    # Validate usage_profile is not empty
    if not config['usage_profile']:
        raise ValueError(
            f"usage_profile in {config_path} cannot be empty.\n"
            f"Please specify at least one service usage (e.g., primary_care_visits: 4)"
        )

    # Validate standard_costs is not empty
    standard_costs = {k: v for k, v in config['standard_costs'].items() if k != 'description'}
    if not standard_costs:
        raise ValueError(
            f"standard_costs in {config_path} cannot be empty.\n"
            f"Please specify market rates for services (e.g., primary_care_visit: 200)"
        )

    # Validate numeric types in usage_profile
    for key, value in config['usage_profile'].items():
        if not isinstance(value, (int, float)):
            raise ValueError(
                f"Invalid value for '{key}' in usage_profile: {value}\n"
                f"Expected numeric value, got {type(value).__name__}"
            )
        if value < 0:
            raise ValueError(
                f"Invalid value for '{key}' in usage_profile: {value}\n"
                f"Values must be non-negative"
            )

    # Validate numeric types in standard_costs (excluding description)
    for key, value in standard_costs.items():
        if not isinstance(value, (int, float)):
            raise ValueError(
                f"Invalid value for '{key}' in standard_costs: {value}\n"
                f"Expected numeric value, got {type(value).__name__}"
            )
        if value < 0:
            raise ValueError(
                f"Invalid value for '{key}' in standard_costs: {value}\n"
                f"Values must be non-negative"
            )

    return config


def load_app_config(config_path: str = "data/config.json") -> Dict[str, Any]:
    """
    Load and validate application configuration.

    Args:
        config_path: Path to config.json file

    Returns:
        Dictionary containing app configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is malformed or missing required keys
        json.JSONDecodeError: If file contains invalid JSON
    """
    # Resolve relative path from project root
    if not os.path.isabs(config_path):
        # Get project root (2 levels up from this file)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, config_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Application configuration file not found: {config_path}\n"
            f"Please create data/config.json with app settings."
        )

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in {config_path}: {e.msg}",
            e.doc,
            e.pos
        )

    # Validate required keys
    required_keys = [
        'target_url',
        'zip_code',
        'family_type',
        'network_type',
        'pdf_download_timeout',
        'max_retries',
        'output_directory',
        'pdf_directory'
    ]
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(
            f"Missing required keys in {config_path}: {missing_keys}\n"
            f"Required keys: {required_keys}"
        )

    # Validate URL format
    if not config['target_url'].startswith(('http://', 'https://')):
        raise ValueError(
            f"Invalid target_url in {config_path}: {config['target_url']}\n"
            f"URL must start with http:// or https://"
        )

    # Validate timeout and retries are positive integers
    if not isinstance(config['pdf_download_timeout'], (int, float)) or config['pdf_download_timeout'] <= 0:
        raise ValueError(
            f"Invalid pdf_download_timeout in {config_path}: {config['pdf_download_timeout']}\n"
            f"Must be a positive number"
        )

    if not isinstance(config['max_retries'], int) or config['max_retries'] < 0:
        raise ValueError(
            f"Invalid max_retries in {config_path}: {config['max_retries']}\n"
            f"Must be a non-negative integer"
        )

    # Validate directory paths are strings
    for dir_key in ['output_directory', 'pdf_directory']:
        if not isinstance(config[dir_key], str) or not config[dir_key]:
            raise ValueError(
                f"Invalid {dir_key} in {config_path}: {config[dir_key]}\n"
                f"Must be a non-empty string"
            )

    return config


def validate_configs() -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load and validate both user needs and app configuration.

    Returns:
        Tuple of (user_needs, app_config)

    Raises:
        FileNotFoundError: If either config file doesn't exist
        ValueError: If either config is malformed
        json.JSONDecodeError: If either file contains invalid JSON
    """
    user_needs = load_user_needs()
    app_config = load_app_config()
    return user_needs, app_config
