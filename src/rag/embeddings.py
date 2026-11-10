
from langchain_huggingface import HuggingFaceEmbeddings

from src.ingestion.document_loader import load_documents
from src.rag.chunking import split_documents


# Initialize the embedding model
def get_embedding_model():

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

    return embeddings


# Generate embeddings for document chunks
def generate_embeddings(chunks):

    embedding_model = get_embedding_model()

    vectors = embedding_model.embed_documents(
        [chunk.page_content for chunk in chunks]
    )

    return vectors


if __name__ == "__main__":

    documents = load_documents()

    chunks = split_documents(documents)

    vectors = generate_embeddings(chunks)

    print("Total chunks:", len(chunks))
    print("Total embeddings:", len(vectors))

    if vectors:
        print("Embedding dimensions:", len(vectors[0]))
        print("First embedding:", vectors[0][:10])
