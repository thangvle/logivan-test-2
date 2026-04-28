import csv
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from src.models.address import AddressResolution
from src.models.validation import ValidationResult


class HumanReviewQueue:
    """
    Human Review Queue for uncertain address resolutions.
    CSV-based storage (no SQLite dependency).
    
    Input: ValidationResult, AddressResolution, GroundTruth
    Output: CorrectedResult
    Logic: Let human compare validation result with AI-resolved address
    
    Features:
    - CSV-based queue storage
    - Easy export for human review
    - Feedback loop to Tier 1 (self-healing)
    """
    
    def __init__(self, queue_file: str = "data/human_review_queue.csv"):
        self.queue_file = Path(queue_file)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_csv()
    
    def _init_csv(self):
        """Initialize CSV file with headers if it doesn't exist."""
        if not self.queue_file.exists():
            with open(self.queue_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self._get_fieldnames())
                writer.writeheader()
    
    def _get_fieldnames(self) -> List[str]:
        """Get CSV fieldnames."""
        return [
            'id', 'raw_address', 'tier_used',
            'llm_province', 'llm_district', 'llm_ward',
            'llm_lat', 'llm_lng', 'llm_location_id',
            'validation_passed', 'failure_reason',
            'logprob', 'rag_context_used',
            'status', 'reviewed_by', 'correction_notes',
            'created_at', 'reviewed_at'
        ]
    
    def _get_next_id(self) -> int:
        """Get next available ID."""
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    return max(int(row['id']) for row in rows) + 1
                return 1
        except:
            return 1
    
    def add(self, raw_address: str, llm_result: dict, validation_result: ValidationResult,
            tier_used: int = 3, rag_context: str = None, logprob: float = None) -> int:
        """
        Add failed case to queue for human review.
        
        Args:
            raw_address: Original messy address
            llm_result: LLM resolution result
            validation_result: Validation result with checks
            tier_used: Which tier was used (1, 2, or 3)
            rag_context: RAG context used (if any)
            logprob: Token probability from LLM
        
        Returns:
            Queue item ID
        """
        item_id = self._get_next_id()
        
        row = {
            'id': item_id,
            'raw_address': raw_address,
            'tier_used': tier_used,
            'llm_province': llm_result.get('province', ''),
            'llm_district': llm_result.get('district', ''),
            'llm_ward': llm_result.get('ward', ''),
            'llm_lat': llm_result.get('lat', ''),
            'llm_lng': llm_result.get('lng', ''),
            'llm_location_id': llm_result.get('resolved_location_id', ''),
            'validation_passed': 'YES' if validation_result.passed else 'NO',
            'failure_reason': validation_result.human_review_reason or '',
            'logprob': logprob or '',
            'rag_context_used': 'YES' if rag_context else 'NO',
            'status': 'PENDING',
            'reviewed_by': '',
            'correction_notes': '',
            'created_at': datetime.now().isoformat(),
            'reviewed_at': ''
        }
        
        with open(self.queue_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self._get_fieldnames())
            writer.writerow(row)
        
        print(f"   QUEUE: Added to human review queue (ID: {item_id})")
        return item_id
    
    def get_pending(self, limit: int = 50) -> List[dict]:
        """
        Get pending items for human review.
        
        Args:
            limit: Maximum number of items to return
        
        Returns:
            List of pending review items
        """
        items = []
        
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['status'] == 'PENDING':
                        items.append(row)
                        if len(items) >= limit:
                            break
        except FileNotFoundError:
            pass
        
        return items
    
    def approve(self, item_id: int, corrected_resolution: dict,
                reviewed_by: str = "human", notes: str = None):
        """
        Approve and correct a review item.
        
        Args:
            item_id: Queue item ID
            corrected_resolution: Human-corrected address resolution
            reviewed_by: Name/ID of reviewer
            notes: Optional correction notes
        """
        self._update_status(item_id, 'APPROVED', reviewed_by, notes)
        print(f"   SUCCESS: Review item {item_id} approved")
    
    def reject(self, item_id: int, reviewed_by: str = "human", notes: str = None):
        """
        Reject a review item.
        
        Args:
            item_id: Queue item ID
            reviewed_by: Name/ID of reviewer
            notes: Optional rejection notes
        """
        self._update_status(item_id, 'REJECTED', reviewed_by, notes)
        print(f"   WARNING: Review item {item_id} rejected")
    
    def _update_status(self, item_id: int, status: str, reviewed_by: str, notes: str):
        """Update status of a queue item."""
        rows = []
        
        with open(self.queue_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row['id']) == item_id:
                    row['status'] = status
                    row['reviewed_by'] = reviewed_by
                    row['correction_notes'] = notes or ''
                    row['reviewed_at'] = datetime.now().isoformat()
                rows.append(row)
        
        with open(self.queue_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self._get_fieldnames())
            writer.writeheader()
            writer.writerows(rows)
    
    def export_to_csv(self, output_file: str = "data/human_review_export.csv",
                      status: str = "PENDING") -> str:
        """
        Export review queue to CSV for human review.
        
        Args:
            output_file: Output CSV file path
            status: Filter by status (PENDING, APPROVED, REJECTED, or ALL)
        
        Returns:
            Path to exported CSV file
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        rows = []
        
        with open(self.queue_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if status == "ALL" or row['status'] == status:
                    rows.append(row)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self._get_fieldnames())
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"   SUCCESS: Exported {len(rows)} items to {output_path}")
        return str(output_path)
    
    def get_stats(self) -> dict:
        """Get queue statistics."""
        stats = {'total': 0, 'pending': 0, 'approved': 0, 'rejected': 0}
        
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stats['total'] += 1
                    if row['status'] == 'PENDING':
                        stats['pending'] += 1
                    elif row['status'] == 'APPROVED':
                        stats['approved'] += 1
                    elif row['status'] == 'REJECTED':
                        stats['rejected'] += 1
        except FileNotFoundError:
            pass
        
        return stats

