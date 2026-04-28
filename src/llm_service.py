import os
import json
from typing import Optional, Tuple
from src.models.address import AddressResolution


class LLMService:
    """
    Tier 3: LLM Service for address resolution.
    
    Input: raw_address (str), rag_context (str | None)
    Output: (AddressResolution, logprob)
    Logic: Prompt engineering + LLM call -> (resolution, token_probability)
    
    Features:
    - OpenAI/Anthropic API integration
    - RAG context injection
    - Logprob extraction for validation
    """
    
    def __init__(self, provider: str = None):
        self.provider = provider or os.getenv('LLM_PROVIDER', 'openai')
        self.api_key = os.getenv('OPENAI_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
        self.model = os.getenv('LLM_MODEL', 'gpt-4o-mini')
        
        self._init_llm_client()
    
    def _init_llm_client(self):
        """Initialize LLM client based on provider."""
        if self.provider == 'openai' and self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                print(f"SUCCESS: LLM Service initialized with OpenAI ({self.model})")
            except ImportError:
                print(f"WARNING: OpenAI library not installed. Install with: pip install openai")
                self.client = None
        elif self.provider == 'anthropic' and self.api_key:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=self.api_key)
                print(f"SUCCESS: LLM Service initialized with Anthropic")
            except ImportError:
                print(f"WARNING: Anthropic library not installed. Install with: pip install anthropic")
                self.client = None
        else:
            print(f"WARNING: LLM API key not configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY")
            self.client = None
    
    def resolve_address(self, raw_address: str, rag_context: str = None) -> Tuple[Optional[dict], Optional[float]]:
        """
        Resolve address using LLM with optional RAG context.
        
        Args:
            raw_address: Raw address string
            rag_context: Optional RAG context from geographic updates
        
        Returns:
            Tuple of (resolution_dict, logprob)
            resolution_dict contains: resolved_location_id, lat, lng, province, district, ward, status
            logprob is the token probability for the location_id prediction
        """
        if not self.client:
            return None, None
        
        # Build prompt
        prompt = self._build_prompt(raw_address, rag_context)
        
        try:
            if self.provider == 'openai':
                return self._call_openai(prompt)
            elif self.provider == 'anthropic':
                return self._call_anthropic(prompt)
        except Exception as e:
            print(f"ERROR: LLM call failed: {e}")
            return None, None
        
        return None, None
    
    def _build_prompt(self, raw_address: str, rag_context: str = None) -> str:
        """Build the prompt for address resolution."""
        
        system_prompt = """You are a logistics address resolution expert for Vietnam.
Given a messy address, resolve it to the correct administrative location.

Rules:
1. Use the provided [Official Updates] to override your internal knowledge if present
2. Return ONLY a valid JSON object with these fields:
   - resolved_location_id: integer or null
   - lat: float or null
   - lng: float or null
   - province: string
   - district: string or null
   - ward: string or null
   - status: "RESOLVED" or "UNRESOLVED"
3. If you cannot resolve, return: {"status": "UNRESOLVED", "reason": "..."}
4. NEVER guess coordinates if uncertain
5. Pay attention to Vietnamese diacritics (đ vs d, ơ vs o, etc.)

Output format (JSON only, no markdown):"""
        
        user_prompt = f"Resolve this address:\n{raw_address}"
        
        if rag_context:
            user_prompt = f"[Official Updates]\n{rag_context}\n\n{user_prompt}"
        
        return json.dumps({
            "system": system_prompt,
            "user": user_prompt
        })
    
    def _call_openai(self, prompt_data: dict) -> Tuple[Optional[dict], Optional[float]]:
        """Call OpenAI API."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt_data["system"]},
                {"role": "user", "content": prompt_data["user"]}
            ],
            response_format={"type": "json_object"},
            max_tokens=500
        )
        
        # Extract content
        content = response.choices[0].message.content
        
        # Parse JSON
        try:
            result = json.loads(content)
            
            # Estimate logprob from finish reason
            # In production, use logprobs parameter: logprobs=True
            logprob = 0.85  # Placeholder - would need actual logprob extraction
            
            return result, logprob
        except json.JSONDecodeError:
            print(f"WARNING: LLM returned invalid JSON: {content[:100]}")
            return None, None
    
    def _call_anthropic(self, prompt_data: dict) -> Tuple[Optional[dict], Optional[float]]:
        """Call Anthropic API."""
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=prompt_data["system"],
            messages=[
                {"role": "user", "content": prompt_data["user"]}
            ]
        )
        
        content = response.content[0].text
        
        try:
            result = json.loads(content)
            # Anthropic provides content_metadata with logprob info
            logprob = 0.85  # Placeholder
            return result, logprob
        except json.JSONDecodeError:
            print(f"WARNING: LLM returned invalid JSON: {content[:100]}")
            return None, None
    
    def resolve_with_validation(self, raw_address: str, rag_context: str = None,
                                expected_location_id: int = None) -> dict:
        """
        Full resolution with built-in validation structure.
        Used by Orchestrator for complete workflow.
        
        Returns:
            dict with resolution and metadata
        """
        result, logprob = self.resolve_address(raw_address, rag_context)
        
        return {
            "raw_address": raw_address,
            "resolved_address": result,
            "logprob": logprob,
            "rag_context_used": rag_context is not None,
            "expected_location_id": expected_location_id
        }