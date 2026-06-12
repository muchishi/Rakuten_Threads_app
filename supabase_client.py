# supabase_client.py
import os
from dotenv import load_dotenv
from supabase import create_client



supabase = None

def get_supabase():
    global supabase

    if supabase:
        return supabase

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL / SUPABASE_KEY が未設定")

    supabase = create_client(url, key)
    return supabase