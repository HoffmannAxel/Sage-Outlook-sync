"""Microsoft Graph Client: Client-Credentials-Auth, Kontaktordner, Kontakt-CRUD."""

__version__ = "0.1.0"
import time

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["https://graph.microsoft.com/.default"]


class GraphClient:
    def __init__(self, cfg):
        import msal
        import requests

        self._msal = msal
        self._requests = requests
        self.cfg = cfg
        self._app = self._msal.ConfidentialClientApplication(
            cfg.client_id,
            authority=f"https://login.microsoftonline.com/{cfg.tenant_id}",
            client_credential=cfg.client_secret,
        )
        self._token = None
        self._token_expiry = 0

    def _access_token(self):
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        result = self._app.acquire_token_for_client(scopes=SCOPES)
        if "access_token" not in result:
            raise RuntimeError(f"Graph-Authentifizierung fehlgeschlagen: {result.get('error_description', result)}")
        self._token = result["access_token"]
        self._token_expiry = time.time() + result.get("expires_in", 3600)
        return self._token

    def _headers(self):
        return {
            "Authorization": "Bearer " + self._access_token(),
            "Content-Type": "application/json",
        }

    def request(self, method: str, path: str, body: dict | None = None, params: dict | None = None, retries: int = 3):
        url = path if path.startswith("http") else GRAPH + path
        for attempt in range(retries):
            resp = self._requests.request(method, url, headers=self._headers(), json=body, params=params, timeout=60)
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = int(resp.headers.get("Retry-After", "2")) or 2
                time.sleep(wait)
                continue
            if resp.status_code == 401 and attempt < retries - 1:
                self._token = None
                continue
            return resp
        return resp

    def request_json(self, method: str, path: str, **kwargs):
        resp = self.request(method, path, **kwargs)
        if resp.status_code >= 400:
            raise RuntimeError(f"Graph-Fehler {resp.status_code} bei {method} {path}: {resp.text[:500]}")
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()


def find_or_create_folder(client: GraphClient, mail: str, folder_name: str) -> str:
    folders = client.request_json("GET", f"/users/{mail}/contactFolders", params={"$top": 100})
    while True:
        for folder in folders.get("value", []):
            if folder["displayName"].lower() == folder_name.lower():
                return folder["id"]
        nxt = folders.get("@odata.nextLink")
        if not nxt:
            break
        folders = client.request_json("GET", nxt)
    created = client.request_json("POST", f"/users/{mail}/contactFolders", body={"displayName": folder_name})
    return created["id"]


def list_folder_contacts(client: GraphClient, mail: str, folder_id: str) -> list[dict]:
    params = {"$top": 100, "$select": "id,extensions"}
    page = client.request_json("GET", f"/users/{mail}/contactFolders/{folder_id}/contacts", params=params)
    contacts = []
    while True:
        for contact in page.get("value", []):
            contacts.append(contact)
        nxt = page.get("@odata.nextLink")
        if not nxt:
            return contacts
        page = client.request_json("GET", nxt)


def get_extension_values(client: GraphClient, mail: str, contact_id: str) -> dict | None:
    resp = client.request(
        "GET",
        f"/users/{mail}/contacts/{contact_id}/extensions/sage.sync",
    )
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise RuntimeError(f"Graph-Fehler {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def upsert_extension(client: GraphClient, mail: str, contact_id: str, data: dict):
    existing = get_extension_values(client, mail, contact_id)
    payload = {
        "@odata.type": "microsoft.graph.openTypeExtension",
        "extensionName": "sage.sync",
        **data,
    }
    if existing is None:
        client.request_json("POST", f"/users/{mail}/contacts/{contact_id}/extensions", body=payload)
    else:
        client.request_json("PATCH", f"/users/{mail}/contacts/{contact_id}/extensions/sage.sync", body=data)


def create_contact(client: GraphClient, mail: str, body: dict) -> dict:
    return client.request_json("POST", f"/users/{mail}/contacts", body=body)


def move_contact(client: GraphClient, mail: str, contact_id: str, folder_id: str):
    client.request_json("POST", f"/users/{mail}/contacts/{contact_id}/move", body={"destinationId": folder_id})


def patch_contact(client: GraphClient, mail: str, contact_id: str, body: dict):
    client.request_json("PATCH", f"/users/{mail}/contacts/{contact_id}", body=body)


def delete_contact(client: GraphClient, mail: str, contact_id: str):
    client.request_json("DELETE", f"/users/{mail}/contacts/{contact_id}")
