__version__ = "0.1.0"

import os
import tempfile
import unittest

from sage_sync import mapping as m
from sage_sync.sync import SyncStore, plan


class TestMapping(unittest.TestCase):
    def setUp(self):
        self.mapping = {
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

    def test_normalize_customer(self):
        row = {
            "KundenNr": " 10001 ",
            "Name1": " Muster GmbH ",
            "Plz": "40233",
            "Ort": "Düsseldorf",
            "EMail": None,
            "Irrelevant": "x",
        }
        c = m.normalize_customer(row, self.mapping)
        self.assertEqual(c["account_number"], "10001")
        self.assertEqual(c["name"], "Muster GmbH")
        self.assertEqual(c["city"], "Düsseldorf")
        self.assertIsNone(c["email"])

    def test_normalize_requires_number_and_name(self):
        self.assertIsNone(m.normalize_customer({"KundenNr": "1"}, self.mapping))
        self.assertIsNone(m.normalize_customer({"Name1": "X"}, self.mapping))

    def test_to_outlook_contact_minimal(self):
        c = m.normalize_customer({"KundenNr": "1", "Name1": "Test AG"}, self.mapping)
        body = m.to_outlook_contact(c, with_postal_address=False)
        self.assertEqual(body["companyName"], "Test AG")
        self.assertEqual(body["emailAddresses"], [])
        self.assertEqual(body["businessPhones"], [])
        self.assertNotIn("businessAddress", body)
        self.assertNotIn("personalNotes", body)

    def test_to_outlook_contact_full(self):
        c = m.normalize_customer(
            {
                "KundenNr": "1",
                "Name1": "Test AG",
                "Abteilung": "Einkauf",
                "Name2": "Filiale Nord",
                "Str": "Hauptstr. 1",
                "Plz": "10115",
                "Ort": "Berlin",
                "Land": "Deutschland",
                "Tel": "+49 30 123",
                "Fax": "+49 30 456",
                "EMail": "info@test.de",
                "Internet": "www.test.de",
                "Bank": "Sparkasse",
                "Kontoinhaber": "Test AG",
                "IBAN": "DE89...",
                "BIC": "BYLA",
                "Bem": "Wichtig",
                "Abteilung2": "Zusatz",
            },
            self.mapping,
        )
        body = m.to_outlook_contact(c, with_postal_address=True)
        self.assertEqual(body["fileAs"], "Test AG Einkauf Filiale Nord")
        self.assertEqual(body["businessPhones"], ["+49 30 123", "Fax: +49 30 456"])
        self.assertEqual(body["emailAddresses"][0]["address"], "info@test.de")
        self.assertEqual(body["businessAddress"]["city"], "Berlin")
        self.assertIn("IBAN: DE89...", body["personalNotes"])
        self.assertEqual(body["businessHomePage"], "www.test.de")

    def test_fingerprint_stable_and_sensitive(self):
        r1 = {"KundenNr": "1", "Name1": "Test AG", "Ort": "A"}
        r2 = {"KundenNr": "1", "Name1": "Test AG", "Ort": "B"}
        f1 = m.fingerprint(m.normalize_customer(r1, self.mapping))
        f1b = m.fingerprint(m.normalize_customer(dict(r1), self.mapping))
        f2 = m.fingerprint(m.normalize_customer(r2, self.mapping))
        self.assertEqual(f1, f1b)
        self.assertNotEqual(f1, f2)

    def test_external_key(self):
        self.assertEqual(m.external_key(" ab1 "), "SAGE:AB1")


class TestPlan(unittest.TestCase):
    def _cust(self, n, name="Firma"):
        return m.normalize_customer({"KundenNr": n, "Name1": name}, {
            "account_number": "KundenNr", "name": "Name1"})

    def test_create_update_delete(self):
        source = {self._cust("1")["account_number"]: self._cust("1"),
                  self._cust("2", "Neu")["account_number"]: self._cust("2", "Neu")}
        target = {
            "cid-1": ("1", m.fingerprint(self._cust("1"))),
            "cid-1b": ("1", m.fingerprint(self._cust("1"))),
            "cid-3": ("3", m.fingerprint(self._cust("3"))),
        }
        a = plan(target, source, delete_missing=True)
        self.assertEqual(len(a.create), 1)
        self.assertEqual(a.create[0]["account_number"], "2")
        self.assertEqual(a.unchanged, ["1"])
        self.assertEqual(a.delete, ["cid-3"])

    def test_update_on_change(self):
        source = {self._cust("1", "Geändert")["account_number"]: self._cust("1", "Geändert")}
        target = {"cid-1": ("1", m.fingerprint(self._cust("1", "Alt")))}
        a = plan(target, source, delete_missing=True)
        self.assertEqual(len(a.update), 1)
        self.assertEqual(a.update[0][0], "cid-1")
        self.assertEqual(a.delete, [])


class TestSyncStore(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state.db")
            store = SyncStore(path)
            store.upsert("cid-1", "100", "abc")
            store.upsert("cid-2", "200", "def")
            self.assertEqual(store.load(), {"cid-1": ("100", "abc"), "cid-2": ("200", "def")})
            store.upsert("cid-1", "100", "xyz")
            self.assertEqual(store.load()["cid-1"], ("100", "xyz"))
            store.mark_deleted("cid-2")
            self.assertEqual(store.load(), {"cid-1": ("100", "xyz")})
            store.close()
            store2 = SyncStore(path)
            self.assertEqual(store2.load(), {"cid-1": ("100", "xyz")})
            store2.close()


if __name__ == "__main__":
    unittest.main()
