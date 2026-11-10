
import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.rag.vector_store import (
    create_vector_store,
    search_documents
)
from src.ingestion.document_loader import load_documents
from src.rag.chunking import split_documents


load_dotenv()


# Initialize Groq LLM
def get_llm():

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY not found in .env")

    llm = ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0
    )

    return llm


# Generate answer using retrieved documents
def generate_answer(question, vector_store):

    llm = get_llm()

    retrieved_docs = search_documents(
        vector_store,
        question
    )

    context = "\n\n".join(
        doc.page_content for doc in retrieved_docs
    )

    sources = list({
        doc.metadata.get("source", "Unknown")
        for doc in retrieved_docs
    })

    prompt = ChatPromptTemplate.from_template("""
You are an IT support assistant.

Answer the employee's question using ONLY the
provided troubleshooting context.

Rules:
1. Do not invent troubleshooting steps.
2. If the answer is not available in the context,
   clearly say that IT support must investigate.
3. Give simple and clear instructions.
4. Never ask the employee to share their password.

Context:
{context}

Employee Question:
{question}

Answer:
""")

    chain = prompt | llm | StrOutputParser()

    answer = chain.invoke({
        "context": context,
        "question": question
    })

    return {
        "answer": answer,
        "sources": sources
    }


if __name__ == "__main__":

    documents = load_documents()

    chunks = split_documents(documents)

    vector_store = create_vector_store(chunks)

    question = "My VPN authentication is failing. What should I do?"

    result = generate_answer(
        question,
        vector_store
    )

    print("\nEmployee Question:")
    print(question)

    print("\nAI Support Answer:")
    print(result["answer"])

    print("\nSources:")
    for source in result["sources"]:
        print(source)
