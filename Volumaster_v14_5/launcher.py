import MetaTrader5 as mt5
import json
import os
import datetime

# Load configuration
with open('vm14_5_config.json', 'r') as config_file:
    config = json.load(config_file)

# Ensure runtime/events.jsonl
os.makedirs('runtime', exist_ok=True)

# Initialize MetaTrader 5
if not mt5.initialize():
    print("initialize() failed, error code =", mt5.last_error())
    quit()

# Select the first configured symbol
symbol = config['symbols'][0]
if not mt5.symbol_select(symbol, True):
    print(f"Symbol {symbol} not found, error code =", mt5.last_error())
    mt5.shutdown()
    quit()

# Fetch a tick
tick = mt5.symbol_info_tick(symbol)
if tick is None:
    print(f"Failed to get tick for {symbol}, error code =", mt5.last_error())
    mt5.shutdown()
    quit()

# Prepare events
startup_event = {"event": "startup", "timestamp": "{}".format(datetime.datetime.utcnow())}
with open('runtime/events.jsonl', 'a') as events_file:
    events_file.write(json.dumps(startup_event) + '\n')
    tick_event = {"event": "tick", "symbol": symbol, "bid": tick.bid, "ask": tick.ask, "timestamp": "{}".format(datetime.datetime.utcnow())}
    events_file.write(json.dumps(tick_event) + '\n')

# Shutdown MetaTrader 5
mt5.shutdown()