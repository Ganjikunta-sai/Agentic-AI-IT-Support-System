
import hashlib

from langchain_chroma import Chroma

from src.ingestion.document_loader import load_documents
from src.rag.chunking import split_documents
from src.rag.embeddings import get_embedding_model


# ChromaDB storage location
PERSIST_DIRECTORY = "chroma_db"

COLLECTION_NAME = "it_support_knowledge"


# Create or connect to the vector database
def create_vector_store(chunks):

    embedding_model = get_embedding_model()

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embedding_model,
        persist_directory=PERSIST_DIRECTORY
    )

    # Generate stable IDs to avoid duplicate records on reruns
    ids = [
        hashlib.sha256(
            (doc.metadata.get("source", "") + doc.page_content).encode("utf-8")
        ).hexdigest()
        for doc in chunks
    ]

    # Store text, metadata and embeddings
    vector_store.add_documents(
        documents=chunks,
        ids=ids
    )

    return vector_store


# Search for relevant documents
def search_documents(vector_store, query):

    results = vector_store.similarity_search(
        query,
        k=3
    )

    return results


if __name__ == "__main__":

    documents = load_documents()

    chunks = split_documents(documents)

    vector_store = create_vector_store(chunks)

    print("\nDocuments successfully stored in ChromaDB!")

    query = "How can I fix VPN authentication failure?"

    results = search_documents(vector_store, query)

    print("\nUser Question:", query)

    print("\nRetrieved Results:")

    for i, result in enumerate(results):

        print(f"\n--- Result {i + 1} ---")
        print(result.page_content)
        print("Metadata:", result.metadata)
