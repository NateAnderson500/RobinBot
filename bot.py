# Importing all the necessary libraries
from openai import OpenAI
import time
from datetime import datetime
import json
import re
from zoneinfo import ZoneInfo

# import config and log
from config import *
from log import *

# Initialize session and login
openai_client = OpenAI(api_key=OPENAI_API_KEY)

