"""MySQL-Zugriff und automatische Erkennung der Sage-Kundentabelle/-spalten."""

__version__ = "0.1.0"
from .mapping import FIELDS, _CANDIDATES, normalize_customer


def connect(cfg):
    import mysql.connector

    return mysql.connector.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        charset=cfg.charset,
        autocommit=True,
    )


def _norm(name: str) -> str:
    return name.strip().lower().replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("ß", "s")


def discover_mapping(conn, mapping_overrides: dict | None = None) -> dict:
    """Findet Kundentabelle + Spalten. Überschreibem aus der Config haben Vorrang."""
    overrides = {k: v for k, v in (mapping_overrides or {}).items() if v}
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT table_name AS t FROM information_schema.tables "
        "WHERE table_schema = DATABASE()"
    )
    tables = [r["t"] for r in cur.fetchall()]

    best = None
    for table in tables:
        if "kunde" in _norm(table) or "customer" in _norm(table) or "adress" in _norm(table):
            cur.execute(
                "SELECT column_name AS c FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = %s",
                (table,),
            )
            columns = [r["c"] for r in cur.fetchall()]
            found = _match_columns(columns)
            if found and (best is None or len(found) > len(best[1])):
                best = (table, found)
    cur.close()

    if best is None:
        raise RuntimeError(
            "Keine Kundentabelle gefunden. Bitte Tabellen-/Spaltennamen in "
            "config.toml unter [mysql.mapping] angeben."
        )
    table, found = best
    mapping = dict(found)
    mapping["customer_table"] = overrides.get("customer_table", table)
    for f in FIELDS:
        key = f + "_column"
        if key in overrides:
            mapping[f] = overrides[key]
        else:
            mapping[f] = found.get(f, "")
    return mapping


def _match_columns(columns: list[str]) -> dict:
    lowered = {_norm(c): c for c in columns}
    found = {}
    for field_name, candidates in _CANDIDATES.items():
        if field_name == "customer_table":
            continue
        key = field_name.removesuffix("_column")
        for cand in candidates:
            for norm, original in lowered.items():
                if norm == cand or norm.startswith(cand + "_") or norm.endswith("_" + cand):
                    found[key] = original
                    break
            if key in found:
                break
    return found


def load_customers(conn, mapping: dict):
    """Liest alle Kundenzeilen (Rohdaten)."""
    table = mapping.get("customer_table")
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM `" + table.replace("`", "") + "`")
    rows = cur.fetchall()
    cur.close()
    return rows


def build_customers(rows, mapping: dict, keep_without_email: bool = True) -> dict:
    """Kundennummer -> kanonisches Kunden-Dict (ungefiltert nach E-Mail)."""
    customers = {}
    for row in rows:
        customer = normalize_customer(row, mapping)
        if not customer:
            continue
        number = customer["account_number"]
        if not keep_without_email and not customer.get("email"):
            continue
        customers[number] = customer
    return customers
