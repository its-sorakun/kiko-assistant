# Copyright (C) 2026 Senpai
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import os
from typing import TypedDict, List
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.graph import StateGraph, START, END

# We will cache the vector store in memory so we don't re-embed the same PDF if queried multiple times in a row
_vector_store_cache = {}

class GraphState(TypedDict):
    """
    Represents the state of our graph.
    """
    file_path: str
    query: str
    documents: List[str]
    formatted_context: str

def get_or_create_vectorstore(file_path: str):
    global _vector_store_cache
    if file_path in _vector_store_cache:
        return _vector_store_cache[file_path]
        
    print(f"   [⚡ Kiko is reading and chunking the PDF: {os.path.basename(file_path)}...]")
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(docs)
    
    print("   [⚡ Kiko is generating HuggingFace embeddings on CPU...]")
    # Using all-MiniLM-L6-v2 as it is incredibly fast and highly ranked for retrieval on CPU
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    vectorstore = FAISS.from_documents(documents=splits, embedding=embeddings)
    _vector_store_cache[file_path] = vectorstore
    return vectorstore

def retrieve(state: GraphState):
    """
    Retrieve documents using FAISS
    """
    print("   [⚡ Kiko is retrieving relevant chunks via FAISS LangGraph Node...]")
    file_path = state["file_path"]
    query = state["query"]
    
    vectorstore = get_or_create_vectorstore(file_path)
    # k=5 pulls a good amount of context without overloading Gemini's prompt
    retriever = vectorstore.as_retriever(search_kwargs={'k': 5})
    
    docs = retriever.invoke(query)
    doc_texts = [d.page_content for d in docs]
    return {"documents": doc_texts}

def format_context(state: GraphState):
    """
    Format retrieved documents into a string
    """
    docs = state["documents"]
    formatted = "\n\n---\n\n".join(docs)
    return {"formatted_context": formatted}

# --- Compile the LangGraph Application ---
workflow = StateGraph(GraphState)
workflow.add_node("retrieve", retrieve)
workflow.add_node("format_context", format_context)
workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "format_context")
workflow.add_edge("format_context", END)
pdf_app = workflow.compile()


def advanced_pdf_query(file_path: str, query: str) -> str:
    """
    Read and query a PDF file using advanced RAG and LangGraph.
    Use this when asked to extract info from a PDF, summarize it, or answer questions based on it.
    You can use '~' to represent the user's home directory.
    """
    file_path = os.path.expanduser(file_path)
    if not os.path.exists(file_path):
        return f"CRITICAL ERROR: PDF file not found at {file_path}"
        
    inputs = {"file_path": file_path, "query": query}
    try:
        # Run the LangGraph application
        output = pdf_app.invoke(inputs)
        context = output["formatted_context"]
        return f"Extracted relevant context from {os.path.basename(file_path)}:\n\n{context}\n\n[INSTRUCTION TO KIKO: Use the above context to answer the user's question '{query}'. Do not mention that you used a tool, just answer naturally.]"
    except Exception as e:
        return f"Error querying PDF: {str(e)}"
