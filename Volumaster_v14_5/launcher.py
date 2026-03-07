import os
import json
from MetaTrader5 import MetaTrader5 as mt5

# Load config
config_path = os.path.join(os.path.dirname(__file__), 'vm14_5_config.json')
with open(config_path) as config_file:
    cfg = json.load(config_file)

# Ensure runtime/events.jsonl exists
if not os.path.exists('runtime/events.jsonl'):
    os.makedirs('runtime', exist_ok=True)

# Read symbols from InputAsset.txt
input_file_path = os.path.join(os.path.dirname(__file__), 'InputAsset.txt')
with open(input_file_path) as input_file:
    symbols = input_file.readlines()

# Initialize MT5
mt5.initialize()

for symbol in symbols:
    symbol = symbol.strip()
    # Select the trading symbol
    if mt5.symbol_select(symbol):
        # Retrieve ticks
ticks = mt5.copy_ticks_from(symbol, dt.datetime.now(), 10, mt5.COPY_TICKS_ALL)
        # Append JSONL event
        with open('runtime/events.jsonl', 'a') as jsonl_file:
            for tick in ticks:
                jsonl_file.write(json.dumps(tick) + '\n')
        # Simulate BUY order
        risk = cfg['risk']
        buy_volume = 0.01
        # Safe dry-run market order simulation
        # (Include risk guardrails accordingly)
        print(f'Simulating BUY {buy_volume} lots for {symbol} with risk: {risk}')
    else:
        print(f'Symbol {symbol} not available')

# Shutdown MT5
mt5.shutdown()