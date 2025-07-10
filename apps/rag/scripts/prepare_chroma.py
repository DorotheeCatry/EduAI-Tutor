import os
import json
from pathlib import Path
from tqdm import tqdm
from PIL import Image
import pytesseract

from langchain_community.document_loaders import TextLoader, NotebookLoader, PyPDFLoader
from langchain.schema import Document

from apps.rag.utils import load_embedding_function, get_chroma_collection
from apps.rag.splitter import get_splitter
from apps.rag.module_index_map import MODULE_INDEX_MAP

# === CONFIGURATION ===
DATA_FOLDER = Path("data/contents")
COURSES_FOLDER = DATA_FOLDER / "courses"
INDEX_FOLDER = DATA_FOLDER / "index"
RESOURCES_FOLDER = DATA_FOLDER / "resources"
CHUNK_THRESHOLD = 1000

SUPPORTED_IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".avif"]
SUPPORTED_TEXT_EXTS = [".md", ".ipynb", ".pdf"]

_loaded_indexes = {}

# === SECTION DETECTION LOGIC ===
def get_section(filepath: Path):
    filename = filepath.name
    parent_dir = filepath.parent.name

    # --- Cas cours ---
    if parent_dir in MODULE_INDEX_MAP:
        index_file = MODULE_INDEX_MAP[parent_dir]
        if index_file not in _loaded_indexes:
            try:
                with open(INDEX_FOLDER / index_file, "r", encoding="utf-8") as f:
                    _loaded_indexes[index_file] = json.load(f)
            except Exception as e:
                print(f"❌ Erreur lecture {index_file}: {e}")
                return "unknown"

        index = _loaded_indexes[index_file]
        for section, files in index.items():
            if filename in files:
                return section
        return "unknown"

    # --- Cas ressources ---
    elif parent_dir == "resources":
        index_file = "ressources_index.json"
        if index_file not in _loaded_indexes:
            try:
                with open(INDEX_FOLDER / index_file, "r", encoding="utf-8") as f:
                    _loaded_indexes[index_file] = json.load(f)
            except Exception as e:
                print(f"❌ Erreur lecture {index_file}: {e}")
                _loaded_indexes[index_file] = {}

        index = _loaded_indexes[index_file]
        for section, files in index.items():
            if filename in files:
                return section

        # Fallback par nom
        if "__" in filename:
            return filename.split("__")[0]

        return "ressources"

    return "unknown"

# === OCR pour images ===
def ocr_image_to_document(filepath: Path):
    try:
        text = pytesseract.image_to_string(Image.open(filepath))
        return Document(
            page_content=text,
            metadata={
                "source": filepath.name,
                "type": "image_cheatsheet",
                "section": get_section(filepath)
            }
        )
    except Exception as e:
        print(f"❌ OCR failed for {filepath.name}: {e}")
        return None

# === Loader unitaire ===
def load_document(filepath: Path):
    suffix = filepath.suffix.lower()

    try:
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
            raise ValueError(f"Unsupported file type: {suffix}")
    except Exception as e:
        print(f"❌ Erreur lors du chargement de {filepath.name} : {e}")
        return []

# === Indexation d’un dossier complet ===
def process_directory(path: Path, collection, splitter, file_type: str):
    for file in tqdm(path.rglob("*"), desc=f"Indexing {file_type}"):
        if not file.is_file():
            continue
        if file.suffix.lower() not in SUPPORTED_TEXT_EXTS + SUPPORTED_IMAGE_EXTS:
            continue

        docs = load_document(file)
        if not docs:
            continue

        section = get_section(file)

        if file_type == "resources":
            existing_sections = {
                s.lower().split("_", 1)[1]  # "01_python" → "python"
                for s in MODULE_INDEX_MAP.keys()
            }
            if section not in existing_sections:
                print(f"⏩ Skip {file.name} (section '{section}' non encore couverte)")
                continue

        for doc in docs:
            doc.metadata.update({
                "source": file.name,
                "type": file.suffix[1:],  # "md", "pdf"…
                "section": section
            })

        chunks = docs if len(docs[0].page_content) < CHUNK_THRESHOLD else splitter.split_documents(docs)

        try:
            collection.add(
                documents=[chunk.page_content for chunk in chunks],
                metadatas=[chunk.metadata for chunk in chunks],
                ids=[f"{file.stem}-{i}" for i in range(len(chunks))]
            )
        except Exception as e:
            print(f"❌ Failed to index {file.name}: {e}")
            
        print(f"✅ {file.name} → {len(chunks)} chunk(s)")

# === POINT D’ENTRÉE ===
def main():
    embedding_fn = load_embedding_function()
    collection = get_chroma_collection(embedding_fn)
    splitter = get_splitter()

    for module_dir in MODULE_INDEX_MAP.keys():
        full_path = COURSES_FOLDER / module_dir
        if full_path.exists():
            process_directory(full_path, collection, splitter, "courses")
        else:
            print(f"⚠️ Dossier {full_path} non trouvé, ignoré.")

    if RESOURCES_FOLDER.exists():
        process_directory(RESOURCES_FOLDER, collection, splitter, "resources")

    print("✅ Chroma vectorstore fully populated.")

if __name__ == "__main__":
    main()
