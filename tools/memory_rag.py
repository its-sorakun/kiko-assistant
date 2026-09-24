from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# Global cache for the embeddings model so it doesn't reload on every scan
_embeddings = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        print("   [🧠 Initializing HuggingFace Embeddings for Memory RAG...]")
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings

def semantic_memory_filter(raw_memory_text: str, k: int = 7) -> str:
    """
    Takes a massive raw memory dump, chunks it, and uses FAISS to extract the most relevant snippets.
    This prevents the LLM context window from being overwhelmed by V8 Javascript garbage.
    """
    if not raw_memory_text.strip():
        return ""
        
    print("   [🧠 Kiko is processing raw memory via FAISS RAG...]")
    
    # Text splitter optimized for chaotic C++ string dumps
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
        length_function=len,
        separators=["--- START PID", "--- END PID", "\n\n", "\n", " ", ""]
    )
    
    docs = text_splitter.split_text(raw_memory_text)
    documents = [Document(page_content=chunk) for chunk in docs]
    
    if not documents:
        return ""
        
    embeddings = get_embeddings()
    vectorstore = FAISS.from_documents(documents, embeddings)
    
    retriever = vectorstore.as_retriever(search_kwargs={'k': k})
    
    # We query for the most human-readable context typical of a chat/UI application
    query = "chat logs, active conversation, recent messages, visible text content, user interface text"
    retrieved_docs = retriever.invoke(query)
    
    formatted_context = "\n\n... [MEMORY JUMP] ...\n\n".join([d.page_content for d in retrieved_docs])
    return formatted_context
