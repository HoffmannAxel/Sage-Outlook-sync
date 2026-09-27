# Testdokumentation: Sage 50 (MySQL) → Outlook Kontakte Replikation

> Diese Datei ist die Markdown-Fassung. Die ODT-Fassung wird mit
> `python make_test_doc.py` erzeugt (benötigt `pip install odfpy`).

| | |
|---|---|
| Projekt | sage-outlook-sync |
| Version | 1.1.0 |
| Testlauf | 27.09.2026, 11:48 UTC |
| Testumgebung | Sandbox, Python 3.12.14, Linux |
| Testframework | unittest (Standardbibliothek) |
| Testrunner-Kommando | `python -m unittest discover -s tests` |
| Ergebnis | **12 Tests, 12 bestanden, 0 Fehler, 0 übersprungen** |

## 1. Überblick und Testziel

Die Tests validieren die Kernlogik der Replikation: das Mapping von Sage-Kundendaten
auf Outlook-Kontakte (Microsoft Graph API), die Diff-Engine
(Anlegen/Aktualisieren/Löschen), die Persistenz des lokalen Zustands (state.db),
den vollständigen Sync-Zyklus mit simulierter MySQL-Datenbank und Graph-API sowie
den Dauerbetrieb des Windows-Dienstes.

MySQL-Server und Microsoft Graph werden bewusst durch Fakes ersetzt (kein
Netzwerkzugriff, deterministische, wiederholbare Läufe). Die Authentifizierung
(MSAL/Client-Credentials) und die reine Netzwerkkommunikation sind nicht
Bestandteil der automatisierten Tests.

## 2. Testdateien und Abdeckung

| # | Testfall | Klasse / Datei | Zweck / erwartetes Ergebnis |
|---|---|---|---|
| 1 | `test_normalize_customer` | TestMapping / test_sync.py | Kundennummer, Name und Ort werden korrekt extrahiert, bereinigt (Trimming), `None`-Felder ignoriert |
| 2 | `test_normalize_requires_number_and_name` | TestMapping | Zeilen ohne Kundennummer oder Name werden verworfen (Rückgabe `None`) |
| 3 | `test_to_outlook_contact_minimal` | TestMapping | Minimaler Kunde erzeugt gültigen Graph-Body ohne Adresse und Notizen |
| 4 | `test_to_outlook_contact_full` | TestMapping | Alle Felder (Abteilung, Anschrift, Telefon/Fax, E-Mail, Website, Bankdaten, Notizen) werden korrecktabgebildet |
| 5 | `test_fingerprint_stable_and_sensitive` | TestMapping | Fingerprint stabil für identische Daten, ändert sich bei geänderten Daten |
| 6 | `test_external_key` | TestMapping | Externer Schlüssel wird normalisiert (`SAGE:` + Großbuchstaben) |
| 7 | `test_create_update_delete` | TestPlan | Diff-Engine erkennt neue, unveränderte und zu löschende Kontakte korrekt |
| 8 | `test_update_on_change` | TestPlan | Geänderter Kunde wird als Update mit zugehöriger contact_id erkannt |
| 9 | `test_roundtrip` | TestSyncStore | Zustand (contact_id → Kundennummer, Fingerprint) wird korrekt gespeichert, aktualisiert, als gelöscht markiert und persistiert |
| 10 | `test_create_update_delete_cycle` | TestRunnerCycle / test_runner.py | Integration: voller Zyklus – Anlegen (2), unverändert (2), Änderung (1 Update), Löschung (1), erneute Bestätigung |
| 11 | `test_run_forever_stops_on_event` | TestRunnerCycle | Dienst-Dauerschleife wartet das Intervall (60 Min.) und beendet sich sauber beim Stop-Event |
| 12 | `test_service_once` | TestRunnerCycle | Dienst-CLI-Modus (`--once`) führt vollständigen Lauf mit Config-Datei aus, Rückgabecode 0 |

## 3. Testmethodik

- **Unit-Tests** für reine Funktionen (Mapping, Fingerprint, Diff) ohne externe Abhängigkeiten.
- **Integrationstests mit Fakes**: `FakeConn` simuliert die MySQL-Verbindung, `FakeGraphClient` simuliert die Graph-API (Ordnersuche, POST/PATCH/DELETE von Kontakten).
- **Dependency Injection**: Die Sync-Logik (runner.py) erhält ihre Abhängigkeiten über importierbare Symbole; die Tests ersetzen `connect`, `discover_mapping`, `load_customers` und `GraphClient` gezielt (`unittest.mock.patch`).
- **Temporäre Verzeichnisse** für die Zustandsdatenbank (state.db), um Persistenz über Neustarts zu prüfen, ohne die Umgebung zu verunreinigen.

## 4. Ergebnisse des Testlaufs

Kommando:

```
cd sage-outlook-sync && python -m unittest discover -s tests -v
```

Ausgabe (Zusammenfassung):

```
Ran 12 tests in 0.024s
OK (12 bestanden, 0 Fehler, 0 übersprungen)
```

Alle 12 Testfälle bestanden (siehe Tabelle in Abschnitt 2).

## 5. Nicht durch automatisierte Tests abgedeckt

Folgende Bereiche erfordern einen manuellen Test in der Zielumgebung:

- MSAL-Authentifizierung gegen den echten Azure AD/Tenant (Client-Credentials-Flow)
- Reale Graph-API-Aufrufe inkl. Throttling (429/Retry-After) und Fehlercodes
- Verbindung zum produktiven Sage-MySQL-Server inkl. Schema-Erkennung (`--discover`)
- Windows-Dienst-Registrierung und -Betrieb (NSSM/pywin32, Ereignisprotokoll, Neustart bei Absturz)

**Empfohlene Verifikation vor Inbetriebnahme:**

1. `--discover` gegen die Sage-Datenbank
2. `--dry-run` gegen das Ziel-Postfach
3. ein manueller Lauf mit kleiner Kundenmenge
4. Dienst-Installation und Beobachtung des Logfiles/Eventlogs über mindestens ein Intervall
