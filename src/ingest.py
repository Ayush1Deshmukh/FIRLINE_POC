import os
import google.generativeai as genai
import psycopg
from pgvector.psycopg import register_vector
from dotenv import load_dotenv

# 1. Setup
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("❌ Error: GOOGLE_API_KEY not found.")
    exit(1)

genai.configure(api_key=GOOGLE_API_KEY)

# 2. Connect to the Database
try:
    print("--- 📚 Librarian: Connecting to 'fireline' database... ---")
    conn = psycopg.connect(os.environ.get("DB_CONNECTION"), autocommit=True)
except Exception as e:
    print(f"❌ Error connecting to DB: {e}")
    print("Did you run 'createdb fireline'?")
    exit(1)

# 3. Prepare the Table
# We use 768 dimensions because that is the size of Gemini's text-embedding-004 model
conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
register_vector(conn)

print("--- 📚 Librarian: Creating 'runbook_chunks' table... ---")
conn.execute("DROP TABLE IF EXISTS runbook_chunks")
conn.execute("""
    CREATE TABLE runbook_chunks (
        id bigserial PRIMARY KEY,
        content text,
        embedding vector(768) 
    )
""")

# 4. Read the Knowledge
print("--- 📚 Librarian: Reading runbook.md... ---")
try:
    with open("knowledge/runbook.md", "r") as f:
        text = f.read()
except FileNotFoundError:
    print("❌ Error: knowledge/runbook.md not found.")
    exit(1)

# 5. Split into Chunks
# Simple splitting by double newlines (paragraphs/headers)
chunks = text.split("\n\n")
print(f"--- 📚 Librarian: Found {len(chunks)} chunks of knowledge. ---")

# 6. Embed and Store
print("--- 📚 Librarian: Embedding and storing chunks... ---")
model_name = "models/text-embedding-004"

for i, chunk in enumerate(chunks):
    if not chunk.strip():
        continue

    # Generate Vector (Math) for the text
    result = genai.embed_content(
        model=model_name,
        content=chunk,
        task_type="retrieval_document"
    )
    embedding = result['embedding']

    # Insert into Postgres
    conn.execute(
        "INSERT INTO runbook_chunks (content, embedding) VALUES (%s, %s)",
        (chunk, embedding)
    )
    print(f"   ✅ Stored chunk {i+1}/{len(chunks)}")

print("--- 🎉 Success! The Brain is populated. ---")
conn.close()
