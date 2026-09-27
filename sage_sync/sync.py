"""Diff-Engine: gleicht Sage-Kunden mit Outlook-Kontakten ab (idempotent)."""

__version__ = "0.1.0"
import dataclasses
import json
import sqlite3

from .mapping import external_key, fingerprint, to_outlook_contact


@dataclasses.dataclass
class Actions:
    create: list = dataclasses.field(default_factory=list)
    update: list = dataclasses.field(default_factory=list)
    delete: list = dataclasses.field(default_factory=list)
    unchanged: list = dataclasses.field(default_factory=list)


def plan(target_state: dict, source_customers: dict, delete_missing: bool) -> Actions:
    """target_state: contact_id -> (account_number, fingerprint)."""
    actions = Actions()

    by_number = {number: (cid, fp) for cid, (number, fp) in target_state.items()}

    for number, customer in source_customers.items():
        fp = fingerprint(customer)
        existing = by_number.get(number)
        if existing is None:
            actions.create.append(customer)
        elif existing[1] != fp:
            actions.update.append((existing[0], customer))
        else:
            actions.unchanged.append(number)

    source_numbers = set(source_customers.keys())
    for cid, (number, fp) in target_state.items():
        if number not in source_numbers:
            actions.delete.append(cid)
    return actions


class SyncStore:
    """Lokaler Zustand: contact_id -> (Kundennummer, Fingerprint)."""

    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS contacts ("
            " contact_id TEXT PRIMARY KEY,"
            " account_number TEXT NOT NULL,"
            " fingerprint TEXT NOT NULL,"
            " deleted INTEGER NOT NULL DEFAULT 0,"
            " etag TEXT DEFAULT NULL,"
            " last_synced_at TEXT NOT NULL"
            ")"
        )
        self.conn.commit()

    def load(self) -> dict:
        cur = self.conn.execute("SELECT contact_id, account_number, fingerprint FROM contacts WHERE deleted = 0")
        return {row[0]: (row[1], row[2]) for row in cur.fetchall()}

    def upsert(self, contact_id: str, account_number: str, fingerprint: str):
        self.conn.execute(
            "INSERT INTO contacts (contact_id, account_number, fingerprint, last_synced_at) "
            "VALUES (?, ?, ?, datetime('now')) "
            "ON CONFLICT(contact_id) DO UPDATE SET "
            "account_number = excluded.account_number, fingerprint = excluded.fingerprint, "
            "deleted = 0, last_synced_at = datetime('now')",
            (contact_id, account_number, fingerprint),
        )
        self.conn.commit()

    def mark_deleted(self, contact_id: str):
        self.conn.execute("UPDATE contacts SET deleted = 1 WHERE contact_id = ?", (contact_id,))
        self.conn.commit()

    def close(self):
        self.conn.close()


def apply(client, mail, folder_id, source_customers, store: SyncStore, cfg, dry_run: bool = False) -> dict:
    """Führt den Abgleich aus; bei dry_run wird nichts verändert."""
    target = store.load()
    actions = plan(target, source_customers, delete_missing=True)

    stats = {"created": 0, "updated": 0, "deleted": 0, "unchanged": len(actions.unchanged)}

    for customer in actions.create:
        body = to_outlook_contact(customer, with_postal_address=cfg.contacts.with_postal_address)
        if dry_run:
            stats["created"] += 1
            continue
        created = create_in_folder(client, mail, folder_id, body, customer)
        store.upsert(created["id"], customer["account_number"], fingerprint(customer))
        stats["created"] += 1

    for contact_id, customer in actions.update:
        body = to_outlook_contact(customer, with_postal_address=cfg.contacts.with_postal_address)
        if dry_run:
            stats["updated"] += 1
            continue
        patch_in_folder(client, mail, folder_id, contact_id, body, customer)
        store.upsert(contact_id, customer["account_number"], fingerprint(customer))
        stats["updated"] += 1

    if cfg.contacts.delete_missing:
        for contact_id in actions.delete:
            if dry_run:
                stats["deleted"] += 1
                continue
            delete_contact_soft(client, mail, contact_id, store)
            stats["deleted"] += 1

    return stats


def create_in_folder(client, mail, folder_id, body, customer):
    from . import graph as g

    created = g.create_contact(client, mail, {**body, "parentFolderId": folder_id})
    try:
        g.upsert_extension(client, mail, created["id"], {
            "accountNumber": customer["account_number"],
            "fingerprint": fingerprint(customer),
        })
    except Exception:
        pass
    return created


def patch_in_folder(client, mail, folder_id, contact_id, body, customer):
    from . import graph as g

    g.patch_contact(client, mail, contact_id, body)
    try:
        g.upsert_extension(client, mail, contact_id, {
            "accountNumber": customer["account_number"],
            "fingerprint": fingerprint(customer),
        })
    except Exception:
        pass


def delete_contact_soft(client, mail, contact_id, store):
    from . import graph as g

    try:
        g.delete_contact(client, mail, contact_id)
    except RuntimeError as exc:
        if "404" in str(exc):
            pass
        else:
            raise
    store.mark_deleted(contact_id)
