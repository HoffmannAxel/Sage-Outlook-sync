"""CLI: Einmal-Sync, Schema-Erkennung, Dry-Run."""

__version__ = "1.1.0"
import argparse
import logging
import sys

from .config import AppConfig
from .db import build_customers, connect, discover_mapping, load_customers
from .graph import GraphClient, find_or_create_folder
from .runner import run_sync, setup_logging
from .sync import SyncStore, apply


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="sage_sync",
        description="Repliziert Sage-50-Kunden (MySQL) in einen Outlook-Kontaktordner (Microsoft Graph).",
    )
    parser.add_argument("config", help="Pfad zur config.toml")
    parser.add_argument("--discover", action="store_true", help="Nur Tabellen-/Spalten-Erkennung anzeigen und beenden")
    parser.add_argument("--dry-run", action="store_true", help="Nichts verändern, nur geplante Aktionen zählen")
    parser.add_argument("--folder", help="Zielordner überschreiben")
    parser.add_argument("--target-mail", help="Ziel-Postfach (UPN) überschreibt [sync].target_mail")
    args = parser.parse_args(argv)

    cfg = AppConfig.load(args.config)
    setup_logging(cfg)
    logger = logging.getLogger("sage_sync")

    if args.folder:
        cfg.contacts.folder_name = args.folder
    if args.target_mail:
        cfg.sync.target_mail = args.target_mail

    if args.discover:
        conn = connect(cfg.mysql)
        mapping = discover_mapping(conn, cfg.mysql.mapping)
        conn.close()
        print("Erkannte Kundentabelle:", mapping.get("customer_table"))
        for field in sorted(k for k in mapping if k != "customer_table"):
            print(f"  {field}: {mapping[field] or '<nicht erkannt>'}")
        return 0

    if not cfg.sync.target_mail:
        print("Kein Ziel-Postfach konfiguriert: [sync].target_mail in config.toml oder --target-mail angeben.")
        return 2

    stats = run_sync(cfg, dry_run=args.dry_run)
    mode = " (Dry-Run)" if args.dry_run else ""
    logger.info(
        "Sync abgeschlossen%s: %d angelegt, %d aktualisiert, %d gelöscht, %d unverändert",
        mode, stats["created"], stats["updated"], stats["deleted"], stats["unchanged"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
