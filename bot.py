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
from main import has_run_today, portfolio_overview, watchlist_overview
from robinhood import *

# Initialize OpenAi agent
openai_client = OpenAI(api_key=OPENAI_API_KEY)
assistant = openai_client.beta.assistants.retrieve(OPENAI_ASSISTANT_ID)

# Initialize some global variables
today = datetime.now(tz=ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
ThreadID = ""

# if the program has not run yet today, create a new assistant thread
if has_run_today() == False:
    Thread = openai_client.beta.threads.create(
        messages=[
            {
                "role": "assistant",
                "content": f"Good Morning! It is {today}. I am ready to start trading! 🚀",
            }
        ],
    )
    # get thread ID from response
    ThreadID = Thread.id
    # log the thread ID
    log_debug(f"Created new daily thread with thread ID: {ThreadID}")

# if the program has already run today, or a thread is already active, log it
log_info("A RobinBot thread has been created for today, or is already active.")

# log that the agent is starting
log_info("Starting RobinBot agent...")

# main agent "loop"
def RobinBot( ThreadID, buying_power, portfolio_overview, watchlist_overview ):
    # set constraints (MIGHT MOVE THIS BACK TO MAIN, NOT SURE YET)
    def set_constraints():
        """
        Combines initial constraints with buying and selling guidelines
        into a single list.
        """
        constraints = [
            f"- Initial budget: {buying_power} USD",
            f"- Max portfolio size: {PORTFOLIO_LIMIT} stocks",
        ]

        # Build sell guidelines
        sell_guidelines_parts = []
        if MIN_SELLING_AMOUNT_USD is not False:
            sell_guidelines_parts.append(f"Minimum amount {MIN_SELLING_AMOUNT_USD} USD")
        if MAX_SELLING_AMOUNT_USD is not False:
            sell_guidelines_parts.append(f"Maximum amount {MAX_SELLING_AMOUNT_USD} USD")
        sell_guidelines = ", ".join(sell_guidelines_parts) if sell_guidelines_parts else None

        # Build buy guidelines
        buy_guidelines_parts = []
        if MIN_BUYING_AMOUNT_USD is not False:
            buy_guidelines_parts.append(f"Minimum amount {MIN_BUYING_AMOUNT_USD} USD")
        if MAX_BUYING_AMOUNT_USD is not False:
            buy_guidelines_parts.append(f"Maximum amount {MAX_BUYING_AMOUNT_USD} USD")
        buy_guidelines = ", ".join(buy_guidelines_parts) if buy_guidelines_parts else None

        # Build sell guidelines
        if sell_guidelines:
            constraints.append(f"- Sell Amounts Guidelines: {sell_guidelines}")
        if buy_guidelines:
            constraints.append(f"- Buy Amounts Guidelines: {buy_guidelines}")
        if TRADE_EXCEPTIONS:  # if TRADE_EXCEPTIONS list is not empty
            constraints.append(f"- Excluded stocks: {', '.join(TRADE_EXCEPTIONS)}")

        return constraints
    
    # sends message to RobinBot
    def send_and_receive_message( message ):
        """
        Sends a message to the RobinBot thread.
        """
        
        messageID = ""
        runID = ""
        
        
        message = openai_client.beta.threads.messages.create(
            f"ThreadID", 
            role="user", 
            content=f"input"
        )
        messageID = message.id
        log_debug(f"Sent message to RobinBot: {input} with ID: {messageID}")
        
        
        # sends the message
        run = openai_client.beta.threads.runs.create(
            thread_id=f"ThreadID",
            assistant_id=f"OPENAI_ASSISTANT_ID",
        )
        runID = run.id
        log_debug(f"Inited run to RobinBot: {run} with ID: {runID}")
        
        # wait for the response
        time.sleep(10)
        
        # get the response
        


    # the message that will be sent to RobinBot
    input = (
        f""
    )