import os
import json
import hashlib
from datetime import datetime
import chromadb
from langchain_voyageai import VoyageAIEmbeddings
from dotenv import load_dotenv
import voyageai

load_dotenv()

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")

# ── Initialize Voyage AI embeddings ──────────────────────
# VoyageAI converts text → vectors
# voyage-4 is their general purpose model, good for RAG
embeddings = VoyageAIEmbeddings(
    voyage_api_key=VOYAGE_API_KEY,
    model="voyage-4"
)

# ── Initialize ChromaDB ───────────────────────────────────
# PersistentClient saves to disk so data survives restarts
# This creates a chroma_db/ folder in your project
client = chromadb.PersistentClient(path="./chroma_db")

# A collection is like a table in a regular database
# get_or_create means: use existing if it exists, create if not
collection = client.get_or_create_collection(
    name="properties",
    metadata={"hnsw:space": "cosine"}  # cosine similarity for text
)

def generate_stable_id(property: dict) -> str:
    """
    Creates a unique ID based on address only.
    Address never changes even if property name or price changes.
    This is our 'passport number' for each property.
    """
    stable_key = property["address"].lower().strip()
    return hashlib.md5(stable_key.encode()).hexdigest()

def generate_content_hash(property: dict) -> str:
    """
    Creates a fingerprint of the property's data.
    If ANY field changes (price, amenities, pet policy etc)
    this hash changes — telling us to re-embed.
    """
    # Sort keys so order doesn't affect the hash
    content = json.dumps(property, sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()

def property_to_text(property: dict) -> str:
    unit_types = ", ".join(property["unit_types"])
    amenities = ", ".join(property["amenities"])
    utilities = ", ".join(property["utilities_included"]) if property["utilities_included"] else "no utilities included"

    rent_parts = []
    for unit, price in property["rent"].items():
        rent_parts.append(f"{unit}: {price}")
    rent_desc = ", ".join(rent_parts)

    pet_status = "pet friendly, pets allowed" if property["pet_friendly"] else "no pets allowed, not pet friendly"
    parking_status = property["parking"]

    text = f"""
        Property name: {property['name']}
        Location: {property['neighborhood']}, {property['city']}
        Address: {property['address']}
        Unit types: {unit_types}
        Monthly rent: {rent_desc}
        Utilities: {utilities}
        Pet policy: {pet_status}
        Parking: {parking_status}
        Amenities: {amenities}
        Availability: {property['availability']}
        Description: {property['highlights']}
            """.strip()

    return text

def embed_properties():
    """
    Main function. Reads properties.json and syncs to ChromaDB.
    - New properties get added
    - Changed properties get re-embedded
    - Unchanged properties get skipped
    """
    # Load properties
    with open("data/properties.json", "r") as f:
        data = json.load(f)
    
    properties = data["properties"]
    print(f"\n[EMBED] Found {len(properties)} properties in data file")
    print(f"[EMBED] Syncing to ChromaDB...\n")

    added = 0
    updated = 0
    skipped = 0

    for prop in properties:
        # Generate stable ID from address
        stable_id = generate_stable_id(prop)
        
        # Generate content hash
        content_hash = generate_content_hash(prop)
        
        # Check if this property already exists in ChromaDB
        existing = collection.get(ids=[stable_id])

        if existing["ids"]:
            # Property exists — check if content changed
            old_hash = existing["metadatas"][0].get("content_hash", "")
            
            if old_hash == content_hash:
                print(f"[SKIP]   {prop['name']} — no changes detected")
                skipped += 1
                continue
            else:
                print(f"[UPDATE] {prop['name']} — content changed, re-embedding")
                action = "update"
                updated += 1
        else:
            print(f"[ADD]    {prop['name']} — new property, embedding")
            action = "add"
            added += 1

        # Convert property to natural language text
        text = property_to_text(prop)
        
        # Generate embedding using Voyage AI
        # This is the API call that converts text → vector
        vector = embeddings.embed_query(text)

        # Store in ChromaDB with metadata
        collection.upsert(
            ids=[stable_id],
            embeddings=[vector],
            documents=[text],
            metadatas=[{
                "name": prop["name"],
                "address": prop["address"],
                "neighborhood": prop["neighborhood"],
                "city": prop["city"],
                "pet_friendly": str(prop["pet_friendly"]),
                "parking": prop["parking"],
                "content_hash": content_hash,
                "last_updated": datetime.now().isoformat(),
                "action": action
            }]
        )

    print(f"\n[EMBED] Done!")
    print(f"[EMBED] Added:   {added}")
    print(f"[EMBED] Updated: {updated}")
    print(f"[EMBED] Skipped: {skipped}")
    print(f"[EMBED] Total in ChromaDB: {collection.count()}\n")



voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
def search_properties(query: str, n_results: int = 3) -> list:
    """
    Two-step search:
    1. Vector search — broad retrieval of top 10 candidates
    2. VoyageAI re-ranker — re-scores candidates against query
    Returns top n_results most relevant properties.
    """
    # Step 1 — Vector search, get top 10 candidates
    query_vector = embeddings.embed_query(query)
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=10,
        include=['metadatas', 'documents']
    )

    documents = results['documents'][0]
    metadatas = results['metadatas'][0]

    # Step 2 — Re-rank using VoyageAI
    reranked = voyage_client.rerank(
        query=query,
        documents=documents,
        model="rerank-2",
        top_k=n_results
    )

    # Return re-ranked results with metadata
    final_results = []
    for r in reranked.results:
        meta = metadatas[r.index]
        final_results.append({
            "name": meta["name"],
            "neighborhood": meta["neighborhood"],
            "document": r.document,
            "relevance_score": r.relevance_score
        })

    return final_results

if __name__ == "__main__":
    embed_properties()