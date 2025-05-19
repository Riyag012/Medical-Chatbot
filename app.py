from flask import Flask, render_template, jsonify, request
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import DuckDuckGoSearchRun
from dotenv import load_dotenv
from src.prompt import *
import os

app = Flask(__name__)
load_dotenv()

PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Initialize embeddings and vector store
embeddings = download_hugging_face_embeddings()
index_name = "medicalbot"

docsearch = PineconeVectorStore.from_existing_index(
    index_name=index_name,
    embedding=embeddings
)
retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 3})

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17",
    temperature=0.3,
    max_output_tokens=800
)

# Initialize web search
search = DuckDuckGoSearchRun()

class SimpleMedicalAgent:
    def __init__(self, retriever, llm, search_tool):
        self.retriever = retriever
        self.llm = llm
        self.search = search_tool
        
    def classify_query(self, query):
        """Simple query classification"""
        query_lower = query.lower()
        
        # Check for emergency keywords
        emergency_words = ['emergency', 'heart attack', 'stroke', 'severe pain', 'can\'t breathe', 'unconscious']
        if any(word in query_lower for word in emergency_words):
            return 'EMERGENCY'
        
        # Check for drug/medication queries
        drug_words = ['medication', 'drug', 'pill', 'prescription', 'side effect', 'dosage']
        if any(word in query_lower for word in drug_words):
            return 'DRUG_INFO'
        
        # Check for recent/current info needs
        current_words = ['latest', 'recent', 'new', '2024', '2025', 'current']
        if any(word in query_lower for word in current_words):
            return 'CURRENT_INFO'
        
        return 'GENERAL'
    
    def search_knowledge_base(self, query):
        """Search the existing medical knowledge base"""
        try:
            docs = self.retriever.get_relevant_documents(query)
            if docs:
                return "\n\n".join([doc.page_content for doc in docs])
            return ""
        except Exception as e:
            print(f"Error searching knowledge base: {e}")
            return ""
    
    def search_web(self, query):
        """Search the web for medical information"""
        try:
            # Enhance query with medical terms and trusted sites
            enhanced_query = f"medical {query} site:mayoclinic.org OR site:webmd.com OR site:healthline.com"
            results = self.search.run(enhanced_query)
            return results
        except Exception as e:
            print(f"Error in web search: {e}")
            return ""
    
    def generate_response(self, user_query):
        """Generate response using both knowledge base and web search"""
        query_type = self.classify_query(user_query)
        
        # Get information from both sources
        kb_info = self.search_knowledge_base(user_query)
        web_info = ""
        
        # Use web search for certain query types or when knowledge base has limited info
        if query_type in ['DRUG_INFO', 'CURRENT_INFO'] or len(kb_info) < 200:
            web_info = self.search_web(user_query)
        
        # Create comprehensive prompt
        if query_type == 'EMERGENCY':
            system_msg = emergency_prompt
        elif query_type == 'DRUG_INFO':
            system_msg = drug_info_prompt
        else:
            system_msg = system_prompt
        
        # Combine information sources
        context = ""
        if kb_info:
            context += f"Medical Knowledge Base Information:\n{kb_info}\n\n"
        if web_info:
            context += f"Recent Medical Information:\n{web_info}\n\n"
        
        # Create the prompt
        final_prompt = f"""
        {system_msg}
        
        Context Information:
        {context}
        
        User Question: {user_query}
        
        Please provide a comprehensive, accurate, and helpful response based on the available information. 
        Always include appropriate medical disclaimers and encourage professional consultation when needed.
        """
        
        try:
            response = self.llm.invoke(final_prompt)
            return self.add_disclaimers(response.content, query_type)
        except Exception as e:
            return f"I apologize, but I encountered an error processing your question. Please try again or consult a healthcare professional. Error: {str(e)}"
    
    def add_disclaimers(self, response, query_type):
        """Add appropriate medical disclaimers"""
        if query_type == 'EMERGENCY':
            disclaimer = "\n\n🚨 EMERGENCY: If this is a medical emergency, please call 911 or go to the nearest emergency room immediately."
        else:
            disclaimer = "\n\n💡 Important: This information is for educational purposes only. Always consult with a healthcare professional for medical advice, diagnosis, or treatment."
        
        return response + disclaimer

# Initialize the agent
medical_agent = SimpleMedicalAgent(retriever, llm, search)

@app.route("/")
def index():
    return render_template('chat.html')

@app.route("/get", methods=["GET", "POST"])
def chat():
    msg = request.form.get("msg", "")
    if not msg:
        return "Please provide a message"
    
    print(f"User input: {msg}")
    
    # Get response from the medical agent
    response = medical_agent.generate_response(msg)
    
    print(f"Bot response: {response}")
    
    # Return simple string response (fixing the [object Object] issue)
    return str(response)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)