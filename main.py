from openai import OpenAI
import time
from datetime import datetime
import json
import re
from config import *
from log import *
from robinhood import *
from bot import *
import asyncio
from zoneinfo import ZoneInfo
import threading


# Initialize session and login
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Figure out if the program has run today, if not, update the date
def has_run_today():
    today = datetime.now().strftime('%Y-%m-%d')
    last_run = ""
    try:
        with open("last_run.txt", "r") as f:
            last_run = f.read()
    except FileNotFoundError:
        with open("last_run.txt", "w") as f:
            f.write(today)
    if today != last_run:
        with open("last_run.txt", "w") as f:
            f.write(today)
    return today == last_run


# Make AI request to OpenAI API 
def make_ai_request(prompt):
    ai_resp = openai_client.chat.completions.create(
        model=OPENAI_MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )
    return ai_resp


# Parse AI response
def parse_ai_response(ai_response):
    try:
        ai_content = re.sub(r'```json|```', '', ai_response.choices[0].message.content.strip())
        decisions = json.loads(ai_content)
    except json.JSONDecodeError:
        raise Exception("Invalid JSON response from OpenAI: " + ai_response.choices[0].message.content.strip())
    return decisions


# Get AI amount guidelines
def get_ai_amount_guidelines():
    sell_guidelines = []
    if MIN_SELLING_AMOUNT_USD is not False:
        sell_guidelines.append(f"Minimum amount {MIN_SELLING_AMOUNT_USD} USD")
    if MAX_SELLING_AMOUNT_USD is not False:
        sell_guidelines.append(f"Maximum amount {MAX_SELLING_AMOUNT_USD} USD")
    sell_guidelines = ", ".join(sell_guidelines) if sell_guidelines else None

    buy_guidelines = []
    if MIN_BUYING_AMOUNT_USD is not False:
        buy_guidelines.append(f"Minimum amount {MIN_BUYING_AMOUNT_USD} USD")
    if MAX_BUYING_AMOUNT_USD is not False:
        buy_guidelines.append(f"Maximum amount {MAX_BUYING_AMOUNT_USD} USD")
    buy_guidelines = ", ".join(buy_guidelines) if buy_guidelines else None

    return sell_guidelines, buy_guidelines


# Make AI-based decisions on stock portfolio and watchlist
def make_ai_decisions(buying_power, portfolio_overview, watchlist_overview):
    constraints = [
        f"- Initial budget: {buying_power} USD",
        f"- Max portfolio size: {PORTFOLIO_LIMIT} stocks",
    ]
    sell_guidelines, buy_guidelines = get_ai_amount_guidelines()
    if sell_guidelines:
        constraints.append(f"- Sell Amounts Guidelines: {sell_guidelines}")
    if buy_guidelines:
        constraints.append(f"- Buy Amounts Guidelines: {buy_guidelines}")
    if len(TRADE_EXCEPTIONS) > 0:
        constraints.append(f"- Excluded stocks: {', '.join(TRADE_EXCEPTIONS)}")

    ai_prompt = (
        "**Context:**\n"
        f"Today is {datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%dT%H:%M:%SZ')}.{chr(10)}"
        f"You are a short to medium-term investment advisor managing a Robinhood stock portfolio.{chr(10)}"
        f"You analyze market conditions every {RUN_INTERVAL_SECONDS} seconds and make investment decisions.{chr(10)}{chr(10)}"
        f"You should analyze the portfolio and watchlist data to make decisions on buying, selling, or holding stocks.{chr(10)}{chr(10)}"
        f"You should NEVER open and close the same position within the same trading week, unless there is a significant change in the stock's fundamentals (50% +/- 5%).{chr(10)}{chr(10)}"
        f"Robinhood allows traders to trade fractional stocks, (e.g., 0.5 shares) so make sure to take that into account when you are making your decisions and analyzing data.{chr(10)}{chr(10)}"
        "**Constraints:**\n"
        f"{chr(10).join(constraints)}{chr(10)}"
        f"(Note: These constraints may include guidelines such as risk tolerance, trading limits, or other investment rules.){chr(10)}{chr(10)}"
        "**Stock Data:**\n"
        f"The JSON below provides a combined view of your portfolio and watchlist data. It includes details like current holdings, performance metrics, potential stock targets, and key market indicators.{chr(10)}"
        "```json\n"
        f"{json.dumps({**portfolio_overview, **watchlist_overview}, indent=1)}{chr(10)}"
        "```\n\n"
        "**Response Format:**\n"
        "Return your decisions in a JSON array with this structure:\n"
        "```json\n"
        "[\n"
        '  {"symbol": <symbol>, "decision": <decision>, "quantity": <quantity>},\n'
        "  ...\n"
        "]\n"
        "```\n"
        "- <symbol>: Stock symbol.\n"
        "- <decision>: One of `buy`, `sell`, or `hold`.\n"
        f"- <quantity>: Recommended transaction quantity (number of shares). For a 'hold' decision, use zero.{chr(10)}{chr(10)}"
        "**Instructions:**\n"
        f"- Provide only the JSON output with no additional text.{chr(10)}"
        "- Return an empty array if no actions are necessary."
    )
    log_debug(f"AI making-decisions prompt:{chr(10)}{ai_prompt}")
    ai_response = make_ai_request(ai_prompt)
    log_debug(f"AI making-decisions response:{chr(10)}{ai_response.choices[0].message.content.strip()}")
    decisions = parse_ai_response(ai_response)
    return decisions


# Filter AI hallucinations
def filter_ai_hallucinations(decisions):
    # Filter if it's sell or buy with 0 quantity
    decisions = [decision for decision in decisions if decision['decision'] == "hold" or decision['quantity'] > 0]
    return decisions

# Limit watchlist stocks based on the current week number
def limit_watchlist_stocks(watchlist_stocks, limit):
    if len(watchlist_stocks) <= limit:
        return watchlist_stocks

    # Sort watchlist stocks by symbol
    watchlist_stocks = sorted(watchlist_stocks, key=lambda x: x['symbol'])

    # Get the current month number
    current_month = datetime.now().month

    # Calculate the number of parts
    num_parts = (len(watchlist_stocks) + limit - 1) // limit  # Ceiling division

    # Determine the part to return based on the current month number
    part_index = (current_month - 1) % num_parts
    start_index = part_index * limit
    end_index = min(start_index + limit, len(watchlist_stocks))

    return watchlist_stocks[start_index:end_index]


# Main trading bot function
def trading_bot():
    log_info("Getting portfolio stocks...")
    portfolio_stocks = get_portfolio_stocks()

    log_debug(f"Portfolio stocks total: {len(portfolio_stocks)}")

    portfolio_stocks_value = 0
    for stock in portfolio_stocks.values():
        portfolio_stocks_value += float(stock['price']) * float(stock['quantity'])
    portfolio = [f"{symbol} ({round(float(stock['price']) * float(stock['quantity']) / portfolio_stocks_value * 100, 2)}%)" for symbol, stock in portfolio_stocks.items()]
    log_info(f"Portfolio stocks to proceed: {'None' if len(portfolio) == 0 else ', '.join(portfolio)}")

    log_info("Prepare portfolio stocks for AI analysis...")
    portfolio_overview = {}
    for symbol, stock_data in portfolio_stocks.items():
        historical_data_day = get_historical_data(symbol, interval="5minute", span="day")
        historical_data_year = get_historical_data(symbol, interval="day", span="year")
        ratings_data = get_ratings(symbol)
        portfolio_overview[symbol] = extract_my_stocks_data(stock_data)
        portfolio_overview[symbol] = enrich_with_rsi(portfolio_overview[symbol], historical_data_day, symbol)
        portfolio_overview[symbol] = enrich_with_vwap(portfolio_overview[symbol], historical_data_day, symbol)
        portfolio_overview[symbol] = enrich_with_moving_averages(portfolio_overview[symbol], historical_data_year, symbol)
        portfolio_overview[symbol] = enrich_with_analyst_ratings(portfolio_overview[symbol], ratings_data, symbol)

    log_info("Getting watchlist stocks...")
    watchlist_stocks = []
    for watchlist_name in WATCHLIST_NAMES:
        try:
            watchlist_stocks.extend(get_watchlist_stocks(watchlist_name))
            watchlist_stocks = [dict(t) for t in {tuple(d.items()) for d in watchlist_stocks}]
        except Exception as e:
            log_error(f"Error getting watchlist stocks for {watchlist_name}: {e}")

    log_debug(f"Watchlist stocks total: {len(watchlist_stocks)}")

    watchlist_overview = {}
    if len(watchlist_stocks) > 0:
        log_debug(f"Limiting watchlist stocks to overview limit of {WATCHLIST_OVERVIEW_LIMIT}...")
        watchlist_stocks = limit_watchlist_stocks(watchlist_stocks, WATCHLIST_OVERVIEW_LIMIT)

        log_debug(f"Removing portfolio stocks from watchlist...")
        watchlist_stocks = [stock for stock in watchlist_stocks if stock['symbol'] not in portfolio_stocks.keys()]

        log_info(f"Watchlist stocks to proceed: {', '.join([stock['symbol'] for stock in watchlist_stocks])}")

        log_info("Prepare watchlist overview for AI analysis...")
        for stock_data in watchlist_stocks:
            symbol = stock_data['symbol']
            historical_data_day = get_historical_data(symbol, interval="5minute", span="day")
            historical_data_year = get_historical_data(symbol, interval="day", span="year")
            ratings_data = get_ratings(symbol)
            watchlist_overview[symbol] = extract_watchlist_data(stock_data)
            watchlist_overview[symbol] = enrich_with_rsi(watchlist_overview[symbol], historical_data_day, symbol)
            watchlist_overview[symbol] = enrich_with_vwap(watchlist_overview[symbol], historical_data_day, symbol)
            watchlist_overview[symbol] = enrich_with_moving_averages(watchlist_overview[symbol], historical_data_year, symbol)
            watchlist_overview[symbol] = enrich_with_analyst_ratings(watchlist_overview[symbol], ratings_data, symbol)

    if len(portfolio_overview) == 0 and len(watchlist_overview) == 0:
        log_warning("No stocks to analyze, skipping AI-based decision-making...")
        return {}

    decisions_data = []
    trading_results = {}

    try:
        log_info("Making AI-based decision...")
        buying_power = get_buying_power()
        decisions_data = make_ai_decisions(buying_power, portfolio_overview, watchlist_overview)
    except Exception as e:
        log_error(f"Error making AI-based decision: {e}")

    log_info("Filtering AI hallucinations...")
    decisions_data = filter_ai_hallucinations(decisions_data)

    if len(decisions_data) == 0:
        log_info("No decisions to execute")
        return trading_results

    log_info("Executing decisions...")

    for decision_data in decisions_data:
        symbol = decision_data['symbol']
        decision = decision_data['decision']
        quantity = decision_data['quantity']
        log_info(f"{symbol} > Decision: {decision} of {quantity}")

        # TODO: Move to filter_ai_hallucinations function
        if symbol in TRADE_EXCEPTIONS:
            trading_results[symbol] = {"symbol": symbol, "quantity": quantity, "decision": decision, "result": "error", "details": "Trade exception"}
            log_warning(f"{symbol} > Decision skipped due to trade exception")
            continue

        if decision == "sell":
            try:
                sell_resp = sell_stock(symbol, quantity)
                if sell_resp and 'id' in sell_resp:
                    if sell_resp['id'] == "demo":
                        trading_results[symbol] = {"symbol": symbol, "quantity": quantity, "decision": "sell", "result": "success", "details": "Demo mode"}
                        log_info(f"{symbol} > Demo > Sold {quantity} stocks")
                    elif sell_resp['id'] == "cancelled":
                        trading_results[symbol] = {"symbol": symbol, "quantity": quantity, "decision": "sell", "result": "cancelled", "details": "Cancelled by user"}
                        log_info(f"{symbol} > Sell cancelled by user")
                    else:
                        details = extract_sell_response_data(sell_resp)
                        trading_results[symbol] = {"symbol": symbol, "quantity": quantity, "decision": "sell", "result": "success", "details": details}
                        log_info(f"{symbol} > Sold {quantity} stocks")
                else:
                    details = sell_resp['detail'] if 'detail' in sell_resp else sell_resp
                    trading_results[symbol] = {"symbol": symbol, "quantity": quantity, "decision": "sell", "result": "error", "details": details}
                    log_error(f"{symbol} > Error selling: {details}")
            except Exception as e:
                trading_results[symbol] = {"symbol": symbol, "quantity": quantity, "decision": "sell", "result": "error", "details": str(e)}
                log_error(f"{symbol} > Error selling: {e}")

        if decision == "buy":
            try:
                buy_resp = buy_stock(symbol, quantity)
                if buy_resp and 'id' in buy_resp:
                    if buy_resp['id'] == "demo":
                        trading_results[symbol] = {"symbol": symbol, "quantity": quantity, "decision": "buy", "result": "success", "details": "Demo mode"}
                        log_info(f"{symbol} > Demo > Bought {quantity} stocks")
                    elif buy_resp['id'] == "cancelled":
                        trading_results[symbol] = {"symbol": symbol, "quantity": quantity, "decision": "buy", "result": "cancelled", "details": "Cancelled by user"}
                        log_info(f"{symbol} > Buy cancelled by user")
                    else:
                        details = extract_buy_response_data(buy_resp)
                        trading_results[symbol] = {"symbol": symbol, "quantity": quantity, "decision": "buy", "result": "success", "details": details}
                        log_info(f"{symbol} > Bought {quantity} stocks")
                else:
                    details = buy_resp['detail'] if 'detail' in buy_resp else buy_resp
                    trading_results[symbol] = {"symbol": symbol, "quantity": quantity, "decision": "buy", "result": "error", "details": details}
                    log_error(f"{symbol} > Error buying: {details}")
            except Exception as e:
                trading_results[symbol] = {"symbol": symbol, "quantity": quantity, "decision": "buy", "result": "error", "details": str(e)}
                log_error(f"{symbol} > Error buying: {e}")

    return trading_results


running = True

def listen_for_stop():
    global running
    while running:
        log_info("Enter 'stop' to stop the bot: ")
        command = input()
        if command.lower() == "stop":
            running = False
            log_info("Stopping the bot...")


# Run trading bot in a loop
async def main():
    await login_to_robinhood()
    
    # start the thread to listen for stop command
    stop_thread = threading.Thread(target=listen_for_stop)
    stop_thread.start()

    while running:
        try:
            if is_market_open():
                run_interval_seconds = RUN_INTERVAL_SECONDS
                log_info(f"Market is open, running trading bot in {MODE} mode...")

                trading_results = trading_bot()

                sold_stocks = [f"{result['symbol']} ({result['quantity']})" for result in trading_results.values() if result['decision'] == "sell" and result['result'] == "success"]
                bought_stocks = [f"{result['symbol']} ({result['quantity']})" for result in trading_results.values() if result['decision'] == "buy" and result['result'] == "success"]
                errors = [f"{result['symbol']} ({result['details']})" for result in trading_results.values() if result['result'] == "error"]
                log_info(f"Sold: {'None' if len(sold_stocks) == 0 else ', '.join(sold_stocks)}")
                log_info(f"Bought: {'None' if len(bought_stocks) == 0 else ', '.join(bought_stocks)}")
                log_info(f"Errors: {'None' if len(errors) == 0 else ', '.join(errors)}")
            else:
                run_interval_seconds = 60
                log_info("Market is closed, waiting for next run...")
        except Exception as e:
            run_interval_seconds = 60
            log_error(f"Trading bot error: {e}")

        log_info(f"Waiting for {run_interval_seconds} seconds...")
        time.sleep(run_interval_seconds)
    
    log_info("Bot stopped")


# Run the main function
if __name__ == '__main__':
    confirm = input(f"Are you sure you want to run the bot in {MODE} mode? (yes/no): ")
    if confirm.lower() not in ["yes", "y"]:
        log_warning("Exiting the bot...")
        exit()
    asyncio.run(main())
