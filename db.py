# db.py
import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wwpuorqzzvzuslbpukil.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
