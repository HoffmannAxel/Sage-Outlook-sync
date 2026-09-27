# Sage 50 (MySQL) → Outlook Kontakte Replikation

**Version: 1.1.0**

Idempotentes Tool, das Kunden aus einer **Sage 50 (2017) MySQL-Datenbank**
in einen **Kontaktordner eines Microsoft-365-/Outlook.com-Kontos** repliziert
(Microsoft Graph API). Wiederholtes Ausführen zieht Änderungen und Löschungen nach.
Läuft als **Windows-Dienst auf einem MS-Server** (NSSM oder nativ per pywin32)
oder einmalig per CLI.

## Features

- **Windows-Dienst-Betrieb**: Dauerschleife mit konfigurierbarem Intervall, Stop-Signal-Support, File-Logging

- Automatische Erkennung der Sage-Kundentabelle und -spalten (`--discover`),
  Überschreiben per Config möglich
- Zielordner (z.B. „Sage Kontakte") wird angelegt, falls nicht vorhanden
- Hash-basierter Abgleich: nur geänderte Kunden werden geschrieben
- In Sage verschwundene Kunden werden im Ordner gelöscht (abschaltbar)
- Dry-Run-Modus, lokaler Zustand in `state.db`
- IBAN/Bank/Notizen landen im Feld „Notizen" des Kontakts

## Voraussetzungen

- Python 3.10+
- Lesezugriff auf die Sage-MySQL-Datenbank (empfohlen: eigener ReadOnly-User)
- Eine Azure-App-Registrierung mit Client-Credentials (siehe unten)

## Einrichtung

### 1. Azure-App registrieren (einmalig)

1. [portal.azure.com](https://portal.azure.com) → **App registrations** → **New registration**
2. Name z.B. `sage-outlook-sync`, Konto-Typ „Accounts in this organizational directory only"
3. **Certificates & secrets** → neuen **Client secret** anlegen, **Wert** kopieren
4. **API permissions** → **Microsoft Graph** → **Application permissions**:
   - `Contacts.ReadWrite`
   - ggf. `User.Read.All` (zum Auffinden des Zielbenutzers)
5. **Admin consent** erteilen (Button auf der Berechtigungsseite)

### 2. Konfiguration

```bash
pip install -r requirements.txt
cp config.example.toml config.toml
# config.toml ausfüllen: MySQL-Zugang, Azure tenant_id/client_id/client_secret
```

### 3. Tabellenstruktur prüfen

```bash
python -m sage_sync config.toml --discover
```

Zeigt die automatisch erkannte Kundentabelle und Spalten. Falls Felder nicht
erkannt werden: entsprechende Spaltennamen in `config.toml` unter `[mysql.mapping]` eintragen.

### 4. Erster Lauf (Dry-Run)

```bash
python -m sage_sync config.toml --dry-run --target-mail vorname.nachname@firma.de
```

Zeigt nur, wie viele Kontakte angelegt/aktualisiert/gelöscht würden.

### 5. Sync ausführen

```bash
python -m sage_sync config.toml --target-mail vorname.nachname@firma.de
```

## Dienstbetrieb auf einem MS-Server

In `config.toml` unter `[sync]` das Ziel-Postfach und das Intervall setzen:

```toml
[sync]
target_mail = "vorname.nachname@firma.de"
interval_minutes = 60
state_path = "state.db"
log_file = "sync.log"        # relativ zur config.toml
```

Der Dienst läuft als Dauerschleife (`python -m sage_sync.service`) und führt den
Sync sofort beim Start und dann alle `interval_minutes` aus.

### Variante A: NSSM (empfohlen)

Kein pywin32 nötig; NSSM überwacht den Prozess, startet ihn bei Absturz neu
und kümmert sich um Windows-Dienst-Signale:

```powershell
nssm install SageOutlookSync "C:\Pfad\python.exe" "-m sage_sync.service --config C:\Pfad\config.toml"
nssm set SageOutlookSync AppStdout "C:\Pfad\sync.log"
nssm set SageOutlookSync AppStderr "C:\Pfad\sync.log"
nssm set SageOutlookSync AppRotateFiles 1
nssm start SageOutlookSync
```

### Variante B: nativer Windows-Dienst (pywin32)

```powershell
pip install pywin32
# pywin32-Dienst-DLL registrieren (einmalig, als Admin):
python C:\Pfad\Lib\site-packages\win32\pythonservice.exe --register

sc.exe create SageOutlookSync binPath= "C:\Pfad\python.exe -m sage_sync.service --config C:\Pfad\config.toml" start= auto DisplayName= "Sage Outlook Sync"
sc.exe description SageOutlookSync "Repliziert Sage-50-Kunden nach Outlook (Microsoft 365)"
sc.exe start SageOutlookSync
```

Hinweis: Bei Variante B muss der Dienst-Account auf `config.toml` und `state.db`
Lesen/Schreiben dürfen; Log-Meldungen gehen zusätzlich ins Windows-Eventlog.

### Handbetrieb / Tests

```powershell
python -m sage_sync.service --config config.toml --once     # ein einzelner Lauf
python -m sage_sync.service --config config.toml           # Dauerschleife (Strg+C beendet)
```

### Alternative ohne Dienst: Taskplaner

```
schtasks /create /tn "Sage Outlook Sync" /tr "python -m sage_sync C:\pfad\config.toml" /sc hourly
```

## Konfigurationsoptionen

| Option | Bedeutung |
|---|---|
| `folder_name` | Ziel-Kontaktordner im Outlook-Konto (wird angelegt) |
| `keep_without_email` | Kunden ohne E-Mail-Adresse trotzdem übertragen (Sage-Adressen haben oft keine E-Mail) |
| `delete_missing` | In Sage gelöschte Kunden auch in Outlook löschen |
| `with_postal_address` | Firmenanschrift als Geschäftsadresse übernehmen |

Hinweis: Die Programmversion steht in `sage_sync/__init__.py` (`__version__`) und ist in allen Modulen als `__version__` hinterlegt.

## Sicherheitshinweise

- `config.toml` enthält Zugangsdaten – Dateiberechtigungen einschränken, nicht committen
- Für MySQL einen dedizierten ReadOnly-User verwenden (`GRANT SELECT ON sage50.* TO ...`)
- Azure-Secret regelmäßig rotieren; nur die benötigten Graph-Berechtigungen vergeben

## Tests

```bash
python -m unittest discover -s tests
```

## Projektstruktur

```
sage_sync/
  __main__.py    Einmal-CLI (--discover, --dry-run)
  service.py    Dienstbetrieb (Konsolloop für NSSM, nativer pywin32-Dienst)
  runner.py     Gemeinsame Sync-Logik + Logging-Setup
  config.py     TOML-Konfiguration ([mysql], [graph], [sync], [contacts])
  db.py         MySQL-Zugriff + Schema-Erkennung
  graph.py      Graph-API-Client (Auth, Ordner, CRUD)
  mapping.py    Sage-Zeile → Outlook-Kontakt, Fingerprints
  sync.py       Diff-Engine + Zustands-Store (state.db)
tests/
  test_sync.py    Unit-Tests (Mapping, Diff, Store)
  test_runner.py  Integrationstests (voller Zyklus mit Fakes, Dienst-Loop)
config.example.toml
```

## Hinweise

- Das Tool verwaltet ausschließlich Kontakte im konfigurierten Ordner;
  manuell dort erstellte Kontakte ohne Sage-Kundennummer bleiben unberührt.
- Sage 50 speichert die Daten je nach Installation in unterschiedlichen
  Schemata; die automatische Erkennung deckt gängige deutsche/englische
  Tabellen- und Spaltennamen (kunden/kunde/customer/adressen etc.) ab.
