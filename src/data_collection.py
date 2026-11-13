
import requests
import json
import time

from pathlib import Path
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parent.parent

BOOKS_PATH = PROJECT_ROOT / "data" / "raw" / "books"
METADATA_PATH = PROJECT_ROOT / "data" / "raw" / "book_metadata.json"

API_URL = "https://gutendex.com/books/"


def load_metadata():

    if METADATA_PATH.exists():
        return json.loads(
            METADATA_PATH.read_text(encoding="utf-8")
        )

    return {}


def save_metadata(metadata):

    METADATA_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    METADATA_PATH.write_text(
        json.dumps(metadata, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )


def download_new_books(max_books=5):

    BOOKS_PATH.mkdir(parents=True, exist_ok=True)

    metadata = load_metadata()

    downloaded_count = 0
    skipped_count = 0

    params = {
        "languages": "en",
        "copyright": "false",
        "mime_type": "text/plain",
        "sort": "descending"
    }

    next_url = API_URL

    session = requests.Session()
    session.headers.update({
        "User-Agent": "NextWord-AI educational research project"
    })

    while next_url and downloaded_count < max_books:

        response = session.get(
            next_url,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()
        next_url = data["next"]
        params = None

        for book in data["results"]:

            book_id = str(book["id"])
            file_path = BOOKS_PATH / f"{book_id}.txt"

            if book_id in metadata or file_path.exists():
                skipped_count += 1
                continue

            formats = book.get("formats", {})

            text_url = next(
                (
                    url for file_type, url in formats.items()
                    if file_type.lower().startswith("text/plain")
                    and not url.lower().endswith(".zip")
                ),
                None
            )

            if not text_url:
                continue

            try:

                print("Downloading:", book["title"])

                book_response = session.get(
                    text_url,
                    timeout=60
                )

                book_response.raise_for_status()

                book_text = book_response.content.decode(
                    "utf-8",
                    errors="replace"
                )

                if len(book_text) < 1000:
                    print("Skipped: insufficient text")
                    continue

                file_path.write_text(
                    book_text,
                    encoding="utf-8"
                )

                metadata[book_id] = {
                    "id": book["id"],
                    "title": book["title"],
                    "authors": [
                        author["name"]
                        for author in book.get("authors", [])
                    ],
                    "languages": book.get("languages", []),
                    "copyright": book.get("copyright"),
                    "download_count": book.get("download_count"),
                    "source_url": text_url,
                    "downloaded_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "file": file_path.name
                }

                save_metadata(metadata)

                downloaded_count += 1

                print("Saved:", file_path.name)

                if downloaded_count >= max_books:
                    break

                time.sleep(1)

            except requests.RequestException as error:

                print(f"Download failed for {book_id}: {error}")

    print("\nDownload completed!")
    print("New downloads:", downloaded_count)
    print("Previously downloaded books skipped:", skipped_count)
    print("Total catalogue records:", len(metadata))
