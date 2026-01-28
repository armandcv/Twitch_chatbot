import asyncio
import threading
import time

from twitchio import Client


class _TwitchChatClient(Client):
    def __init__(self, token, nick, channel, message_queue):
        super().__init__(
            token=token,
            initial_channels=[channel],
        )
        self._message_queue = message_queue
        self._channel = channel

    def _emit(self, item):
        self._message_queue.put(item)

    def _emit_status(self, text):
        self._emit({"type": "status", "text": text})

    def _emit_system(self, text):
        self._emit({"type": "system", "text": text})

    def _emit_message(self, username, message, color):
        self._emit(
            {
                "type": "message",
                "user": username,
                "content": message,
                "color": color,
                "timestamp": time.time(),
            }
        )

    def _emit_tts(self, username, message):
        self._emit(
            {
                "type": "tts",
                "user": username,
                "content": message,
                "timestamp": time.time(),
            }
        )

    async def event_ready(self):
        self._emit_status("Connected")
        self._emit_system("Connected to #{0}".format(self._channel))

    async def event_message(self, message):
        if message.author is None:
            return
        content = message.content or ""
        color = None
        if message.tags:
            color = message.tags.get("color")
        self._emit_message(message.author.name, content, color)

        normalized = content.strip()
        if normalized.lower().startswith("!dice"):
            spoken = normalized[5:].strip()
            if spoken:
                self._emit_tts(message.author.name, spoken)

    async def event_error(self, error, data=None):
        self._emit_system("Error: {0}".format(error))


class TwitchChatClient:
    def __init__(self, token, nick, channel, message_queue):
        self._token = token
        self._nick = nick
        self._channel = channel
        self._message_queue = message_queue
        self._client = None
        self._loop = None
        self._thread = None

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.is_running:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if not self._client or not self._loop:
            return
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._client.close(), self._loop
            )
            future.result(timeout=5)
        except Exception:
            pass

    def _run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._client = _TwitchChatClient(
                token=self._token,
                nick=self._nick,
                channel=self._channel,
                message_queue=self._message_queue,
            )
            self._loop.run_until_complete(self._client.start())
        except Exception as exc:
            self._message_queue.put(
                {"type": "system", "text": "Error: {0}".format(exc)}
            )
        finally:
            if self._loop and self._loop.is_running():
                self._loop.stop()
            if self._loop:
                self._loop.close()
            self._client = None
