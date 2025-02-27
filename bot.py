# Importing all the necessary libraries
from openai import OpenAI
import time
from datetime import datetime
import json
import re
from zoneinfo import ZoneInfo

# import config, log, and main modules
from config import *
from log import *
from main import has_run_today

# Initialize session and login
openai_client = OpenAI(api_key=OPENAI_API_KEY)
assistant = openai_client.beta.assistants.retrieve(OPENAI_ASSISTANT_ID)

# Initialize some variables
today = datetime.now(tz=ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
ThreadID = ""

# if the program has not run yet today, create a new assistant thread
if has_run_today() == False:
    Thread = openai_client.beta.threads.create(
        messages=[
            {
                "role": "assistant",
                "content": f"Good Morning! It is {today}. I'm here to help you with your trading decisions, what would you like to do first?",
            }
        ],
    )
    # get thread ID from response
    ThreadID = Thread.id
    # log the thread ID
    log_debug(f"Created new daily thread with thread ID: {ThreadID}")

# if the program has already run today, or a thread is already active, log it
log_info("A RobinBot thread has been created for today, or is already active.")
