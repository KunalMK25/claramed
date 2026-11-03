import os
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

def get_symptom_chain():
    # Initialize the Groq LLM with the replacement model
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.2,
        max_tokens=1024,
    )
    
    # Create the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful, professional medical assistant. A user will describe their symptoms. "
                   "Provide a clear, educational explanation of what these symptoms might indicate, "
                   "possible common causes, and general advice. "
                   "Always maintain a reassuring tone. "
                   "CRITICAL: Always state that you are an AI and this is for educational purposes, and advise them to see a doctor for a proper diagnosis. "
                   "Always respond in {language}"),
        ("human", "My symptoms are: {symptoms}")
    ])
    
    # Create the chain connecting prompt to the language model to string output
    chain = prompt | llm | StrOutputParser()
    
    return chain

def get_emergency_chain():
    # Initialize the Groq LLM for classification using the replacement model
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.0,
        max_tokens=10,
    )
    
    # Create the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Based on this symptom, is this a medical emergency? Reply with only YES or NO. "
                   "Always respond in {language}"),
        ("human", "{symptoms}")
    ])
    
    # Create the chain
    chain = prompt | llm | StrOutputParser()
    
    return chain

def get_report_explainer_chain():
    # Initialize the Groq LLM for explanation
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.2,
        max_tokens=2048,
    )
    
    # Create the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert medical communicator. Your task is to take a medical report or lab results and explain it in simple, plain English that a layperson can easily understand. "
                   "Break down medical terms, explain what the values mean, and highlight any important findings. "
                   "Always maintain a supportive and reassuring tone. "
                   "CRITICAL: Always state that you are an AI and this explanation is for educational purposes only. Recommend they discuss the findings with their doctor. "
                   "Always respond in {language}"),
        ("human", "Here is the medical report text:\n\n{report_text}")
    ])
    
    # Create the chain
    chain = prompt | llm | StrOutputParser()
    
    return chain

def get_wellness_tips_chain():
    # Initialize the Groq LLM for wellness tips
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.3,
        max_tokens=1024,
    )
    
    # Create the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a friendly wellness and nutrition assistant. The user has described their symptoms. "
                   "Based on their symptoms, provide 3 simple and practical diet suggestions (e.g., foods/fluids to prioritize or avoid) "
                   "and 3 lifestyle tips (e.g., rest, environmental adjustments) that can help them feel more comfortable. "
                   "Format your response under separate '### 🥗 Diet Suggestions' and '### 🚶 Lifestyle Tips' sections using clean bullet points. "
                   "Keep the tone extremely warm, supportive, simple, and strictly non-prescriptive. "
                   "Always respond in {language}"),
        ("human", "My symptoms are: {symptoms}")
    ])
    
    # Create the chain
    chain = prompt | llm | StrOutputParser()
    
    return chain
