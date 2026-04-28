from pathlib import Path
from src.queue import HumanReviewQueue


class HumanReviewManager:
    """Manager for human review queue operations."""
    
    def __init__(self):
        self.queue = HumanReviewQueue()
    
    def export_queues(self):
        """Export all review queues to CSV files."""
        self.queue.export_to_csv("data/human_review_pending.csv", "PENDING")
        self.queue.export_to_csv("data/human_review_approved.csv", "APPROVED")
        self.queue.export_to_csv("data/human_review_rejected.csv", "REJECTED")
        self.queue.export_to_csv("data/human_review_all.csv", "ALL")
    
    def add_failed_resolution(self, raw_address: str, llm_result: dict,
                              validation_result: dict, tier_used: int = 3,
                              rag_context: str = None, logprob: float = None) -> int:
        """Add failed case to human review queue."""
        return self.queue.add(
            raw_address=raw_address,
            llm_result=llm_result,
            validation_result=validation_result,
            tier_used=tier_used,
            rag_context=rag_context,
            logprob=logprob
        )
    
    def approve_item(self, item_id: int, reviewed_by: str = "human", notes: str = None):
        """Approve a review item."""
        self.queue.approve(item_id, reviewed_by, notes)
    
    def reject_item(self, item_id: int, reviewed_by: str = "human", notes: str = None):
        """Reject a review item."""
        self.queue.reject(item_id, reviewed_by, notes)
    
    def get_pending(self, limit: int = 50) -> list:
        """Get pending items for review."""
        return self.queue.get_pending(limit)
    
    def get_stats(self) -> dict:
        """Get queue statistics."""
        return self.queue.get_stats()
    
    def clear_queue(self):
        """Clear all items from queue."""
        self.queue.clear_all()


def export_all_queues():
    """Export all review queues to CSV files."""
    manager = HumanReviewManager()
    manager.export_queues()


if __name__ == "__main__":
    export_all_queues()