import asyncio
import json
import logging
import os
import threading
import uuid
from concurrent.futures import Future
from typing import Any, Dict

import websockets
from websockets.asyncio.server import ServerConnection

logger = logging.getLogger(__name__)

WS_CONTROL_HOST = os.getenv("WS_CONTROL_HOST", "0.0.0.0")
WS_CONTROL_PORT = int(os.getenv("WS_CONTROL_PORT", "8765"))
WS_CONTROL_TOKEN = os.getenv("WS_CONTROL_TOKEN")
if not WS_CONTROL_TOKEN:
    raise RuntimeError("WS_CONTROL_TOKEN environment variable is not set")


class ControlHub:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._clients: dict[str, ServerConnection] = {}
        self._clients_lock = threading.Lock()
        self._pending: dict[str, Future] = {}
        self._pending_lock = threading.Lock()
        self._start_error: str | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_thread, name="control-hub", daemon=True)
        self._thread.start()
        self._started.wait(timeout=5)
        if self._start_error:
            logger.error("WS control hub failed to start: %s", self._start_error)
        else:
            logger.info("WS control hub listening on ws://%s:%s", self.host, self.port)

    def _run_thread(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._start_server())
        except Exception as e:
            self._start_error = str(e)
            self._started.set()
            return

        self._started.set()
        self.loop.run_forever()

    async def _start_server(self) -> None:
        await websockets.serve(
            self._handle_client,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=20,
        )

    async def _handle_client(self, websocket: ServerConnection) -> None:
        device_id = ""
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(raw)

            if data.get("type") != "register":
                await websocket.send(json.dumps({"type": "error", "message": "first message must be register"}))
                await websocket.close()
                return

            device_id = str(data.get("device_id", "")).strip()
            token = str(data.get("token", "")).strip()

            if not device_id:
                await websocket.send(json.dumps({"type": "error", "message": "missing device_id"}))
                await websocket.close()
                return
            if token != WS_CONTROL_TOKEN:
                peer = websocket.remote_address
                logger.warning("Rejected registration from %s (device_id=%r): invalid token", peer, device_id)
                await websocket.send(json.dumps({"type": "error", "message": "unauthorized"}))
                await websocket.close()
                return

            with self._clients_lock:
                self._clients[device_id] = websocket

            await websocket.send(json.dumps({"type": "registered", "device_id": device_id}))
            logger.info("Control socket registered: %s", device_id)

            async for message in websocket:
                await self._handle_message(message)
        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            logger.warning("WS client handler error: %s", e)
        finally:
            if device_id:
                with self._clients_lock:
                    existing = self._clients.get(device_id)
                    if existing is websocket:
                        self._clients.pop(device_id, None)
                logger.info("Control socket disconnected: %s", device_id)

    async def _handle_message(self, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        if data.get("type") != "ack":
            return

        request_id = str(data.get("request_id", ""))
        if not request_id:
            return

        with self._pending_lock:
            fut = self._pending.pop(request_id, None)

        if fut and not fut.done():
            fut.set_result(data)

    async def _send_command_async(self, device_id: str, payload: Dict[str, Any]) -> None:
        with self._clients_lock:
            websocket = self._clients.get(device_id)
        if websocket is None:
            raise RuntimeError(f"Device '{device_id}' is not connected")
        await websocket.send(json.dumps(payload))

    def send_command(self, device_id: str, command: str, payload: Dict[str, Any] | None = None, timeout: int = 5) -> Dict[str, Any]:
        if not self.loop:
            raise RuntimeError("WS control hub is not running")

        request_id = str(uuid.uuid4())
        message = {
            "type": "command",
            "request_id": request_id,
            "command": command,
            "payload": payload or {},
        }
        ack_future: Future = Future()
        with self._pending_lock:
            self._pending[request_id] = ack_future

        send_future = asyncio.run_coroutine_threadsafe(self._send_command_async(device_id, message), self.loop)
        send_future.result(timeout=timeout)

        try:
            return ack_future.result(timeout=timeout)
        except Exception:
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise

    def connected_devices(self) -> list[str]:
        with self._clients_lock:
            return sorted(self._clients.keys())


hub = ControlHub(WS_CONTROL_HOST, WS_CONTROL_PORT)
