import json
import os
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from queue import Empty, Queue
import threading
from tkinter import ttk

from dotenv import load_dotenv
import pyttsx3

from chat_client import TwitchChatClient


def refresh_access_token(refresh_token, client_id, client_secret):
    payload = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://id.twitch.tv/oauth2/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read().decode("utf-8")
        data = json.loads(body)
    return data.get("access_token")


def load_config():
    load_dotenv()
    token = os.getenv("TWITCH_TOKEN")
    nick = os.getenv("TWITCH_NICK")
    channel = os.getenv("TWITCH_CHANNEL")
    refresh_token = os.getenv("TWITCH_REFRESH_TOKEN")
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")
    tts_rate_raw = os.getenv("TTS_RATE")
    tts_rate = None
    if tts_rate_raw:
        try:
            tts_rate = int(tts_rate_raw)
        except ValueError:
            tts_rate = None

    missing_required = [
        name
        for name, value in (
            ("TWITCH_NICK", nick),
            ("TWITCH_CHANNEL", channel),
        )
        if not value
    ]
    missing_token = not token
    return (
        token,
        nick,
        channel,
        missing_required,
        missing_token,
        refresh_token,
        client_id,
        client_secret,
        tts_rate,
    )


class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Twitch Chat")
        self.queue = Queue()
        self.tts_queue = Queue()
        self.tts_stop = threading.Event()
        self.tts_thread = threading.Thread(
            target=self._tts_worker, daemon=True
        )
        self.tts_thread.start()
        self.tts_rate_var = tk.IntVar(value=180)
        self.color_tags = {}

        (
            self.token,
            self.nick,
            self.channel,
            self.missing_required,
            self.missing_token,
            self.refresh_token,
            self.client_id,
            self.client_secret,
            self.tts_rate,
        ) = load_config()
        if self.tts_rate:
            self.tts_rate_var.set(self.tts_rate)
        self.client = None

        self._build_ui()
        self._update_status("Disconnected")

        if self.refresh_token and self.client_id and self.client_secret:
            self._append_system("Refreshing access token...")
            try:
                refreshed = refresh_access_token(
                    self.refresh_token,
                    self.client_id,
                    self.client_secret,
                )
                if refreshed:
                    self.token = "oauth:{0}".format(refreshed)
                    self._append_system("Access token refreshed.")
            except (urllib.error.URLError, json.JSONDecodeError) as exc:
                self._append_system("Refresh failed: {0}".format(exc))

        if self.missing_required or (self.missing_token and not self.token):
            missing_items = list(self.missing_required)
            if self.missing_token and not self.token:
                missing_items.append("TWITCH_TOKEN")
            self._append_system(
                "Missing env vars: {0}".format(
                    ", ".join(missing_items)
                )
            )
            self._append_system("Create a .env file and restart.")
            self.connect_button.configure(state="disabled")
        else:
            title = "Chat Twitch: {0}".format(self.channel)
            self.root.title(title)
            self.client = TwitchChatClient(
                token=self.token,
                nick=self.nick,
                channel=self.channel,
                message_queue=self.queue,
            )

        self.root.after(100, self._poll_queue)

    def _build_ui(self):
        self.root.geometry("700x500")
        self.root.minsize(520, 360)

        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        self.connect_button = ttk.Button(
            toolbar, text="Connect", command=self._toggle_connection
        )
        self.connect_button.pack(side=tk.LEFT)

        self.status_label = ttk.Label(toolbar, text="")
        self.status_label.pack(side=tk.LEFT, padx=12)

        rate_label = ttk.Label(toolbar, text="TTS speed")
        rate_label.pack(side=tk.LEFT, padx=(16, 6))

        self.rate_scale = ttk.Scale(
            toolbar,
            from_=120,
            to=240,
            orient=tk.HORIZONTAL,
            command=self._on_rate_change,
        )
        self.rate_scale.set(self.tts_rate_var.get())
        self.rate_scale.pack(side=tk.LEFT)

        self.rate_value_label = ttk.Label(
            toolbar, text=str(self.tts_rate_var.get())
        )
        self.rate_value_label.pack(side=tk.LEFT, padx=(6, 0))

        chat_frame = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        chat_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.chat_text = tk.Text(
            chat_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Consolas", 10),
        )
        scrollbar = ttk.Scrollbar(
            chat_frame, orient=tk.VERTICAL, command=self.chat_text.yview
        )
        self.chat_text.configure(yscrollcommand=scrollbar.set)

        self.chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _toggle_connection(self):
        if not self.client:
            return

        if self.client.is_running:
            self.client.stop()
            self._update_status("Disconnected")
            self.connect_button.configure(text="Connect")
        else:
            self._update_status("Connecting...")
            self.client.start()
            self.connect_button.configure(text="Disconnect")

    def _append_line(self, text):
        self.chat_text.configure(state=tk.NORMAL)
        self.chat_text.insert(tk.END, text + "\n")
        self.chat_text.configure(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def _append_system(self, text):
        self._append_line("[system] {0}".format(text))

    def _ensure_color_tag(self, color_hex):
        if not color_hex:
            return None
        if color_hex in self.color_tags:
            return self.color_tags[color_hex]
        tag_name = "usercolor_{0}".format(color_hex.replace("#", ""))
        self.chat_text.tag_configure(tag_name, foreground=color_hex)
        self.color_tags[color_hex] = tag_name
        return tag_name

    def _append_message(self, username, message, timestamp, color_hex):
        time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M")
        self.chat_text.configure(state=tk.NORMAL)
        self.chat_text.insert(tk.END, "[{0}] ".format(time_str))
        tag = self._ensure_color_tag(color_hex)
        if tag:
            self.chat_text.insert(tk.END, username, tag)
        else:
            self.chat_text.insert(tk.END, username)
        self.chat_text.insert(tk.END, ": {0}\n".format(message))
        self.chat_text.configure(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def _update_status(self, text):
        self.status_label.configure(text="Status: {0}".format(text))

    def _poll_queue(self):
        while True:
            try:
                item = self.queue.get_nowait()
            except Empty:
                break

            item_type = item.get("type")
            if item_type == "message":
                self._append_message(
                    item.get("user"),
                    item.get("content"),
                    item.get("timestamp"),
                    item.get("color"),
                )
            elif item_type == "system":
                self._append_system(item.get("text"))
            elif item_type == "status":
                self._update_status(item.get("text"))
            elif item_type == "tts":
                self.tts_queue.put(item)

        self.root.after(100, self._poll_queue)

    def _tts_worker(self):
        engine = pyttsx3.init()
        engine.setProperty("rate", self.tts_rate_var.get())
        while not self.tts_stop.is_set():
            try:
                item = self.tts_queue.get(timeout=0.2)
            except Empty:
                continue

            if item is None:
                break

            if item.get("type") == "tts_rate":
                rate = item.get("value")
                if isinstance(rate, int):
                    engine.setProperty("rate", rate)
                continue

            message = item.get("content")
            if not message:
                continue
            engine.say(message)
            engine.runAndWait()

    def _on_rate_change(self, value):
        rate = int(float(value))
        self.tts_rate_var.set(rate)
        self.rate_value_label.configure(text=str(rate))
        self.tts_queue.put({"type": "tts_rate", "value": rate})


def main():
    root = tk.Tk()
    app = ChatApp(root)
    def handle_close():
        app.tts_stop.set()
        app.tts_queue.put(None)
        if app.client and app.client.is_running:
            app.client.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", handle_close)
    root.mainloop()


if __name__ == "__main__":
    main()
