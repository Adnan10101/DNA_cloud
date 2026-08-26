import os
from dotenv import load_dotenv

load_dotenv()

GITEA_API_URL = os.getenv("GITEA_API_URL")
GITEA_TOKEN = os.getenv("GITEA_TOKEN")
REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")
PV_FILE_PATH = os.getenv("PV_FILE_PATH")