# reset_documents.py
from resume_ingestion.database.mongodb_manager import MongoDBManager

def reset_documents_for_testing():
    mongo = MongoDBManager()
    
    # Reset all documents to "pending" status
    result = mongo.collection.update_many(
        {},  # All documents
        {"$set": {"qdrant_status": "pending"}}
    )
    
    print(f"✅ Reset {result.modified_count} documents to 'pending' status")
    
    # Verify
    pending_count = mongo.collection.count_documents({"qdrant_status": "pending"})
    print(f"📊 Now have {pending_count} pending documents")

if __name__ == "__main__":
    reset_documents_for_testing()