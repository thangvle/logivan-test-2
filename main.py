import json
import sys
from pathlib import Path

from src.orchestrator import Orchestrator
from src.human_review import HumanReviewManager, export_all_queues


def load_vat_invoices(json_file: str) -> list:
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('data', {}).get('vat_invoices', [])


def extract_addresses_from_vat(vat_invoices: list) -> list:
    addresses = []
    for invoice in vat_invoices:
        metadata = invoice.get('metadata', {})
        delivery_addr = metadata.get('(Delivery address)', '')
        loading_addr = metadata.get('(Loading address)', '')
        
        if delivery_addr:
            addresses.append({
                'invoice_id': invoice.get('id'),
                'invoice_identifier': invoice.get('invoice_identifier'),
                'truck_plate': invoice.get('truck_plate'),
                'delivery_address': delivery_addr,
                'loading_address': loading_addr
            })
    
    return addresses


def process_addresses(orchestrator: Orchestrator, review_manager: HumanReviewManager, addresses: list) -> list:
    results = []
    
    for addr_data in addresses:
        delivery_addr = addr_data.get('delivery_address', '')
        
        if not delivery_addr:
            continue
        
        result = orchestrator.resolve(delivery_addr)
        result['invoice_id'] = addr_data['invoice_id']
        result['invoice_identifier'] = addr_data['invoice_identifier']
        result['truck_plate'] = addr_data['truck_plate']
        
        results.append(result)
        
        if result['status'] == 'NEED_HUMAN_REVIEW':
            review_manager.add_failed_resolution(
                raw_address=delivery_addr,
                llm_result=result.get('output', {}),
                validation_result={'passed': False, 'reason': result.get('validation_reason')},
                tier_used=3
            )
    
    return results


def save_results(results: list, output_file: str):
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({'results': results}, f, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <vat_invoices.json> [output.json]")
        sys.exit(1)
    
    vat_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'data/processed_results.json'
    
    vat_invoices = load_vat_invoices(vat_file)
    addresses = extract_addresses_from_vat(vat_invoices)
    
    orchestrator = Orchestrator()
    review_manager = HumanReviewManager()
    results = process_addresses(orchestrator, review_manager, addresses)
    
    save_results(results, output_file)
    export_all_queues()


if __name__ == "__main__":
    main()