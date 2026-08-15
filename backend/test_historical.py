from app.core.supabase import supabase


response = (
    supabase
    .table("historical_data")
    .select("*")
    .execute()
)

print(response.data)