
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.ingestion.document_loader import load_documents


def split_documents(documents):

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", " ", ""]
    )

    chunks = text_splitter.split_documents(documents)

    return chunks


if __name__ == "__main__":

    documents = load_documents()

    chunks = split_documents(documents)

    print("Total original documents:", len(documents))
    print("Total chunks generated:", len(chunks))

    for i, chunk in enumerate(chunks[:5]):

        print(f"\n--- Chunk {i + 1} ---")
        print(chunk.page_content)
        print("Metadata:", chunk.metadata)
