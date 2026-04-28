"""
Seed script to populate the database with sample data.
Usage: python -m scripts.seed
"""
import json
import uuid
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_json(filepath):
    with open(filepath, "r") as f:
        return json.load(f)


def main():
    database_url = os.getenv(
        "DATABASE_URL_SYNC",
        "postgresql://telo:telo_dev@localhost:5432/telo_venue_assistant",
    )

    engine = create_engine(database_url)
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

    venues_data = load_json(os.path.join(data_dir, "venues.json"))
    docs_data = load_json(os.path.join(data_dir, "venue_docs.json"))

    with Session(engine) as session:
        result = session.execute(text("SELECT COUNT(*) FROM venues"))
        count = result.scalar()
        if count > 0:
            print(f"Database already has {count} venues. Skipping seed.")
            return

        id_map = {}
        print(f"Seeding {len(venues_data)} venues...")

        for venue in venues_data:
            original_id = venue.pop("id")
            new_id = uuid.uuid4()
            id_map[original_id] = new_id

            session.execute(
                text("""
                    INSERT INTO venues (id, name, city, neighborhood, capacity,
                        price_per_head_usd, venue_type, amenities, tags,
                        description, policies)
                    VALUES (:id, :name, :city, :neighborhood, :capacity,
                        :price, :venue_type, CAST(:amenities AS jsonb),
                        CAST(:tags AS jsonb), :description, CAST(:policies AS jsonb))
                    ON CONFLICT DO NOTHING
                """),
                {
                    "id": new_id,
                    "name": venue["name"],
                    "city": venue["city"],
                    "neighborhood": venue.get("neighborhood"),
                    "capacity": venue.get("capacity"),
                    "price": venue.get("price_per_head_usd"),
                    "venue_type": venue.get("venue_type"),
                    "amenities": json.dumps(venue.get("amenities", [])),
                    "tags": json.dumps(venue.get("tags", [])),
                    "description": venue.get("description"),
                    "policies": json.dumps(venue.get("policies", {})),
                },
            )

        print(f"Seeding {len(docs_data)} documents...")

        for doc in docs_data:
            venue_uuid = id_map.get(doc.get("venue_id"))

            title_lower = doc["title"].lower()
            if "faq" in title_lower:
                doc_type = "FAQ"
            elif "polic" in title_lower:
                doc_type = "POLICY"
            elif "note" in title_lower:
                doc_type = "OPERATIONAL_NOTE"
            elif "booking" in title_lower:
                doc_type = "BOOKING_DETAIL"
            else:
                doc_type = "GENERAL"

            session.execute(
                text("""
                    INSERT INTO documents (id, venue_id, title, content, doc_type, status)
                    VALUES (:id, :venue_id, :title, :content, :doc_type, 'PENDING')
                """),
                {
                    "id": uuid.uuid4(),
                    "venue_id": venue_uuid,
                    "title": doc["title"],
                    "content": doc["content"],
                    "doc_type": doc_type,
                },
            )

        session.commit()
        print("Seed complete.")

        for original_id, new_id in id_map.items():
            result = session.execute(text("SELECT name FROM venues WHERE id = :id"), {"id": new_id})
            name = result.scalar()
            print(f"  {original_id} -> {new_id} ({name})")

        doc_count = session.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        print(f"  Total documents: {doc_count}")


if __name__ == "__main__":
    main()