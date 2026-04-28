import json
import os
from pathlib import Path
from typing import List, Optional

# Try to import LlamaIndex (requires Python 3.10+)
LLAMAINDEX_AVAILABLE = False
try:
    from llama_index.core import VectorStoreIndex, Document, Settings
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    LLAMAINDEX_AVAILABLE = True
except (ImportError, TypeError) as e:
    # TypeError occurs on Python 3.9 due to | union syntax
    pass


class RAGService:
    """
    RAG (Retrieval-Augmented Generation) Service using LlamaIndex.
    
    Provides updated geographic context to LLM when local APIs fail.
    
    Input: raw_address (str)
    Output: context_string (str) - formatted geographic updates
    Logic: Vector search using LlamaIndex with HuggingFace embeddings
    
    Features:
    - Uses LlamaIndex for vector search
    - HuggingFace embeddings (multilingual support)
    - Stores official Vietnamese administrative boundary updates
    - Handles outdated API/Geography edge cases
    """
    
    def __init__(self, 
                 updates_file: str = "data/geographic_updates.json",
                 human_corrections_file: str = "data/human_corrections.json"):
        self.updates_file = Path(updates_file)
        self.human_corrections_file = Path(human_corrections_file)
        
        # Load geographic updates
        self.updates = self._load_updates()
        self.human_corrections = self._load_human_corrections()
        
        # Initialize LlamaIndex
        self.index = None
        if LLAMAINDEX_AVAILABLE:
            self._init_llamaindex()
        else:
            print("   WARNING: Using fallback keyword matching (install llama-index for better results)")
    
    def _init_llamaindex(self):
        """Initialize LlamaIndex with HuggingFace embeddings."""
        try:
            # Configure embeddings
            embed_model = HuggingFaceEmbedding(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            
            # Create documents from updates
            documents = []
            for update in self.updates:
                text = f"{update['description']} Province: {update['province']}. "
                text += f"Effective date: {update['effective_date']}. "
                text += f"Type: {update['type']}."
                
                doc = Document(
                    text=text,
                    metadata={
                        'id': update['id'],
                        'province': update['province'],
                        'type': update['type'],
                        'effective_date': update['effective_date']
                    }
                )
                documents.append(doc)
            
            # Create vector index with custom embed model
            if documents:
                self.index = VectorStoreIndex.from_documents(
                    documents,
                    embed_model=embed_model
                )
                print("   SUCCESS: LlamaIndex initialized with vector embeddings")
            
        except Exception as e:
            print(f"   WARNING: LlamaIndex initialization failed: {e}")
            self.index = None
    
    def _load_updates(self) -> List[dict]:
        """Load official geographic boundary updates."""
        if not self.updates_file.exists():
            # Create default updates file
            self.updates_file.parent.mkdir(parents=True, exist_ok=True)
            default_updates = {
                "version": "1.0",
                "last_updated": "2026-04-28",
                "updates": [
                    {
                        "id": "VN-HCM-2024-001",
                        "effective_date": "2024-01-15",
                        "province": "Hồ Chí Minh",
                        "type": "WARD_MERGE",
                        "description": "Phường Tân Định merged into Phường Đa Kao, Quận 1",
                        "old_location": {"ward": "Tân Định", "district": "Quận 1"},
                        "new_location": {"ward": "Đa Kao", "district": "Quận 1"}
                    },
                    {
                        "id": "VN-HCM-2025-001",
                        "effective_date": "2025-06-01",
                        "province": "Hồ Chí Minh",
                        "type": "DISTRICT_RENAME",
                        "description": "Quận 2, Quận 9, Thủ Đức merged into Thành phố Thủ Đức",
                        "old_location": {"district": "Quận 2"},
                        "new_location": {"district": "Thành phố Thủ Đức"}
                    },
                    {
                        "id": "VN-DL-2024-001",
                        "effective_date": "2024-03-20",
                        "province": "Lâm Đồng",
                        "type": "WARD_UPDATE",
                        "description": "Phường 8 administrative boundary updated in Đà Lạt",
                        "location": {"ward": "Phường 8", "district": "Đà Lạt"}
                    }
                ]
            }
            with open(self.updates_file, 'w', encoding='utf-8') as f:
                json.dump(default_updates, f, ensure_ascii=False, indent=2)
            
            return default_updates['updates']
        
        with open(self.updates_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('updates', [])
    
    def _load_human_corrections(self) -> List[dict]:
        """Load human-corrected addresses for context."""
        if not self.human_corrections_file.exists():
            return []
        
        with open(self.human_corrections_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('corrections', [])
    
    def retrieve(self, raw_address: str, top_k: int = 3) -> List[dict]:
        """
        Retrieve relevant geographic updates using LlamaIndex.
        
        Args:
            raw_address: Raw address string
            top_k: Number of top results to return
        
        Returns:
            List of relevant geographic updates
        """
        if self.index and LLAMAINDEX_AVAILABLE:
            # Use LlamaIndex vector search
            try:
                query_engine = self.index.as_query_engine(similarity_top_k=top_k)
                response = query_engine.query(raw_address)
                
                # Extract relevant updates from response
                relevant_updates = []
                for node in response.source_nodes:
                    update_id = node.metadata.get('id')
                    # Find full update by ID
                    for update in self.updates:
                        if update['id'] == update_id:
                            relevant_updates.append(update)
                            break
                
                return relevant_updates
            except Exception as e:
                print(f"   WARNING: LlamaIndex query failed: {e}")
                return self._fallback_retrieve(raw_address, top_k)
        else:
            # Fallback to keyword matching
            return self._fallback_retrieve(raw_address, top_k)
    
    def _fallback_retrieve(self, raw_address: str, top_k: int) -> List[dict]:
        """Fallback keyword-based matching."""
        relevant_updates = []
        address_lower = raw_address.lower()
        
        for update in self.updates:
            score = 0
            province = update.get('province', '').lower()
            if province and province in address_lower:
                score += 3
            
            old_loc = update.get('old_location', {})
            new_loc = update.get('new_location', {})
            
            if old_loc.get('district', '').lower() in address_lower:
                score += 2
            if old_loc.get('ward', '').lower() in address_lower:
                score += 2
            
            if score > 0:
                relevant_updates.append({'update': update, 'score': score})
        
        relevant_updates.sort(key=lambda x: x['score'], reverse=True)
        return [item['update'] for item in relevant_updates[:top_k]]
    
    def build_context(self, updates: List[dict]) -> str:
        """
        Format retrieved updates into context string for LLM prompt.
        
        Args:
            updates: List of geographic updates
        
        Returns:
            Formatted context string
        """
        if not updates:
            return ""
        
        context_parts = ["[Official Geographic Updates]"]
        
        for update in updates:
            update_id = update.get('id', 'N/A')
            effective_date = update.get('effective_date', 'N/A')
            description = update.get('description', 'N/A')
            
            context_parts.append(
                f"- [{update_id}] Effective {effective_date}: {description}"
            )
        
        context_parts.append("\nUse these official updates to resolve the address correctly.")
        
        return "\n".join(context_parts)
    
    def get_context(self, raw_address: str) -> str:
        """
        Main entry point: Retrieve and format context for LLM.
        
        Args:
            raw_address: Raw address string
        
        Returns:
            Formatted context string ready for LLM prompt injection
        """
        updates = self.retrieve(raw_address, top_k=3)
        context = self.build_context(updates)
        return context
    
    def add_human_correction(self, raw_address: str, corrected_address: str, 
                            reason: str):
        """
        Add human correction to the knowledge base.
        
        Args:
            raw_address: Original messy address
            corrected_address: Human-corrected address
            reason: Reason for correction
        """
        correction = {
            "raw_address": raw_address,
            "corrected_address": corrected_address,
            "reason": reason,
            "timestamp": "2026-04-28"
        }
        
        self.human_corrections.append(correction)
        
        self.human_corrections_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.human_corrections_file, 'w', encoding='utf-8') as f:
            json.dump({
                "corrections": self.human_corrections
            }, f, ensure_ascii=False, indent=2)
