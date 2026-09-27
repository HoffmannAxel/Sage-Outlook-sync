"""Gemeinsame Sync-Logik für CLI und Windows-Dienst."""

__version__ = "0.1.0"
import logging
import os

from .config import AppConfig
from .db import build_customers, connect, discover_mapping, load_customers
from .graph import GraphClient, find_or_create_folder
from .sync import SyncStore, apply

logger = logging.getLogger("sage_sync")


def run_sync(cfg: AppConfig, dry_run: bool = False) -> dict:
    """Ein vollständiger Sync-Lauf: MySQL lesen, Diff bilden, Graph anwenden.

    Wirft bei Fehlern; der Aufrufer (CLI oder Dienst) entscheidet über Logging/Exit.
    """
    conn = connect(cfg.mysql)
    try:
        mapping = discover_mapping(conn, cfg.mysql.mapping)
        rows = load_customers(conn, mapping)
    finally:
        conn.close()

    customers = build_customers(rows, mapping, keep_without_email=cfg.contacts.keep_without_email)
    if not customers:
        logger.warning("Keine gültigen Kunden gefunden (Kundennummer und Name müssen vorhanden sein)")
        return {"created": 0, "updated": 0, "deleted": 0, "unchanged": 0}

    client = GraphClient(cfg.graph)
    folder_id = find_or_create_folder(client, cfg.sync.target_mail, cfg.contacts.folder_name)

    store = SyncStore(cfg.state_path)
    try:
        return apply(client, cfg.sync.target_mail, folder_id, customers, store, cfg, dry_run)
    finally:
        store.close()


def run_forever(cfg: AppConfig, stop_event, sleep=None):
    """Dauerschleife für den Dienstebetrieb; sleep ist injizierbar für Tests."""
    if sleep is None:
        import time
        sleep = time.sleep

    interval = cfg.sync.interval_minutes
    logger.info("Starte Dauer-Sync alle %d Minute(n) auf %s", interval, cfg.sync.target_mail)

    first = True
    while not stop_event.is_set():
        if not first:
            stop_event.wait(interval * 60)
            if stop_event.is_set():
                break
        first = False
        try:
            stats = run_sync(cfg)
            logger.info(
                "Sync fertig: %d angelegt, %d aktualisiert, %d gelöscht, %d unverändert",
                stats["created"], stats["updated"], stats["deleted"], stats["unchanged"],
            )
        except Exception:
            logger.exception("Sync-Lauf fehlgeschlagen")


def setup_logging(cfg: AppConfig, stream: bool = True, service_name: str = None) -> None:
    root = logging.getLogger("sage_sync")
    root.setLevel(logging.INFO)
    root.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    if cfg.sync.log_file:
        log_path = os.path.join(cfg.base_dir, cfg.sync.log_file)
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(formatter)
        root.addHandler(handler)

    if service_name:
        try:
            import servicemanager

            win_handler = _ServiceLogHandler(service_name)
            win_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
            root.addHandler(win_handler)
        except ImportError:
            pass
    elif stream:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)


class _ServiceLogHandler(logging.Handler):
    def __init__(self, service_name: str):
        super().__init__()
        import servicemanager

        servicemanager.Initialize(service_name, None)
        servicemanager.StartServiceCtrlDispatcher()
        self._sm = servicemanager

    def emit(self, record):
        try:
            msg = self.format(record)
            if record.levelno >= logging.ERROR:
                self._sm.LogErrorMsg(msg)
            elif record.levelno >= logging.WARNING:
                self._sm.LogWarningMsg(msg)
            else:
                self._sm.LogInfo(msg)
        except Exception:
            pass
