"""Remote notifications and an emergency stop through a Telegram bot."""

import os
import time
import queue
import threading
import requests
import cv2
from datetime import datetime, timedelta
from src.common import config
from src.common.interfaces import Configurable

API_BASE = 'https://api.telegram.org/bot{token}/{method}'
POLL_TIMEOUT = 25           # Telegram long-poll duration in seconds
HELP_TEXT = (
    'Commands:\n'
    '/stop - stop the bot and silence the siren\n'
    '/start - recalibrate and resume the bot\n'
    '/status - current state\n'
    '/screenshot - send the current frame\n'
    '/help - this message'
)


class Remote(Configurable):
    """
    Pushes notable events to a Telegram chat and accepts remote commands.
    Both directions run on daemon threads with their own error handling, so
    a missing token or a dead network can never affect the bot itself.
    """

    DEFAULT_CONFIG = {
        'Telegram bot token': '',
        'Telegram chat id': ''
    }

    def __init__(self):
        super().__init__('remote')
        config.remote = self

        self.queue = queue.Queue()
        self.started_at = time.time()
        self.last_enabled = config.enabled
        self.ready = False

        self.sender_thread = threading.Thread(target=self._sender)
        self.sender_thread.daemon = True
        self.poller_thread = threading.Thread(target=self._poller)
        self.poller_thread.daemon = True

    def start(self):
        state = 'configured' if self._configured() else 'no Telegram token, idle'
        print(f'\n[~] Started remote control ({state})')
        self.sender_thread.start()
        self.poller_thread.start()
        self.ready = True

    def _configured(self):
        return bool(str(self.config['Telegram bot token']).strip())

    def _chat_id(self):
        return str(self.config['Telegram chat id']).strip()

    #################################
    #       Outgoing messages       #
    #################################
    def notify(self, text):
        """Queues TEXT for delivery. Returns immediately and never raises."""

        if self._configured():
            self.queue.put(('text', text))

    def notify_frame(self, caption, frame=None):
        """Queues CAPTION with a JPEG of FRAME (default: the current capture)."""

        if not self._configured():
            return
        if frame is None and config.capture is not None:
            frame = config.capture.frame
        if frame is None:
            self.queue.put(('text', caption))
            return
        ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            self.queue.put(('photo', (caption, encoded.tobytes())))
        else:
            self.queue.put(('text', caption))

    def _sender(self):
        while True:
            try:
                kind, payload = self.queue.get(timeout=1)
            except queue.Empty:
                self._watch_state()
                continue
            try:
                if kind == 'text':
                    self._api('sendMessage', data={'chat_id': self._chat_id(), 'text': payload})
                else:
                    caption, image = payload
                    self._api(
                        'sendPhoto',
                        data={'chat_id': self._chat_id(), 'caption': caption},
                        files={'photo': ('screen.jpg', image, 'image/jpeg')}
                    )
            except Exception as e:
                print(f'[!] Telegram send failed: {e}')

    def _watch_state(self):
        """Notifies on start/stop regardless of what triggered the change."""

        if config.enabled != self.last_enabled:
            self.last_enabled = config.enabled
            self.notify(f"Auto Maple is now {'RUNNING' if config.enabled else 'STOPPED'}")

    #################################
    #       Incoming commands       #
    #################################
    def _poller(self):
        offset = 0
        synced = False
        while True:
            if not self._configured():
                time.sleep(5)
                synced = False
                continue
            try:
                result = self._api(
                    'getUpdates',
                    data={'offset': offset, 'timeout': POLL_TIMEOUT},
                    timeout=POLL_TIMEOUT + 10
                )
            except Exception as e:
                print(f'[!] Telegram polling failed: {e}')
                time.sleep(5)
                continue

            updates = result.get('result', [])
            for update in updates:
                offset = max(offset, update['update_id'] + 1)
            if not synced:
                # Discard commands that were sent while Auto Maple was offline
                # so a stale /start cannot enable the bot on startup.
                synced = True
                continue
            for update in updates:
                message = update.get('message') or update.get('edited_message')
                if message:
                    try:
                        self._handle_message(message)
                    except Exception as e:
                        print(f'[!] Telegram command failed: {e}')

    def _handle_message(self, message):
        chat_id = str(message.get('chat', {}).get('id', ''))
        text = (message.get('text') or '').strip()
        configured = self._chat_id()

        if not configured:
            print(f'\n[!] Telegram message received from chat id {chat_id}. Paste this id '
                  'into Settings -> Remote Control to enable commands.')
            self._api('sendMessage', data={
                'chat_id': chat_id,
                'text': f'This chat id is: {chat_id}\nPaste it into Auto Maple '
                        'Settings -> Remote Control, then send /help.'
            })
            return
        if chat_id != configured:
            return      # Ignore messages from anyone else

        parts = text.split()
        command = parts[0].split('@')[0].lower() if parts else ''
        if command == '/stop':
            config.alert_ack = True             # Also silences an active siren
            if config.enabled:
                config.enabled = False
                self.last_enabled = False       # Suppress the duplicate state notification
                self.notify('Stopped.')
            else:
                self.notify('Already stopped.')
        elif command == '/start':
            if config.enabled:
                self.notify('Already running.')
            else:
                self._remote_start()
        elif command == '/status':
            self.notify(self._status_text())
        elif command in ('/screenshot', '/shot'):
            self.notify_frame(f"Screenshot at {datetime.now().strftime('%H:%M:%S')}")
        else:
            self.notify(HELP_TEXT)

    def _remote_start(self):
        capture = config.capture
        if capture is not None:
            capture.calibrated = False          # The capture thread recalibrates itself
            for _ in range(100):
                if capture.calibrated:
                    break
                time.sleep(0.05)
            if not capture.calibrated:
                self.notify('Could not recalibrate the minimap, not starting.')
                return
        config.enabled = True
        self.last_enabled = True
        self.notify('Recalibrated and running.')

    def _status_text(self):
        routine = 'none'
        if config.routine is not None and config.routine.path:
            routine = os.path.basename(config.routine.path)
        rune = 'yes' if config.bot is not None and config.bot.rune_active else 'no'
        uptime = timedelta(seconds=round(time.time() - self.started_at))
        return (f"State: {'running' if config.enabled else 'stopped'}\n"
                f'Routine: {routine}\n'
                f'Player: ({config.player_pos[0]:.3f}, {config.player_pos[1]:.3f})\n'
                f'Rune active: {rune}\n'
                f'Uptime: {uptime}')

    def _api(self, method, data=None, files=None, timeout=10):
        token = str(self.config['Telegram bot token']).strip()
        url = API_BASE.format(token=token, method=method)
        response = requests.post(url, data=data, files=files, timeout=timeout)
        response.raise_for_status()
        return response.json()
