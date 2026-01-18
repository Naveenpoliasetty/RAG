#!/usr/bin/env python3
"""
Connection Status Check Script
Checks MongoDB and Qdrant connection status and provides detailed information.
"""

import sys
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from resume_ingestion.database.mongodb_manager import MongoDBManager
    from resume_ingestion.vector_store.qdrant_manager import QdrantManager
    from src.core.settings import config
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root and dependencies are installed.")
    sys.exit(1)


def check_mongodb_connection() -> Dict[str, Any]:
    """Check MongoDB connection status and return detailed information."""
    result = {
        "status": "unknown",
        "connected": False,
        "error": None,
        "database": None,
        "collection": None,
        "document_count": None,
        "server_info": None,
        "uri": None
    }
    
    try:
        print("🔍 Checking MongoDB connection...")
        mongo = MongoDBManager()
        
        # Health check
        if mongo.health_check():
            result["connected"] = True
            result["status"] = " Connected"
            result["database"] = mongo.db.name
            result["collection"] = mongo.collection.name
            result["uri"] = str(mongo.client.address)
            
            # Get document count
            try:
                doc_count = mongo.collection.count_documents({})
                result["document_count"] = doc_count
            except Exception as e:
                result["error"] = f"Failed to count documents: {e}"
            
            # Get server info
            try:
                server_info = mongo.client.server_info()
                result["server_info"] = {
                    "version": server_info.get("version", "unknown"),
                    "host": server_info.get("host", "unknown")
                }
            except Exception as e:
                result["error"] = f"Failed to get server info: {e}"
                
        else:
            result["status"] = "❌ Health check failed"
            result["error"] = "Health check returned False"
            
    except Exception as e:
        result["status"] = "❌ Connection failed"
        result["error"] = str(e)
        result["connected"] = False
    
    return result


def check_qdrant_connection() -> Dict[str, Any]:
    """Check Qdrant connection status and return detailed information."""
    result = {
        "status": "unknown",
        "connected": False,
        "error": None,
        "host": None,
        "port": None,
        "collections": [],
        "total_points": 0
    }
    
    try:
        print("🔍 Checking Qdrant connection...")
        qdrant = QdrantManager()
        
        # Health check
        if qdrant.health_check():
            result["connected"] = True
            result["status"] = " Connected"
            result["host"] = config.qdrant_host
            result["port"] = config.qdrant_port
            
            # Get collections info
            try:
                collections_info = []
                total_points = 0
                
                for key, collection_name in qdrant.collections_mapping.items():
                    info = qdrant.get_collection_info(collection_name)
                    if info:
                        points_count = info.get("points_count", 0)
                        total_points += points_count
                        collections_info.append({
                            "name": collection_name,
                            "key": key,
                            "points_count": points_count,
                            "status": info.get("status", "unknown")
                        })
                    else:
                        collections_info.append({
                            "name": collection_name,
                            "key": key,
                            "points_count": 0,
                            "status": "error"
                        })
                
                result["collections"] = collections_info
                result["total_points"] = total_points
                
            except Exception as e:
                result["error"] = f"Failed to get collections info: {e}"
        else:
            result["status"] = "❌ Health check failed"
            result["error"] = "Health check returned False"
            
    except Exception as e:
        result["status"] = "❌ Connection failed"
        result["error"] = str(e)
        result["connected"] = False
    
    return result


def print_mongodb_status(status: Dict[str, Any]):
    """Print MongoDB status in a formatted way."""
    print("\n" + "="*60)
    print("📊 MONGODB CONNECTION STATUS")
    print("="*60)
    print(f"Status: {status['status']}")
    
    if status["connected"]:
        print(f"URI: {status.get('uri', 'N/A')}")
        print(f"Database: {status.get('database', 'N/A')}")
        print(f"Collection: {status.get('collection', 'N/A')}")
        print(f"Document Count: {status.get('document_count', 'N/A')}")
        
        if status.get("server_info"):
            server_info = status["server_info"]
            print(f"MongoDB Version: {server_info.get('version', 'N/A')}")
    else:
        print(f"❌ Error: {status.get('error', 'Unknown error')}")
    
    print("="*60)


def print_qdrant_status(status: Dict[str, Any]):
    """Print Qdrant status in a formatted way."""
    print("\n" + "="*60)
    print("📊 QDRANT CONNECTION STATUS")
    print("="*60)
    print(f"Status: {status['status']}")
    
    if status["connected"]:
        print(f"Host: {status.get('host', 'N/A')}")
        print(f"Port: {status.get('port', 'N/A')}")
        print(f"Total Points: {status.get('total_points', 0)}")
        
        collections = status.get("collections", [])
        if collections:
            print("\n📋 Collections:")
            for coll in collections:
                print(f"   • {coll['name']} ({coll['key']})")
                print(f"     Points: {coll['points_count']}, Status: {coll['status']}")
        else:
            print("\n⚠️  No collections found")
    else:
        print(f"❌ Error: {status.get('error', 'Unknown error')}")
    
    print("="*60)


def main():
    """Main function to check both connections."""
    print("\n" + "="*60)
    print("🔌 CONNECTION STATUS CHECK")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Check MongoDB
    mongodb_status = check_mongodb_connection()
    print_mongodb_status(mongodb_status)
    
    # Check Qdrant
    qdrant_status = check_qdrant_connection()
    print_qdrant_status(qdrant_status)
    
    # Summary
    print("\n" + "="*60)
    print("📋 SUMMARY")
    print("="*60)
    mongodb_ok = "" if mongodb_status["connected"] else "❌"
    qdrant_ok = "" if qdrant_status["connected"] else "❌"
    print(f"MongoDB: {mongodb_ok}")
    print(f"Qdrant: {qdrant_ok}")
    
    if mongodb_status["connected"] and qdrant_status["connected"]:
        print("\n All connections are healthy!")
        return 0
    else:
        print("\n⚠️  Some connections failed. Check the details above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

