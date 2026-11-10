
import os

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader
)


KNOWLEDGE_BASE_PATH = "data/knowledge_base"


def load_documents():

    documents = []

    for filename in os.listdir(KNOWLEDGE_BASE_PATH):

        file_path = os.path.join(
            KNOWLEDGE_BASE_PATH,
            filename
        )

        if filename.endswith(".pdf"):
            loader = PyPDFLoader(file_path)

        elif filename.endswith(".txt"):
            loader = TextLoader(
                file_path,
                encoding="utf-8"
            )

        elif filename.endswith(".docx"):
            loader = Docx2txtLoader(file_path)

        else:
            print(f"Skipping unsupported file: {filename}")
            continue

        loaded_docs = loader.load()

        documents.extend(loaded_docs)

        print(f"Loaded: {filename}")

    return documents


if __name__ == "__main__":

    docs = load_documents()

    print("\nTotal document pages/files:", len(docs))

    for doc in docs:
        print(doc.page_content[:200])
