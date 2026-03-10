import json
import os
import logging
import logging.handlers
from functools import lru_cache
import colorlog
from pathlib import Path
from typing import Dict

@lru_cache(maxsize=1)
def get_config() -> Dict:
    config_dir = Path(__file__).parent
    config_path = config_dir / "config.json"

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
        
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

def setup_logging() -> None:
    config = get_config()
    log_config = config['logging_config']
    console_config = log_config['console_output']
    file_config = log_config['file_output']
    
    # Create logs directory if needed
    if file_config['enabled']:
        os.makedirs(file_config['log_dir'], exist_ok=True)
    
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    # Add console handler with colors
    if console_config['enabled']:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, console_config['level'].upper()))
        console_formatter = colorlog.ColoredFormatter(
            '%(log_color)s' + console_config['format'],
            datefmt=console_config['date_format'],
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white'
            }
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # Add file handler with rotation
    if file_config['enabled']:
        file_path = os.path.join(file_config['log_dir'], file_config['filename'])
        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=file_config['max_bytes'],
            backupCount=file_config['backup_count']
        )
        file_handler.setLevel(getattr(logging, file_config['level'].upper()))
        file_formatter = logging.Formatter(
            fmt=file_config['format'],
            datefmt=file_config['date_format']
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

