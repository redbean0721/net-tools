import os
import asyncio
import platform
import subprocess
import websockets
import logging

# === Logging Setup ===

# ✅ 改用標準 logging config，不依賴 uvicorn 的 LOGGING_CONFIG
class ColorizingStreamHandler(logging.StreamHandler):
    COLORS = {
        "INFO": "\033[0;32m",
        "WARNING": "\033[0;33m",
        "ERROR": "\033[0;31m",
        "CRITICAL": "\033[1;31m",
        "DEBUG": "\033[0;34m",
        "WHITE": "\033[0m",
    }

    def emit(self, record):
        msg = self.format(record)
        level_color = self.COLORS.get(record.levelname, self.COLORS["WHITE"])
        parts = msg.split(" - ", 1)
        if len(parts) < 2:
            self.stream.write(msg + "\n")
            return
        timestamp_part = parts[0]
        level_part = parts[1].split(":")[0]
        message_part = parts[1][len(level_part) + 1:]

        if record.levelname == "INFO":
            level_spacing = "     "
        elif record.levelname == "WARNING":
            level_spacing = "  "
        elif record.levelname == "ERROR":
            level_spacing = "    "
        elif record.levelname == "DEBUG":
            level_spacing = "    "
        else:
            level_spacing = " "

        colored_msg = f"{timestamp_part} - {level_color}{level_part}{ColorizingStreamHandler.COLORS['WHITE']}:{level_spacing}{message_part}"
        self.stream.write(f"{colored_msg}\n")

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = ColorizingStreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(handler)

setup_logging()
logger = logging.getLogger(__name__)

# === WebSocket Client Worker ===

API_WS_BASE_URL = "wss://api.redbean0721.com/api/net-tools/websocket"
NODE_NAME = os.getenv("NODE_NAME", "unknown-node")
API_WS_URL = f"{API_WS_BASE_URL}?node={NODE_NAME}"

def get_ping_command(host: str) -> list[str]:
    system = platform.system().lower()
    return ["ping", "-n" if system == "windows" else "-c", "4", host]

def get_traceroute_command(host: str) -> list[str]:
    system = platform.system().lower()
    return ["tracert" if system == "windows" else "traceroute", host]

async def run_command(command: list[str]) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(*command,
                                                    stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        return stdout.decode() if stdout else stderr.decode()
    except Exception as e:
        return f"❌ 執行錯誤：{str(e)}"

async def ws_worker():
    async with websockets.connect(API_WS_URL) as websocket:
        logger.info(f"[{NODE_NAME}] 已連線至 API：{API_WS_URL}")
        try:
            while True:
                message = await websocket.recv()
                logger.info(f"收到指令：{message}")

                parts = message.strip().split(maxsplit=1)
                if len(parts) != 2:
                    await websocket.send("❌ 格式錯誤，請用: ping <host> 或 traceroute <host>")
                    continue

                cmd, host = parts
                if cmd == "ping":
                    command = get_ping_command(host)
                elif cmd == "traceroute":
                    command = get_traceroute_command(host)
                else:
                    await websocket.send(f"❌ 不支援的指令: {cmd}")
                    continue

                output = await run_command(command)
                await websocket.send(output)
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"[{NODE_NAME}] WebSocket 已斷線")

if __name__ == "__main__":
    if not os.getenv("NODE_NAME"):
        logger.critical("❌ 未設定環境變數 NODE_NAME，請以 -e NODE_NAME=your-node-name 設定容器節點名稱")
        exit(1)

    while True:
        try:
            asyncio.run(ws_worker())
        except Exception as e:
            logger.error(f"無法連線 API，5 秒後重試：{e}")
            asyncio.run(asyncio.sleep(5))
