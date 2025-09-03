#!/usr/bin/env python3
"""
Simple Aiceberg API Test
-----------------------
Test the event API and then use the event_id to fetch detailed prompt analysis.
"""

import json
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def mask_pii_from_prompt_details(original_text: str, prompt_details: dict) -> str:
    """
    Extract flagged PII values from prompt details and replace them with *** in the original text.
    
    Args:
        original_text: The original prompt text
        prompt_details: The response from the prompt details API
    
    Returns:
        The text with PII values replaced by ***
    """
    masked_text = original_text
    
    # Navigate to the cards.prompt array
    cards = prompt_details.get("cards", {})
    prompt_cards = cards.get("prompt", [])
    
    # Look for pii_phi_pci category cards that are flagged
    for card in prompt_cards:
        if (card.get("category") == "pii_phi_pci" and 
            card.get("status") == "flagged"):
            
            # Extract flagged values from metadata
            metadata = card.get("metadata", {})
            flagged_values = metadata.get("flagged_values", [])
            
            # Replace each flagged value with ***
            for flagged_value in flagged_values:
                if flagged_value in masked_text:
                    masked_text = masked_text.replace(flagged_value, "***")
    
    return masked_text

def test_event_api():
    """Test the original event API and return the event_id"""
    api_key = os.getenv("AICEBERG_API_KEY", "")
    profile_id = os.getenv("AICEBERG_PROFILE_ID", "") 
    api_url = os.getenv("AICEBERG_API_URL", "https://test.api.aiceberg.ai/eap/v0/event")
    
    if not api_key or not profile_id:
        print("⚠️  Missing AICEBERG_API_KEY or AICEBERG_PROFILE_ID in .env file")
        return None, None
    
    # Simple test payload with PII
    payload = {
        "profile_id": profile_id,
        "event_type": "user_agt",
        "input": "Hey! Here's my social security SSN number: 734-745-8732",
        "forward_to_llm": False,
        "metadata": {
            "source": "test_script"
        }
    }
    
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print("Event API Response:")
            print(json.dumps(result, indent=2))
            return result.get("event_id"), payload["input"]
        else:
            print(f"Error: {response.text}")
            return None, None
            
    except Exception as e:
        print(f"Failed: {e}")
        return None, None

def fetch_prompt_details(event_id: str):
    """Fetch detailed prompt analysis using the event_id as prompt_id"""
    api_token = os.getenv("AICEBERG_API_KEY", "")
    url = f"https://test.api.aiceberg.ai/ogma_agent/v2/prompt/{event_id}"
    
    headers = {
        "Authorization": api_token,
        "Accept": "application/json"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            print("\nPrompt Details Response:")
            print(json.dumps(data, indent=2))
            return data
        else:
            print(f"Error: {resp.text}")
            return None
            
    except Exception as e:
        print(f"Failed: {e}")
        return None

if __name__ == "__main__":
    # Step 1: Test event API and get event_id
    # event_id, original_text = test_event_api()
    event_id = "01JVZ483JD138PK48T2FYQ32V8"
    original_text = "Hello"
    # Step 2: Use event_id to fetch detailed prompt analysis
    if event_id and original_text:
        prompt_details = fetch_prompt_details(event_id)
        
        if prompt_details:
            # Step 3: Mask PII in the original text
            masked_text = mask_pii_from_prompt_details(original_text, prompt_details)
            
            print(f"\n--- PII MASKING DEMO ---")
            print(f"Original: {original_text}")
            print(f"Masked:   {masked_text}")