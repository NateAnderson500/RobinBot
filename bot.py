# Importing all the necessary libraries
from openai import OpenAI
from agents import *
import time
from datetime import datetime
import json
import re
from zoneinfo import ZoneInfo

# import config, log, and main modules
from config import *
from log import *
from main import has_run_today, portfolio_overview, watchlist_overview, set_constraints
from robinhood import *

# Initialize OpenAi Agent Through SDK
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize some global variables
today = datetime.now(tz=ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

