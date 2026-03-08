from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import MetaTrader5 as mt5  # type: ignore

def repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def load_config() -> Dict[str, Any]:
    cfg_path = os.path.join(os.path.dirname(__file__), "vm14_5_config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)

def read_input_assets() -> List[str]:
    assets_path = os.path.join(os.path.dirname(__file__), "InputAsset.txt")
    with open(assets_path, "r", encoding="utf-8") as f:
        out: List[str] = []
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            out.append(s)
        return out

def ensure_events_path(cfg: Dict[str, Any]) -> str:
    runtime_dir = cfg.get("runtime_dir", "runtime")
    events_path = cfg.get("events_path", os.path.join(runtime_dir, "events.jsonl"))

    runtime_abs = os.path.join(repo_root(), runtime_dir)
    events_abs = os.path.join(repo_root(), events_path)

    os.makedirs(runtime_abs, exist_ok=True)
    os.makedirs(os.path.dirname(events_abs), exist_ok=True)
    return events_abs

def append_event(events_abs: str, payload: Dict[str, Any]) -> None:
    with open(events_abs, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

def risk_ok(cfg: Dict[str, Any], symbol: str, side: str, volume: float) -> tuple[bool, str]:
    risk = cfg.get("risk", {}) or {}

    if not risk.get("enabled", True):
        return False, "risk.disabled"

    allowed_symbols = risk.get("allowed_symbols", []) or []
    if allowed_symbols and symbol not in allowed_symbols:
        return False, "symbol.not_allowed"

    allowed_types = risk.get("allowed_order_types", []) or []
    if allowed_types and side.upper() not in allowed_types:
        return False, "side.not_allowed"

    max_vol = float(risk.get("max_volume_per_trade", 0.01))
    if volume > max_vol:
        return False, "volume.too_large"

    return True, "ok"

def build_market_request(cfg: Dict[str, Any], symbol: str, side: str, volume: float) -> Dict[str, Any]:
    mt5_cfg = cfg.get("mt5", {}) or {}
    deviation = int(mt5_cfg.get("deviation", 20))
    magic = int(mt5_cfg.get("magic", 145001))
    comment = str(mt5_cfg.get("comment", "VM14.5"))

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"tick.none: {mt5.last_error()}")

    side = side.upper()
    order_type = mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL
    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

    return {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type,
        "price": float(price),
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

def main() -> None:
    cfg = load_config()
    assets = read_input_assets()
    events_abs = ensure_events_path(cfg)

    ts0 = datetime.now(timezone.utc).isoformat()
    append_event(events_abs, {"ts": ts0, "type": "startup", "assets_count": len(assets)})

    if not mt5.initialize(path=(cfg.get("mt5", {}) or {}).get("path") or None):
        append_event(events_abs, {"ts": ts0, "type": "error", "where": "initialize", "err": str(mt5.last_error())})
        print("initialize() failed:", mt5.last_error())
        return

    risk = cfg.get("risk", {}) or {}
    dry_run = bool(risk.get("dry_run", True))

    for symbol in assets:
        ts = datetime.now(timezone.utc).isoformat()

        if not mt5.symbol_select(symbol, True):
            append_event(events_abs, {"ts": ts, "type": "symbol_select_failed", "symbol": symbol, "err": str(mt5.last_error())})
            continue

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            append_event(events_abs, {"ts": ts, "type": "tick_failed", "symbol": symbol, "err": str(mt5.last_error())})
            continue

        append_event(events_abs, {"ts": ts, "type": "tick", "symbol": symbol, "bid": tick.bid, "ask": tick.ask})

        side = "BUY"
        volume = 0.01
        ok, reason = risk_ok(cfg, symbol, side, volume)
        if not ok:
            append_event(events_abs, {"ts": ts, "type": "order_blocked", "symbol": symbol, "side": side, "volume": volume, "reason": reason})
            continue

        try:
            request = build_market_request(cfg, symbol, side, volume)
        except Exception as e:
            append_event(events_abs, {"ts": ts, "type": "order_prepare_failed", "symbol": symbol, "err": str(e)})
            continue

        if dry_run:
            append_event(events_abs, {"ts": ts, "type": "order_dry_run", "symbol": symbol, "request": request})
        else:
            result = mt5.order_send(request)
            append_event(events_abs, {"ts": ts, "type": "order_send", "symbol": symbol, "request": request, "result": str(result)})

    mt5.shutdown()
    append_event(events_abs, {"ts": datetime.now(timezone.utc).isoformat(), "type": "shutdown"})


if __name__ == "__main__":
    main()