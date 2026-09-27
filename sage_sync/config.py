__version__ = "1.1.0"

import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from dataclasses import dataclass, field


@dataclass
class MysqlConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = ""
    password: str = ""
    database: str = ""
    charset: str = "utf8mb4"
    sage_roots: str = ""
    mapping: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "MysqlConfig":
        return cls(
            host=data.get("host", "127.0.0.1"),
            port=int(data.get("port", 3306)),
            user=data.get("user", ""),
            password=data.get("password", ""),
            database=data.get("database", ""),
            charset=data.get("charset", "utf8mb4"),
            sage_roots=data.get("sage_roots", ""),
            mapping=dict(data.get("mapping", {})),
        )


@dataclass
class GraphConfig:
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""


@dataclass
class ContactsConfig:
    folder_name: str = "Sage Kontakte"
    keep_without_email: bool = True
    delete_missing: bool = True
    with_postal_address: bool = True


@dataclass
class SyncConfig:
    target_mail: str = ""
    interval_minutes: int = 60
    state_path: str = "state.db"
    log_file: str = ""


@dataclass
class AppConfig:
    mysql: MysqlConfig
    graph: GraphConfig
    contacts: ContactsConfig
    sync: SyncConfig
    base_dir: str = ""

    @property
    def state_path(self) -> str:
        import os

        return os.path.join(self.base_dir, self.sync.state_path)

    @classmethod
    def load(cls, path: str) -> "AppConfig":
        import os

        base_dir = os.path.dirname(os.path.abspath(path))
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
        mysql = MysqlConfig.from_dict(data.get("mysql", {}))
        graph = GraphConfig(**{
            k: data.get("graph", {}).get(k, "")
            for k in ("tenant_id", "client_id", "client_secret")
        })
        contacts = ContactsConfig(
            **{
                k: v
                for k, v in data.get("contacts", {}).items()
                if k in ContactsConfig.__dataclass_fields__
            }
        )
        sync = SyncConfig(
            **{
                k: v
                for k, v in data.get("sync", {}).items()
                if k in SyncConfig.__dataclass_fields__
            }
        )
        return cls(mysql=mysql, graph=graph, contacts=contacts, sync=sync, base_dir=base_dir)
