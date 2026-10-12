import os

from dotenv import load_dotenv


load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("STREAMLIT_API_TIMEOUT", "30"))
GENERATION_TIMEOUT_SECONDS = int(os.getenv("STREAMLIT_GENERATION_TIMEOUT", "600"))
MAX_RETRIES = int(os.getenv("STREAMLIT_API_RETRIES", "3"))
