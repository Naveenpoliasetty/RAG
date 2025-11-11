# check_status.py
from resume_ingestion.database.mongodb_manager import MongoDBManager

def check_document_status():
    mongo = MongoDBManager()
    
    # Count documents by status
    pipeline = [
        {"$group": {
            "_id": "$qdrant_status", 
            "count": {"$sum": 1}
        }}
    ]
    
    status_counts = list(mongo.collection.aggregate(pipeline))
    print("📊 Document Status Counts:")
    for status in status_counts:
        print(f"   {status['_id']}: {status['count']} documents")
    
    # Check if any documents have vectors
    sample_doc = mongo.collection.find_one()
    if sample_doc:
        print(f"\n📄 Sample Document ID: {sample_doc.get('_id')}")
        print(f"   Qdrant Status: {sample_doc.get('qdrant_status')}")
        print(f"   Processing Status: {sample_doc.get('processing_status')}")
        print(f"   Has professional_summary: {bool(sample_doc.get('professional_summary'))}")
        print(f"   Has technical_skills: {bool(sample_doc.get('technical_skills'))}")
        print(f"   Experiences count: {len(sample_doc.get('experiences', []))}")

if __name__ == "__main__":
    check_document_status()