# Stores API keys, configs, environment variables

import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

DATABASE_URL = os.getenv('DATABASE_URL')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

class Config:
    STOCK_API_KEY = os.getenv('API_KEY_STOCK')
    NEWS_API_KEY = os.getenv('API_KEY_NEWS')
    # Add other configurations as needed