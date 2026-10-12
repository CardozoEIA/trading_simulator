import os

import httpx
from dotenv import load_dotenv
from supabase import Client, ClientOptions, create_client


load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


if not SUPABASE_URL:
    raise RuntimeError("Falta SUPABASE_URL en el archivo .env")

if not SUPABASE_KEY:
    raise RuntimeError("Falta SUPABASE_KEY en el archivo .env")

if not SUPABASE_SECRET_KEY:
    raise RuntimeError("Falta SUPABASE_SECRET_KEY en el archivo .env")


def _http_client() -> httpx.Client:
    # HTTP/1.1 on purpose: the default HTTP/2 connection is shared across
    # FastAPI's worker threads and drops ("Server disconnected") when several
    # requests hit it concurrently. HTTP/1.1 uses a pool of separate connections.
    return httpx.Client(
        http2=False,
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
    )


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
    options=ClientOptions(httpx_client=_http_client()),
)

supabase_admin: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
    options=ClientOptions(httpx_client=_http_client()),
)