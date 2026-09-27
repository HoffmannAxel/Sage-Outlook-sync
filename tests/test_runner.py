"""Integrationstest: voller Sync-Zyklus mit Fake-MySQL und Fake-Graph."""

__version__ = "0.1.0"
import os
import tempfile
import unittest
from unittest import mock

from sage_sync.config import AppConfig, ContactsConfig, GraphConfig, MysqlConfig, SyncConfig
from sage_sync import runner
from sage_sync.service import console_main


MAPPING = {
    "customer_table": "kunden",
    "account_number": "KundenNr",
    "name": "Name1",
    "department": "Abteilung",
    "name2": "Name2",
    "street": "Str",
    "zip": "Plz",
    "city": "Ort",
    "country": "Land",
    "phone": "Tel",
    "fax": "Fax",
    "email": "EMail",
    "website": "Internet",
    "bank": "Bank",
    "account_holder": "Kontoinhaber",
    "iban": "IBAN",
    "bic": "BIC",
    "notes": "Bem",
    "department2": "Abteilung2",
}


def row(nr, name, ort="Berlin"):
    return {"KundenNr": nr, "Name1": name, "Ort": ort}


class FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def close(self):
        pass


class FakeGraphClient:
    """Minimaler Graph-Fake: Ordner + CRUD mit zähler-basierten IDs."""

    def __init__(self, cfg=None):
        self.contacts = {}

    def request_json(self, method, path, body=None, params=None, **kwargs):
        if method == "GET" and path.startswith("/users/") and "contactFolders" in path:
            return {"value": [{"id": "folder-1", "displayName": "Sage Kontakte"}]}
        if method == "POST" and path.rstrip("/").endswith("/contacts"):
            contact_id = f"cid-{len(self.contacts) + 1}"
            self.contacts[contact_id] = {"id": contact_id, **body}
            return self.contacts[contact_id]
        if method == "PATCH" and "/contacts/cid-" in path:
            contact_id = path.split("/")[-1]
            self.contacts[contact_id].update(body)
            return self.contacts[contact_id]
        if method == "DELETE" and "/contacts/cid-" in path:
            contact_id = path.split("/")[-1]
            del self.contacts[contact_id]
            return {}
        raise AssertionError(f"FakeGraph: unerwartet {method} {path}")


def make_config(tmpdir):
    return AppConfig(
        mysql=MysqlConfig(mapping=MAPPING),
        graph=GraphConfig(),
        contacts=ContactsConfig(folder_name="Sage Kontakte"),
        sync=SyncConfig(target_mail="user@firma.de"),
        base_dir=tmpdir,
    )


class TestRunnerCycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = make_config(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _patch(self, rows):
        fake = FakeGraphClient()
        patchers = [
            mock.patch.object(runner, "connect", lambda cfg: FakeConn(rows)),
            mock.patch.object(runner, "discover_mapping", lambda conn, m: MAPPING),
            mock.patch.object(runner, "load_customers", lambda conn, m: rows),
            mock.patch.object(runner, "GraphClient", lambda cfg: fake),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)
        return fake

    def test_create_update_delete_cycle(self):
        rows = [row("1", "Firma A"), row("2", "Firma B")]
        fake = self._patch(rows)

        stats = runner.run_sync(self.cfg)
        self.assertEqual(stats, {"created": 2, "updated": 0, "deleted": 0, "unchanged": 0})
        self.assertEqual(len(fake.contacts), 2)

        stats = runner.run_sync(self.cfg)
        self.assertEqual(stats["unchanged"], 2)
        self.assertEqual(stats["created"], 0)

        rows[0]["Ort"] = "Hamburg"
        stats = runner.run_sync(self.cfg)
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(stats["unchanged"], 1)

        rows.pop()
        stats = runner.run_sync(self.cfg)
        self.assertEqual(stats["deleted"], 1)
        self.assertEqual(len(fake.contacts), 1)

        stats = runner.run_sync(self.cfg)
        self.assertEqual(stats["unchanged"], 1)

    def test_run_forever_stops_on_event(self):
        self._patch([row("1", "Firma A")])

        calls = []

        class StopNow:
            def __init__(self):
                self.count = 0

            def is_set(self):
                self.count += 1
                return self.count > 2

            def wait(self, seconds):
                calls.append(seconds)

        runner.run_forever(self.cfg, StopNow(), sleep=lambda s: None)
        self.assertEqual(calls, [60 * 60])

    def test_service_once(self):
        self._patch([row("1", "Firma A"), row("2", "Firma B")])
        config_path = os.path.join(self.tmp.name, "config.toml")
        with open(config_path, "w", encoding="utf-8") as fh:
            fh.write(
                '[mysql]\nhost = "x"\n[mysql.mapping]\n'
                + "".join(f'{k.replace("_", "")} = "{v}"\n' for k, v in MAPPING.items())
                + '[sync]\ntarget_mail = "user@firma.de"\n'
            )
        with mock.patch("sys.argv", ["prog", "--config", config_path, "--once"]):
            rc = console_main()
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
