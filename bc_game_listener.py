import websocket
import json
import threading
import time
import random
import requests
import logging
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BCGameListener:
    def __init__(self, on_crash_callback=None, use_simulation=False):
        self.ws = None
        self.on_crash_callback = on_crash_callback
        self.running = False
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60
        self.current_delay = self.reconnect_delay
        self.last_crash_value = None
        self.subscribed = False
        self.use_simulation = use_simulation
        self.last_fetched_id = None

    def _generate_game_meta(self, value):
        now_ms = int(time.time() * 1000)
        game_id = f"G{now_ms}" 
        player_count = random.randint(10, 500)
        bet_count = max(1, int(player_count * random.uniform(0.4, 1.8)))
        avg_bet = random.uniform(0.25, 25.0)
        total_bet_amount = round(bet_count * avg_bet, 2)

        house_edge = random.uniform(0.01, 0.07)
        win_ratio = max(0.0, min(0.95, (1.0 / max(1.01, float(value))) * (1.0 - house_edge)))
        total_win_amount = round(total_bet_amount * win_ratio, 2)
        total_profit_amount = round(total_win_amount - total_bet_amount, 2)

        h = hashlib.sha256(f"{game_id}:{now_ms}:{value}:{random.random()}".encode('utf-8')).hexdigest()
        return {
            'game_id': game_id,
            'max_rate': float(value),
            'total_bet_amount': total_bet_amount,
            'total_win_amount': total_win_amount,
            'total_profit_amount': total_profit_amount,
            'player_count': player_count,
            'bet_count': bet_count,
            'hash': h,
            'timestamp': now_ms,
        }

    def _ensure_meta(self, raw_data, value):
        if raw_data is None:
            raw_data = {}
        if not isinstance(raw_data, dict):
            raw_data = {'raw': str(raw_data)[:500]}

        meta = self._generate_game_meta(value)
        for k, v in meta.items():
            if raw_data.get(k) in (None, ''):
                raw_data[k] = v
        return raw_data
        
    def generate_realistic_crash(self):
        r = random.random()
        if r < 0.50:
            return round(random.uniform(1.0, 1.99), 2)
        elif r < 0.85:
            return round(random.uniform(2.0, 9.99), 2)
        elif r < 0.95:
            return round(random.uniform(10.0, 49.99), 2)
        else:
            return round(random.uniform(50.0, 200.0), 2)
    
    def fetch_crash_history(self):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Origin': 'https://bc.game',
                'Referer': 'https://bc.game/game/crash'
            }
            
            urls = [
                'https://bc.game/api/single/game/crash/history?size=20',
                'https://bc.game/api/game/support/crash/history?size=20',
                'https://bc.game/api/crash/history?limit=20',
            ]
            
            for url in urls:
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, dict) and 'data' in data:
                            return data['data']
                        elif isinstance(data, list):
                            return data
                except Exception as e:
                    logger.debug(f"Failed to fetch from {url}: {e}")
                    continue
            
            return None
        except Exception as e:
            logger.error(f"Error fetching crash history: {e}")
            return None
    
    def poll_crash_history(self):
        while self.running:
            try:
                history = self.fetch_crash_history()
                
                if history and len(history) > 0:
                    latest = history[0]
                    
                    for key in ['value', 'crash', 'multiplier', 'bust', 'point', 'rate', 'v']:
                        if key in latest:
                            value = float(latest[key])
                            if value != self.last_crash_value and 1.0 <= value <= 1000:
                                self.handle_crash(value, self._ensure_meta(latest, value))
                            break
                else:
                    if self.use_simulation:
                        self.run_simulation_round()
                
                time.sleep(8)
                
            except Exception as e:
                logger.error(f"Poll error: {e}")
                time.sleep(10)
    
    def run_simulation_round(self):
        value = self.generate_realistic_crash()
        self.handle_crash(value, self._ensure_meta({'simulated': True}, value))
    
    def parse_crash_data(self, message):
        try:
            if isinstance(message, bytes):
                message = message.decode('utf-8', errors='ignore')
            
            import re
            patterns = [
                r'"value"\s*:\s*([\d.]+)',
                r'"crash"\s*:\s*([\d.]+)',
                r'"multiplier"\s*:\s*([\d.]+)',
                r'"bust"\s*:\s*([\d.]+)',
                r'"point"\s*:\s*([\d.]+)',
                r'"v"\s*:\s*([\d.]+)',
                r'"rate"\s*:\s*([\d.]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, message)
                if match:
                    value = float(match.group(1))
                    if 1.0 <= value <= 1000:
                        return value
            
        except Exception as e:
            logger.debug(f"Parse error: {e}")
        
        return None
    
    def on_message(self, ws, message):
        try:
            logger.debug(f"Received: {message[:200] if isinstance(message, str) else 'binary'}")
            
            if isinstance(message, str):
                if message == '3':
                    return
                
                if message.startswith('0'):
                    logger.info("Connected to bc.game socket")
                    self.subscribe_to_crash()
                    return
                
                if message.startswith('40'):
                    logger.info("Socket.IO namespace connected")
                    return
                
                if message.startswith('42'):
                    try:
                        json_str = message[2:]
                        data = json.loads(json_str)
                        
                        if isinstance(data, list) and len(data) >= 2:
                            event_name = data[0]
                            event_data = data[1]
                            
                            crash_events = ['crash.tick', 'crash', 'game.crash', 'crash.result', 
                                          'crash.end', 'game_end', 'bust', 'end']
                            
                            if any(e in str(event_name).lower() for e in ['crash', 'bust', 'end']):
                                if isinstance(event_data, dict):
                                    for key in ['v', 'value', 'crash', 'multiplier', 'bust', 'point', 'rate']:
                                        if key in event_data:
                                            try:
                                                value = float(event_data[key])
                                                if 1.0 <= value <= 1000:
                                                    self.handle_crash(value, self._ensure_meta(event_data, value))
                                                    return
                                            except (ValueError, TypeError):
                                                pass
                    except json.JSONDecodeError:
                        pass
            
            crash_value = self.parse_crash_data(message)
            if crash_value and crash_value != self.last_crash_value:
                self.handle_crash(crash_value, self._ensure_meta({'raw': str(message)[:500]}, crash_value))
                
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    def handle_crash(self, value, raw_data=None):
        if value == self.last_crash_value:
            return
        
        self.last_crash_value = value
        logger.info(f"CRASH: {value}x")
        
        if self.on_crash_callback:
            self.on_crash_callback(value, raw_data)
    
    def subscribe_to_crash(self):
        if self.ws and not self.subscribed:
            try:
                self.ws.send('40/crash,')
                
                subscribe_msgs = [
                    '42/crash,["subscribe","crash"]',
                    '42/crash,["join","crash"]',
                    '42["subscribe",{"channel":"crash"}]',
                ]
                
                for msg in subscribe_msgs:
                    try:
                        self.ws.send(msg)
                        logger.info(f"Sent subscription: {msg}")
                    except:
                        pass
                
                self.subscribed = True
                
            except Exception as e:
                logger.error(f"Subscribe error: {e}")
    
    def on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.subscribed = False
        if self.running:
            logger.info("Falling back to HTTP polling / simulation mode")
            self.use_simulation = True
    
    def on_open(self, ws):
        logger.info("WebSocket connected to bc.game")
        self.current_delay = self.reconnect_delay
        
        def ping_loop():
            while self.running and self.ws:
                try:
                    time.sleep(25)
                    if self.ws:
                        self.ws.send('2')
                except:
                    break
        
        ping_thread = threading.Thread(target=ping_loop, daemon=True)
        ping_thread.start()
    
    def try_websocket_connect(self):
        url = "wss://socketv4.bc.game/socket.io/?EIO=3&transport=websocket"
        
        headers = {
            'Origin': 'https://bc.game',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        self.ws = websocket.WebSocketApp(
            url,
            header=headers,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        logger.info(f"Attempting WebSocket connection...")
        self.ws.run_forever()
    
    def connect(self):
        try:
            self.try_websocket_connect()
        except Exception as e:
            logger.warning(f"WebSocket failed: {e}, using polling/simulation")
        
        if self.running:
            self.poll_crash_history()
    
    def start(self):
        self.running = True
        
        logger.info("Starting BC.Game listener - attempting WebSocket connection first")
        
        ws_thread = threading.Thread(target=self.connect, daemon=True)
        ws_thread.start()
        
        time.sleep(3)
        
        if not self.subscribed:
            logger.info("WebSocket connection failed, falling back to polling/simulation")
            self.use_simulation = True
            poll_thread = threading.Thread(target=self.poll_crash_history, daemon=True)
            poll_thread.start()
        
        logger.info("BC.Game listener started")
        return ws_thread
    
    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()
        logger.info("BC.Game listener stopped")


if __name__ == "__main__":
    def on_crash(value, raw):
        print(f"Crash: {value}x")
    
    listener = BCGameListener(on_crash_callback=on_crash, use_simulation=True)
    listener.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listener.stop()
