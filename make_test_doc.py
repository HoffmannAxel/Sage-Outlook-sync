#!/usr/bin/env python3
"""Erzeugt die Testdokumentation als ODT-Datei.

Aufruf:
    pip install odfpy
    python make_test_doc.py
-> schreibt Testdokumentation_Sage_Outlook_Sync.odt ins aktuelle Verzeichnis.

Inhalt: Metadaten, Testabdeckung (12 Tests), Methodik, Ergebnisse des
Testlaufs vom 27.09.2026 sowie Hinweise zu nicht automatisierbaren Bereichen.
"""

__version__ = "1.1.0"
from odf.opendocument import OpenDocumentText
from odf.style import Style, TextProperties, ParagraphProperties, TableProperties, TableColumnProperties, TableRowProperties, TableCellProperties
from odf.text import H, P, Span, List, ListItem, ListStyle, ListLevelStyleBullet
from odf.table import Table, TableColumn, TableRow, TableCell
from odf.namespaces import TEXTNS, STYLENS

doc = OpenDocumentText()

# ---------- Styles ----------
h1 = Style(name="H1", family="paragraph")
h1.addElement(ParagraphProperties(numberlines=False))
h1.addElement(TextProperties(fontweight="bold", fontsize="16pt"))
doc.styles.addElement(h1)

h2 = Style(name="H2", family="paragraph")
h2.addElement(ParagraphProperties(numberlines=False))
h2.addElement(TextProperties(fontweight="bold", fontsize="13pt"))
doc.styles.addElement(h2)

normal = Style(name="Normal", family="paragraph")
normal.addElement(TextProperties(fontsize="10pt"))
doc.automaticstyles.addElement(normal)

mono = Style(name="Mono", family="paragraph")
mono.addElement(TextProperties(fontname="Courier New", fontweight="normal", fontsize="9pt"))
mono.addElement(ParagraphProperties(numberlines=False))
doc.automaticstyles.addElement(mono)

bold = Style(name="Bold", family="paragraph")
bold.addElement(TextProperties(fontweight="bold", fontsize="10pt"))
doc.automaticstyles.addElement(bold)

cell_header = Style(name="CellHeader", family="table-cell")
cell_header.addElement(TableCellProperties(backgroundcolor="#dce6f1"))
cell_header.addElement(TextProperties(fontweight="bold", fontsize="9pt"))
doc.automaticstyles.addElement(cell_header)

cell_normal = Style(name="CellNormal", family="table-cell")
cell_normal.addElement(TextProperties(fontsize="9pt"))
doc.automaticstyles.addElement(cell_normal)

list_style = Style(name="BulletList", family="paragraph")
doc.styles.addElement(list_style)

# ---------- Helpers ----------
def heading(text, level=1):
    h = H(outlinelevel=level, stylename="H1" if level == 1 else "H2")
    h.addText(text)
    return h

def para(text, style="Normal", bold_prefix=None):
    p = P(stylename=style)
    if bold_prefix:
        s = Span(stylename="Bold")
        s.addText(bold_prefix)
        p.addElement(s)
    p.addText(text)
    return p

def bullet(text, bold_prefix=None):
    p = P(stylename="Normal")
    if bold_prefix:
        s = Span(stylename="Bold")
        s.addText(bold_prefix)
        p.addElement(s)
    p.addText(text)
    li = ListItem()
    li.addElement(p)
    lst = List()
    lst.addElement(li)
    return lst

def make_table(headers, rows, widths=None):
    t = Table(name="Table")
    # Spalten
    for _ in headers:
        t.addElement(TableColumn())
    # Kopfzeile
    tr = TableRow()
    for h in headers:
        tc = TableCell(stylename="CellHeader")
        p = P(stylename="Normal")
        p.addText(h)
        tc.addElement(p)
        tr.addElement(tc)
    t.addElement(tr)
    # Datenzeilen
    for row in rows:
        tr = TableRow()
        for value in row:
            tc = TableCell(stylename="CellNormal")
            p = P(stylename="Normal")
            p.addText(str(value))
            tc.addElement(p)
            tr.addElement(tc)
        t.addElement(tr)
    return t

# ---------- Inhalt ----------
doc.text.addElement(heading("Testdokumentation: Sage 50 (MySQL) → Outlook Kontakte Replikation", 1))

t = Table(name="Meta")
for _ in range(2):
    t.addElement(TableColumn())
meta_rows = [
    ("Projekt", "sage-outlook-sync"),
    ("Version", "1.1.0"),
    ("Testlauf", "27.09.2026, 11:48 UTC"),
    ("Testumgebung", "Sandbox, Python 3.12.14, Linux"),
    ("Testframework", "unittest (Standardbibliothek)"),
    ("Testrunner-Kommando", "python -m unittest discover -s tests"),
    ("Ergebnis", "12 Tests, 12 bestanden, 0 Fehler, 0 übersprungen"),
]
for label, value in meta_rows:
    tr = TableRow()
    tc1 = TableCell(stylename="CellHeader")
    p1 = P(stylename="Normal"); p1.addText(label); tc1.addElement(p1)
    tc2 = TableCell(stylename="CellNormal")
    p2 = P(stylename="Normal"); p2.addText(value); tc2.addElement(p2)
    tr.addElement(tc1); tr.addElement(tc2)
    t.addElement(tr)
doc.text.addElement(t)
doc.text.addElement(P(stylename="Normal"))

doc.text.addElement(heading("1. Überblick und Testziel", 2))
doc.text.addElement(para(
    "Die Tests validieren die Kernlogik der Replikation: das Mapping von Sage-Kundendaten auf "
    "Outlook-Kontakte (Microsoft Graph API), die Diff-Engine (Anlegen/Aktualisieren/Löschen), "
    "die Persistenz des lokalen Zustands (state.db), den vollständigen Sync-Zyklus mit simulierter "
    "MySQL-Datenbank und Graph-API sowie den Dauerbetrieb des Windows-Dienstes. "
    "MySQL-Server und Microsoft Graph werden bewusst durch Fakes ersetzt (kein Netzwerkzugriff, "
    "deterministische, wiederholbare Läufe). Die Authentifizierung (MSAL/Client-Credentials) und "
    "die reine Netzwerkkommunikation sind nicht Bestandteil der automatisierten Tests."
))

doc.text.addElement(heading("2. Testdateien und Abdeckung", 2))
doc.text.addElement(make_table(
    ["Datei", "Testklasse", "Testfall", "Zweck / erwartetes Ergebnis"],
    [
        ("tests/test_sync.py", "TestMapping", "test_normalize_customer",
         "Kundennummer, Name und Ort werden aus der DB-Zeile korrekt extrahiert, bereinigt (Trimming) und 'None'-Felder ignoriert."),
        ("tests/test_sync.py", "TestMapping", "test_normalize_requires_number_and_name",
         "Zeilen ohne Kundennummer oder ohne Name werden verworfen (Rückgabe None)."),
        ("tests/test_sync.py", "TestMapping", "test_to_outlook_contact_minimal",
         "Ein minimaler Kunde erzeugt einen gültigen Graph-Body ohne Adresse und Notizen."),
        ("tests/test_sync.py", "TestMapping", "test_to_outlook_contact_full",
         "Alle Felder (Abteilung, Anschrift, Telefon/Fax, E-Mail, Website, Bankdaten, Notizen) werden korrekt auf den Outlook-Kontakt abgebildet."),
        ("tests/test_sync.py", "TestMapping", "test_fingerprint_stable_and_sensitive",
         "Der Fingerprint ist für identische Daten stabil und ändert sich bei geänderten Daten."),
        ("tests/test_sync.py", "TestMapping", "test_external_key",
         "Der externe Schlüssel wird normalisiert (SAGE: + Großbuchstaben)."),
        ("tests/test_sync.py", "TestPlan", "test_create_update_delete",
         "Die Diff-Engine erkennt neue, unveränderte und zu löschende Kontakte korrekt."),
        ("tests/test_sync.py", "TestPlan", "test_update_on_change",
         "Ein geänderter Kunde wird als Update (mit der zugehörigen contact_id) erkannt."),
        ("tests/test_sync.py", "TestSyncStore", "test_roundtrip",
         "Der Zustand (contact_id → Kundennummer, Fingerprint) wird korrekt gespeichert, aktualisiert, als gelöscht markiert und persistiert."),
        ("tests/test_runner.py", "TestRunnerCycle", "test_create_update_delete_cycle",
         "Integration: voller Zyklus über mehrere Läufe – Anlegen (2), unverändert (2), Änderung (1 Update), Löschung (1), erneutes Unverändert-Bestätigen."),
        ("tests/test_runner.py", "TestRunnerCycle", "test_run_forever_stops_on_event",
         "Die Dienst-Dauerschleife wartet das konfigurierte Intervall (60 Minuten) und beendet sich sauber beim Stop-Event."),
        ("tests/test_runner.py", "TestRunnerCycle", "test_service_once",
         "Der Dienst-CLI-Modus (--once) führt einen vollständigen Sync-Lauf mit Konfigurationsdatei aus und beendet sich mit Rückgabecode 0."),
    ]
))
doc.text.addElement(P(stylename="Normal"))

doc.text.addElement(heading("3. Testmethodik", 2))
doc.text.addElement(para("Eingesetzte Verfahren:"))
doc.text.addElement(bullet("Unit-Tests für reine Funktionen (Mapping, Fingerprint, Diff) ohne externe Abhängigkeiten."))
doc.text.addElement(bullet("Integrationstests mit Fake-Objekten: FakeConn simuliert die MySQL-Verbindung, FakeGraphClient simuliert die Graph-API (Ordnersuche, POST/PATCH/DELETE von Kontakten)."))
doc.text.addElement(bullet("Dependency Injection: Die Sync-Logik (runner.py) erhält ihre Abhängigkeiten über importierbare Symbole, sodass die Tests gezielt connect, discover_mapping, load_customers und GraphClient ersetzen (unittest.mock.patch)."))
doc.text.addElement(bullet("Temporäre Verzeichnisse für die Zustandsdatenbank (state.db), um Persistenz über Neustarts zu prüfen, ohne die Umgebung zu verunreinigen."))
doc.text.addElement(P(stylename="Normal"))

doc.text.addElement(heading("4. Ergebnisse des Testlaufs", 2))
doc.text.addElement(para("Kommando: ", bold_prefix=None))
doc.text.addElement(para("cd sage-outlook-sync && python -m unittest discover -s tests -v", style="Mono"))
doc.text.addElement(para("Ausgabe (Zusammenfassung):", bold_prefix=None))
doc.text.addElement(para("Ran 12 tests in 0.024s — OK (12 bestanden, 0 Fehler, 0 übersprungen)", style="Mono"))
doc.text.addElement(P(stylename="Normal"))
doc.text.addElement(make_table(
    ["#", "Testfall", "Modul", "Ergebnis"],
    [
        ("1", "test_create_update_delete_cycle", "test_runner", "bestanden"),
        ("2", "test_run_forever_stops_on_event", "test_runner", "bestanden"),
        ("3", "test_service_once", "test_runner", "bestanden"),
        ("4", "test_external_key", "test_sync", "bestanden"),
        ("5", "test_fingerprint_stable_and_sensitive", "test_sync", "bestanden"),
        ("6", "test_normalize_customer", "test_sync", "bestanden"),
        ("7", "test_normalize_requires_number_and_name", "test_sync", "bestanden"),
        ("8", "test_to_outlook_contact_full", "test_sync", "bestanden"),
        ("9", "test_to_outlook_contact_minimal", "test_sync", "bestanden"),
        ("10", "test_create_update_delete", "test_sync", "bestanden"),
        ("11", "test_update_on_change", "test_sync", "bestanden"),
        ("12", "test_roundtrip", "test_sync", "bestanden"),
    ]
))
doc.text.addElement(P(stylename="Normal"))

doc.text.addElement(heading("5. Nicht durch automatisierte Tests abgedeckt", 2))
doc.text.addElement(para(
    "Folgende Bereiche erfordern einen manuellen Test in der Zielumgebung und wurden nicht "
    "automatisiert:"
))
doc.text.addElement(bullet("MSAL-Authentifizierung gegen den echten Azure AD/Tenant (Client-Credentials-Flow)."))
doc.text.addElement(bullet("Reale Graph-API-Aufrufe inkl. Throttling (429/Retry-After) und Fehlercodes."))
doc.text.addElement(bullet("Verbindung zum produktiven Sage-MySQL-Server inkl. Schema-Erkennung (python -m sage_sync config.toml --discover)."))
doc.text.addElement(bullet("Windows-Dienst-Registrierung und -Betrieb (NSSM oder pywin32-Dienst, Ereignisprotokoll, Neustart bei Absturz)."))
doc.text.addElement(P(stylename="Normal"))
doc.text.addElement(para(
    "Empfohlene Verifikation vor Inbetriebnahme: 1) --discover gegen die Sage-Datenbank, "
    "2) --dry-run gegen das Ziel-Postfach, 3) ein manueller Lauf mit kleiner Kundenmenge, "
    "4) Dienst-Installation und Beobachtung des Logfiles/Eventlogs über mindestens ein Intervall."
))

doc.save("Testdokumentation_Sage_Outlook_Sync.odt")
print("ODT erstellt")
