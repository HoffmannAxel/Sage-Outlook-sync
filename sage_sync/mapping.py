"""Kanonisches Kundenmodell + Mapping Sage-Zeile -> Outlook-Kontakt (Graph API)."""

__version__ = "1.1.0"

import hashlib
import json


FIELDS = (
    "account_number",
    "name",
    "department",
    "name2",
    "street",
    "zip",
    "city",
    "country",
    "phone",
    "fax",
    "email",
    "website",
    "bank",
    "account_holder",
    "iban",
    "bic",
    "notes",
    "department2",
)

_CANDIDATES = {
    "customer_table": ("kunden", "kunde", "customer", "customers", "adressen", "adresse"),
    "account_number_column": ("kundennr", "kundennummer", "kunden_nr", "kdnr", "account", "accountnumber", "customernumber", "customer_no", "nummer", "number"),
    "name_column": ("name", "name1", "firma", "firmenname", "company", "companyname", "bezeichnung"),
    "department_column": ("abteilung", "department", "name3"),
    "name2_column": ("name2", "namezus", "zusatz", "nam2"),
    "street_column": ("str", "strasse", "straße", "street", "adresse", "adresse1"),
    "zip_column": ("plz", "postleitzahl", "zip", "zipcode", "postalcode"),
    "city_column": ("ort", "stadt", "city"),
    "country_column": ("land", "country", "staat"),
    "phone_column": ("tel", "telefon", "telefon1", "phone", "phonenumber", "rufnummer"),
    "fax_column": ("fax", "telefax"),
    "email_column": ("email", "e_mail", "email1", "mail", "internetmail"),
    "website_column": ("internet", "web", "website", "homepage", "url"),
    "bank_column": ("bank", "bankname", "creditinstitut"),
    "account_holder_column": ("kontoinhaber", "inhaber", "accountholder"),
    "iban_column": ("iban", "iban1"),
    "bic_column": ("bic", "swift"),
    "notes_column": ("bemerkung", "bem", "notiz", "notizen", "notes", "comment", "memo"),
    "department2_column": ("abteilung2", "department2", "name4"),
}


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_customer(row: dict, mapping: dict) -> dict | None:
    """Extrahiert kanonische Felder aus einer DB-Zeile anhand des Spalten-Mappings."""
    def pick(field_name: str) -> str | None:
        column = mapping.get(field_name)
        if not column:
            return None
        return _clean(row.get(column))

    account_number = pick("account_number")
    name = pick("name")
    if not account_number or not name:
        return None
    return {f: pick(f) for f in FIELDS}


def to_outlook_contact(customer: dict, with_postal_address: bool = True) -> dict:
    """Erzeugt den Body für die Graph API (POST/PATCH /me/contacts)."""
    name = customer["name"]
    display_parts = [p for p in (customer.get("department"), customer.get("name2")) if p]
    full_name = " ".join([name] + display_parts)

    contact = {
        "fileAs": full_name,
        "companyName": name,
        "businessPhones": [customer["phone"]] if customer.get("phone") else [],
        "emailAddresses": (
            [{"address": customer["email"], "name": full_name}]
            if customer.get("email")
            else []
        ),
    }
    if customer.get("fax"):
        contact["businessPhones"].append("Fax: " + customer["fax"])
    if customer.get("website"):
        contact["businessHomePage"] = customer["website"]
    if customer.get("department"):
        contact["department"] = customer["department"]

    if with_postal_address:
        contact["businessAddress"] = {
            "street": customer.get("street") or None,
            "postalCode": customer.get("zip") or None,
            "city": customer.get("city") or None,
            "countryOrRegion": customer.get("country") or None,
        }

    notes_lines = []
    if customer.get("account_holder"):
        notes_lines.append("Konto-Inhaber: " + customer["account_holder"])
    if customer.get("iban"):
        notes_lines.append("IBAN: " + customer["iban"])
    if customer.get("bic"):
        notes_lines.append("BIC: " + customer["bic"])
    if customer.get("bank"):
        notes_lines.append("Bank: " + customer["bank"])
    if customer.get("notes"):
        notes_lines.append(customer["notes"])
    if customer.get("department2"):
        notes_lines.append(customer["department2"])
    if notes_lines:
        contact["personalNotes"] = "\n".join(notes_lines)

    return contact


def fingerprint(customer: dict) -> str:
    payload = {f: customer.get(f) for f in FIELDS}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def external_key(account_number: str) -> str:
    return "SAGE:" + account_number.strip().upper()
