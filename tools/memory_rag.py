from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import torch

# Global cache for the embeddings model so it doesn't reload on every scan
_embeddings = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        print("   [🧠 Initializing HuggingFace Embeddings on RTX 3050 (CUDA)...]")
        
        if not torch.cuda.is_available():
            raise RuntimeError("CRITICAL: PyTorch cannot detect the CUDA GPU! Please install the CUDA version of PyTorch.")
            
        _embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2", 
            model_kwargs={'device': 'cuda'}
        )
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
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        separators=["--- START PID", "--- END PID", "\n\n", "\n", " ", ""]
    )
    
    docs = text_splitter.split_text(raw_memory_text)
    documents = [Document(page_content=chunk) for chunk in docs]
    
    if not documents:
        return ""
        
    embeddings = get_embeddings()
    vectorstore = FAISS.from_documents(documents, embeddings)
    
    # We grab 10 dense chunks to ensure we don't miss the actual chat timeline
    retriever = vectorstore.as_retriever(search_kwargs={'k': max(k, 10)})
    
    # We explicitly bias the semantic query AWAY from static UI profiles and TOWARD actual conversational dialogue
    query = "timestamped user messages, active chat history, conversation dialogue, sent text messages, user replying"
    retrieved_docs = retriever.invoke(query)
    
    formatted_context = "\n\n... [MEMORY JUMP] ...\n\n".join([d.page_content for d in retrieved_docs])
    return formatted_context
