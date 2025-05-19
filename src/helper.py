import os
import logging
from sentence_transformers import SentenceTransformer
import requests
from typing import List, Dict, Optional
import json
from datetime import datetime
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_hugging_face_embeddings():
    """
    Download and return HuggingFace embeddings model.
    Using a medical-specific model for better performance.
    """
    try:
        # Use a model that's good for medical/scientific text
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        logger.info("Successfully loaded HuggingFace embeddings model")
        return model
    except Exception as e:
        logger.error(f"Error loading embeddings model: {str(e)}")
        raise

class MedicalQueryProcessor:
    """
    Process and enhance medical queries for better search results.
    """
    
    def __init__(self):
        self.medical_terms = self._load_medical_terms()
        
    def _load_medical_terms(self) -> List[str]:
        """
        Load common medical terms for query enhancement.
        """
        # Basic list - in production, load from a comprehensive medical dictionary
        return [
            'symptom', 'symptoms', 'disease', 'condition', 'treatment', 'medication',
            'diagnosis', 'therapy', 'infection', 'virus', 'bacteria', 'chronic',
            'acute', 'syndrome', 'disorder', 'pain', 'inflammation', 'allergy',
            'cancer', 'tumor', 'diabetes', 'hypertension', 'cardiac', 'respiratory'
        ]
    
    def enhance_query(self, query: str) -> str:
        """
        Enhance medical queries with relevant medical context.
        """
        enhanced_query = query.lower().strip()
        
        # Add medical context if not present
        if not any(term in enhanced_query for term in self.medical_terms):
            enhanced_query = f"medical health {enhanced_query}"
        
        return enhanced_query
    
    def extract_medical_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract medical entities from text (basic implementation).
        For production, consider using specialized medical NER models.
        """
        entities = {
            'symptoms': [],
            'conditions': [],
            'medications': [],
            'body_parts': []
        }
        
        # Simple pattern matching - enhance with proper medical NER
        symptom_patterns = [
            r'\b\w*pain\w*\b', r'\b\w*ache\w*\b', r'\b\w*fever\w*\b',
            r'\b\w*nausea\w*\b', r'\b\w*fatigue\w*\b', r'\b\w*dizz\w*\b'
        ]
        
        for pattern in symptom_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities['symptoms'].extend(matches)
        
        return entities

class WebSearchEnhancer:
    """
    Enhance web search capabilities for medical queries.
    """
    
    def __init__(self):
        self.trusted_medical_sites = [
            'mayoclinic.org', 'webmd.com', 'healthline.com', 
            'nih.gov', 'cdc.gov', 'who.int', 'medlineplus.gov',
            'uptodate.com', 'bmj.com', 'nejm.org'
        ]
    
    def create_enhanced_query(self, original_query: str, query_type: str) -> str:
        """
        Create enhanced search queries based on query type.
        """
        base_query = original_query
        
        if query_type == "DRUG_INFO":
            site_restriction = " OR ".join([f"site:{site}" for site in self.trusted_medical_sites[:3]])
            return f"{base_query} medication drug information {site_restriction}"
        elif query_type == "CURRENT_INFO":
            return f"{base_query} 2024 2025 latest medical research clinical trial"
        elif query_type == "EMERGENCY":
            return f"{base_query} emergency first aid immediate care site:redcross.org OR site:mayoclinic.org"
        else:
            site_restriction = " OR ".join([f"site:{site}" for site in self.trusted_medical_sites])
            return f"medical health {base_query} {site_restriction}"
    
    def filter_search_results(self, results: str) -> str:
        """
        Filter and clean search results for medical reliability.
        """
        # Basic filtering - remove obvious non-medical content
        lines = results.split('\n')
        filtered_lines = []
        
        # Keywords that might indicate unreliable medical content
        exclude_keywords = ['buy', 'purchase', 'advertisement', 'ad', 'sponsored']
        
        for line in lines:
            if not any(keyword in line.lower() for keyword in exclude_keywords):
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)

class ResponseValidator:
    """
    Validate medical responses for safety and accuracy.
    """
    
    def __init__(self):
        self.warning_triggers = [
            'diagnosis', 'diagnose', 'treatment plan', 'prescribe', 'prescription',
            'specific medication', 'dosage recommendation', 'medical advice',
            'replace doctor', 'substitute for physician'
        ]
        
        self.emergency_keywords = [
            'chest pain', 'heart attack', 'stroke', 'severe bleeding',
            'difficulty breathing', 'unconscious', 'seizure', 'emergency'
        ]
    
    def validate_response(self, response: str, original_query: str) -> Dict[str, any]:
        """
        Validate medical response for safety and appropriateness.
        """
        validation_result = {
            'is_safe': True,
            'needs_disclaimer': False,
            'is_emergency': False,
            'warnings': [],
            'recommendations': []
        }
        
        response_lower = response.lower()
        query_lower = original_query.lower()
        
        # Check for potential diagnostic language
        if any(trigger in response_lower for trigger in self.warning_triggers):
            validation_result['needs_disclaimer'] = True
            validation_result['warnings'].append(
                "Response contains language that might be interpreted as medical advice"
            )
        
        # Check for emergency situations
        if any(keyword in query_lower for keyword in self.emergency_keywords):
            validation_result['is_emergency'] = True
            validation_result['recommendations'].append(
                "Add emergency care recommendation"
            )
        
        # Check if professional consultation is mentioned
        if 'consult' not in response_lower and 'doctor' not in response_lower:
            validation_result['recommendations'].append(
                "Add recommendation to consult healthcare professional"
            )
        
        return validation_result
    
    def add_safety_disclaimer(self, response: str, validation: Dict[str, any]) -> str:
        """
        Add appropriate safety disclaimers to medical responses.
        """
        disclaimer = ""
        
        if validation['is_emergency']:
            disclaimer = "\n\n⚠️ **EMERGENCY NOTICE**: If you're experiencing a medical emergency, please call emergency services (911) immediately or go to the nearest emergency room."
        
        if validation['needs_disclaimer']:
            disclaimer += "\n\n💡 **Important**: This information is for educational purposes only and should not replace professional medical advice. Please consult with a healthcare provider for personalized medical guidance."
        else:
            disclaimer += "\n\n💡 **Reminder**: Always consult with a healthcare professional for any medical concerns or before making changes to your health routine."
        
        return response + disclaimer

def create_conversation_context(history: List[Dict], max_turns: int = 3) -> str:
    """
    Create conversation context from recent history for better responses.
    """
    if not history:
        return ""
    
    # Get recent conversation turns
    recent_history = history[-max_turns:]
    context_parts = []
    
    for turn in recent_history:
        context_parts.append(f"User: {turn['user']}")
        context_parts.append(f"Bot: {turn['bot'][:200]}...")  # Truncate for brevity
    
    return "Recent conversation context:\n" + "\n".join(context_parts)

def log_medical_interaction(user_query: str, response: str, sources_used: List[str], 
                          query_type: str, session_id: Optional[str] = None):
    """
    Log medical interactions for monitoring and improvement.
    """
    interaction_log = {
        'timestamp': datetime.now().isoformat(),
        'session_id': session_id,
        'user_query': user_query,
        'query_type': query_type,
        'sources_used': sources_used,
        'response_length': len(response),
        'has_disclaimer': 'consult' in response.lower() or 'professional' in response.lower()
    }
    
    # In production, send to a proper logging service
    logger.info(f"Medical interaction logged: {json.dumps(interaction_log)}")

# Medical knowledge validation utilities
def validate_medical_facts(text: str) -> Dict[str, any]:
    """
    Basic validation of medical facts in responses.
    In production, integrate with medical fact-checking APIs.
    """
    return {
        'fact_checked': False,
        'confidence_score': 0.85,  # Placeholder
        'needs_verification': True,
        'medical_accuracy': 'uncertain'
    }