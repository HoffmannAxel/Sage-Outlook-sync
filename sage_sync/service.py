"""Betrieb als Windows-Dienst – zwei Varianten:

Variante A (empfohlen, kein pywin32 nötig): Dienst-Wrapper wie NSSM führt den
Konsolmodus aus und überwacht ihn (Neustart bei Absturz, Log-Handling):

    nssm install SageOutlookSync "C:\\Pfad\\python.exe" "-m sage_sync.service --config C:\\Pfad\\config.toml"

Variante B: nativer Dienst über pywin32 (pythonservice.exe). Die Konfiguration
wird hier über die Umgebungsvariable SAGE_SYNC_CONFIG übergeben:

    sc.exe create SageOutlookSync binPath= "C:\\Pfad\\Lib\\site-packages\\win32\\pythonservice.exe" start= auto
    (Konvention: vorher `python -m sage_sync.service install` mit SAGE_SYNC_CONFIG gesetzt)

Konsolmodus für Tests/Handbetrieb:

    python -m sage_sync.service --config config.toml            # Dauerschleife (Strg+C beendet)
    python -m sage_sync.service --config config.toml --once     # ein einzelner Sync-Lauf
"""

__version__ = "1.1.0"
import argparse
import logging
import os
import signal
import sys
import threading

from .config import AppConfig
from .runner import run_forever, run_sync, setup_logging


def console_main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sage_sync.service",
        description="Dauerbetrieb des Sage→Outlook-Sync (für Dienst-Wrapper wie NSSM oder pywin32-Hosting).",
    )
    parser.add_argument("--config", required=True, help="Pfad zur config.toml")
    parser.add_argument("--once", action="store_true", help="Nur einen Sync-Lauf ausführen und beenden")
    parser.add_argument("--dry-run", action="store_true", help="Nichts verändern (nur mit --once sinnvoll)")
    args = parser.parse_args(argv)

    cfg = AppConfig.load(args.config)
    setup_logging(cfg, stream=True)
    logger = logging.getLogger("sage_sync")

    if args.once:
        stats = run_sync(cfg, dry_run=args.dry_run)
        logger.info(
            "Sync fertig: %d angelegt, %d aktualisiert, %d gelöscht, %d unverändert",
            stats["created"], stats["updated"], stats["deleted"], stats["unchanged"],
        )
        return 0

    stop = threading.Event()

    def _handle_signal(signum, frame):
        logger.info("Stoppsignal erhalten, beende laufenden Zyklus...")
        stop.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    run_forever(cfg, stop)
    logger.info("Dienst beendet.")
    return 0


def _win32_available() -> bool:
    try:
        import servicemanager  # noqa: F401
        import win32event  # noqa: F401
        import win32service  # noqa: F401
        import win32serviceutil  # noqa: F401
        return True
    except ImportError:
        return False


if _win32_available():
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    class SageSyncService(win32service.ServiceFramework):
        _svc_name_ = "SageOutlookSync"
        _svc_display_name_ = "Sage Outlook Sync"
        _svc_description_ = "Repliziert Sage-50-Kunden (MySQL) in Outlook-Kontakte (Microsoft 365)."

        def __init__(self, args):
            super().__init__(args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)

        def SvcDoRun(self):
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            logger = logging.getLogger("sage_sync")
            config_path = os.environ.get("SAGE_SYNC_CONFIG")
            try:
                cfg = AppConfig.load(config_path)
                setup_logging(cfg, stream=False)
                run_forever(cfg, _Win32StopEvent(self.stop_event))
            except Exception:
                logger.exception("Dienst fehlgeschlagen")
                servicemanager.LogErrorMsg("Sage Outlook Sync: unerwarteter Fehler, Dienst endet")
            self.SvcStop()

    class _Win32StopEvent:
        def __init__(self, handle):
            self._handle = handle

        def is_set(self):
            return win32event.WaitForSingleObject(self._handle, 0) == 0

        def wait(self, seconds):
            win32event.WaitForSingleObject(self._handle, int(seconds * 1000))


if __name__ == "__main__":
    if _win32_available() and len(sys.argv) > 1 and sys.argv[1] in ("install", "remove", "start", "stop", "restart", "debug"):
        if not _win32_available():
            sys.exit(1)
        win32serviceutil.HandleCommandLine(SageSyncService)
    else:
        sys.exit(console_main())
