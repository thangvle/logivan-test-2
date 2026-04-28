from src.tier1 import Tier1Formatter
from src.tier2_cache import Tier2Cache
from src.validator import Validator
from src.rag_service import RAGService
from src.llm_service import LLMService
from src.models.address import AddressResolution
from typing import Optional


class Orchestrator:
    """
    Central coordinator implementing the Orchestration Pattern.
    Routes address resolution requests through Tier 1 → Tier 2 → Tier 3.
    """
    
    def __init__(self):
        self.tier1 = Tier1Formatter()
        self.tier2 = Tier2Cache()
        self.validator = Validator()
        self.rag = RAGService()
        self.tier3 = LLMService()
    
    def resolve(self, messy_address: str) -> dict:
        """Main entry point. Executes the tiered resolution flow."""
        print(f"\nPROCESSING: Orchestrator resolving: {messy_address[:50]}...")
        
        # TIER 1: Programmatic Normalization
        tier1_result = self.tier1.process(messy_address)
        accuracy = tier1_result.get("accuracy", 0)
        
        print(f"   Accuracy: {accuracy:.0%}")
        
        if accuracy >= 0.8 and tier1_result["status"] == "TIER1_SUCCESS":
            print(f"   SUCCESS: Tier 1 Success (0 token cost)")
            return {
                "status": "RESOLVED",
                "source": "TIER1_PROGRAMMATIC",
                "tier_used": 1,
                "token_cost": 0,
                "accuracy": accuracy,
                "input": messy_address,
                "output": tier1_result["output"],
                "components": tier1_result["components"]
            }
        
        print(f"   WARNING: Tier 1 accuracy too low ({accuracy:.0%})")
        
        # TIER 2: Semantic Cache
        print(f"   CHECKING: Checking Tier 2 cache...")
        tier2_result = self.tier2.get(messy_address)
        
        if tier2_result:
            print(f"   SUCCESS: Tier 2 Cache Hit")
            return {
                "status": "RESOLVED",
                "source": "TIER2_CACHE",
                "tier_used": 2,
                "token_cost": 0,
                "accuracy": 0.9,
                "input": messy_address,
                "output": tier2_result
            }
        
        print(f"   MISS: Tier 2 Cache Miss")
        print(f"   MAPS: Checking Google Maps API...")
        
        validation_result = self.validator.validate_coordinates(tier1_result["output"])
        
        if validation_result.get('passed'):
            print(f"   SUCCESS: Google Maps validation passed")
            return {
                "status": "RESOLVED",
                "source": "GOOGLE_MAPS_VALIDATED",
                "tier_used": 1,
                "token_cost": 0,
                "accuracy": accuracy,
                "validation": validation_result,
                "input": messy_address,
                "output": tier1_result["output"]
            }
        
        print(f"   WARNING: Google Maps validation failed")
        
        # RAG: Retrieve geographic context
        print(f"   RAG: Retrieving RAG context...")
        rag_context = self.rag.get_context(messy_address)
        
        if rag_context:
            print(f"   SUCCESS: RAG context retrieved")
        else:
            print(f"   WARNING: No RAG context found")
        
        # TIER 3: LLM inference
        print(f"   LLM: Calling LLM Service...")
        
        llm_result, logprob = self.tier3.resolve_address(messy_address, rag_context)
        
        if llm_result and llm_result.get('status') == 'RESOLVED':
            print(f"   SUCCESS: LLM resolution received")
            
            resolution = AddressResolution(
                resolved_location_id=llm_result.get('resolved_location_id'),
                lat=llm_result.get('lat'),
                lng=llm_result.get('lng'),
                province=llm_result.get('province'),
                district=llm_result.get('district'),
                ward=llm_result.get('ward'),
                confidence="HIGH",
                source="TIER3_LLM"
            )
            
            validation = self.validator.validate(resolution, logprob=logprob)
            
            if validation.passed:
                print(f"   SUCCESS: Validation passed. Promoting to Tier 1...")
                self.promote_to_tier1(messy_address, llm_result)
                return {
                    "status": "RESOLVED_LLM",
                    "source": "TIER3_LLM_VALIDATED",
                    "tier_used": 3,
                    "token_cost": "FULL",
                    "logprob": logprob,
                    "input": messy_address,
                    "output": llm_result,
                    "rag_context": rag_context
                }
            else:
                print(f"   WARNING: Validation failed. Routing to Human Queue...")
                
                return {
                    "status": "NEED_HUMAN_REVIEW",
                    "source": "TIER3_LLM_FAILED",
                    "tier_used": 3,
                    "token_cost": "FULL",
                    "input": messy_address,
                    "output": llm_result,
                    "validation_reason": validation.human_review_reason
                }
        
        print(f"   ERROR: LLM resolution failed")
        return {
            "status": "LLM_FAILED",
            "source": "TIER3_LLM",
            "tier_used": 3,
            "token_cost": "FULL",
            "input": messy_address,
            "output": None,
            "rag_context": rag_context
        }
    
    def promote_to_tier1(self, messy_address: str, resolution: dict):
        """Self-healing: Promote successful LLM result to Tier 1."""
        print(f"   PROCESSING: Self-healing: Promoting to Tier 1")
        self.tier2.put(messy_address, AddressResolution(
            resolved_location_id=resolution.get('resolved_location_id'),
            lat=resolution.get('lat'),
            lng=resolution.get('lng'),
            province=resolution.get('province'),
            district=resolution.get('district'),
            ward=resolution.get('ward'),
            confidence="HIGH",
            source="TIER3_PROMOTED"
        ))
