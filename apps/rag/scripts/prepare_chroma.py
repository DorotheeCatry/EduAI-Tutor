import os
import json
from pathlib import Path
from tqdm import tqdm
from PIL import Image
import pytesseract
from apps.rag.module_index_map import MODULE_INDEX_MAP

from langchain_community.document_loaders import TextLoader, NotebookLoader, PyPDFLoader
from langchain.schema import Document

from apps.rag.utils import load_embedding_function, get_chroma_collection
from apps.rag.splitter import get_splitter

# === CONFIGURATION ===
COURSES_PATH = Path("data/01_courses")
RESOURCES_PATH = Path("data/03_ressources")
INDEX_FOLDER = Path("data/index/")
CHUNK_THRESHOLD = 1000

SUPPORTED_IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".avif"]
SUPPORTED_TEXT_EXTS = [".md", ".ipynb", ".pdf"]

# === Chargement de l’index (sections) ===
def load_index():
    if not INDEX_FILE.exists():
        return {}
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_section(index_map, filename):
    for section, files in index_map.items():
        if filename in files:
            return section
    return "unknown"

# === OCR pour images ===
def ocr_image_to_document(filepath):
    try:
        text = pytesseract.image_to_string(Image.open(filepath))
    except Exception as e:
        print(f"❌ OCR failed for {filepath.name}: {e}")
        return None

    return Document(
        page_content=text,
        metadata={
            "source": filepath.name,
            "type": "image_cheatsheet",
            "section": "ressources"
        }
    )

# === Loader dynamique ===
def load_document(filepath):
    suffix = filepath.suffix.lower()

    if suffix == ".md":
        return TextLoader(str(filepath), encoding="utf-8").load()
    elif suffix == ".ipynb":
        return NotebookLoader(str(filepath)).load()
    elif suffix == ".pdf":
        return PyPDFLoader(str(filepath)).load()
    elif suffix in SUPPORTED_IMAGE_EXTS:
        doc = ocr_image_to_document(filepath)
        return [doc] if doc else []
    else:
        raise ValueError(f"Unsupported file type: {filepath.suffix}")

# === Indexation principale ===
def process_directory(path, index_map, collection, splitter, file_type):
    for file in tqdm(path.rglob("*"), desc=f"Indexing {file_type}"):
        if not file.is_file():
            continue
        if file.suffix.lower() not in SUPPORTED_TEXT_EXTS + SUPPORTED_IMAGE_EXTS:
            continue

        try:
            docs = load_document(file)
            if not docs:
                continue

            for doc in docs:
                section = get_section(index_map, file.name) if file_type == "courses" else "ressources"
                doc.metadata.update({
                    "source": file.name,
                    "type": file.suffix[1:],  # sans le point
                    "section": section
                })

            if len(docs[0].page_content) < CHUNK_THRESHOLD:
                chunks = docs
            else:
                chunks = splitter.split_documents(docs)

            collection.add(
                documents=[chunk.page_content for chunk in chunks],
                metadatas=[chunk.metadata for chunk in chunks],
                ids=[f"{file.stem}-{i}" for i in range(len(chunks))]
            )

            print(f"✅ {file.name} → {len(chunks)} chunk(s)")

        except Exception as e:
            print(f"⚠️ Skipping {file.name} ({e})")

# === MAIN ===
def main():
    embedding_fn = load_embedding_function()
    collection = get_chroma_collection(embedding_fn)
    splitter = get_splitter()
    index_map = load_index()

    process_directory(COURSES_PATH, index_map, collection, splitter, "courses")
    process_directory(RESOURCES_PATH, index_map, collection, splitter, "resources")

    print("✅ Chroma vectorstore fully populated.")

if __name__ == "__main__":
    main()
