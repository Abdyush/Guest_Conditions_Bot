from __future__ import annotations

from src.application.ports.notifier import Notifier


class ConsoleNotifier(Notifier):
    def send(self, guest_id: str, message: str) -> None:
        print(f"[guest_id={guest_id}]")
        print(message)
