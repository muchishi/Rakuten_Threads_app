# supabase_client.py
"""
Supabaseクライアントのシングルトン管理
"""
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

_supabase: Client | None = None


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase
