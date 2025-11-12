#!/usr/bin/env python3
"""
Main entry point for MongoDB to Qdrant ingestion pipeline.
Run with: python main.py --mode continuous --batch-size 50
"""

import argparse
import sys
import time
from typing import Dict, Any, Optional

# Import our components
from resume_ingestion.database.mongodb_manager import MongoDBManager
from resume_ingestion.ingestion.batch_ingestion_processor import BatchIngestionProcessor
from resume_ingestion.vector_store.embeddings import EmbeddingService
from resume_ingestion.vector_store.qdrant_manager import QdrantManager
from src.utils.logger import get_logger


logger = get_logger("IngestionPipeline")

class IngestionPipeline:
    """
    Main pipeline class that provides various running modes and monitoring.
    """
    
    def __init__(self, batch_size: int = 50, max_retries: int = 3):
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.mongo_manager: Optional[MongoDBManager] = None
        self.qdrant_manager: Optional[QdrantManager] = None
        self.embedding_service: Optional[EmbeddingService] = None
        self.processor: Optional[BatchIngestionProcessor] = None
        
    def initialize_components(self) -> bool:
        """Initialize all components with health checks."""
        try:
            logger.info("Initializing pipeline components...")
            
            # Initialize MongoDB Manager
            self.mongo_manager = MongoDBManager()
            if not self.mongo_manager.health_check():
                logger.error("MongoDB health check failed")
                return False
            logger.info("MongoDB connection established")
            
            # Initialize Embedding Service
            self.embedding_service = EmbeddingService()
            model_info = self.embedding_service.get_model_info()
            logger.info(f"Embedding service loaded: {model_info['model_name']} (dim: {model_info['vector_size']})")
            
            # Initialize Qdrant Manager
            self.qdrant_manager = QdrantManager()
            if not self.qdrant_manager.health_check():
                logger.error("Qdrant health check failed")
                return False
            logger.info("Qdrant connection established")
            
            # Initialize Batch Processor
            self.processor = BatchIngestionProcessor(
                batch_size=self.batch_size,
                max_retries=self.max_retries
            )
            logger.info("Batch processor initialized")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize pipeline components: {e}")
            return False
    
    def run_single_batch(self) -> Dict[str, Any]:
        """Run a single batch ingestion."""
        if not self.initialize_components():
            return {"success": False, "error": "Component initialization failed"}
        
        try:
            logger.info(f"Starting single batch ingestion (batch_size: {self.batch_size})")
            
            # Get initial stats
            initial_stats = self.processor.get_processing_stats()
            logger.info(f"Initial stats: {initial_stats}")
            
            # Process batch
            batch_result = self.processor.process_batch()
            
            # Get final stats
            final_stats = self.processor.get_processing_stats()
            
            result = {
                "success": True,
                "batch_result": batch_result,
                "initial_stats": initial_stats,
                "final_stats": final_stats
            }
            
            logger.info(f"Batch completed: {batch_result}")
            return result
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            self.shutdown()
    
    def run_continuous(self, interval_seconds: int = 60, max_iterations: Optional[int] = None):
        """Run continuous ingestion."""
        if not self.initialize_components():
            logger.error("Failed to initialize components for continuous processing")
            return
        
        try:
            logger.info(f"Starting continuous ingestion (interval: {interval_seconds}s, max_iterations: {max_iterations})")
            
            # Reset any stuck documents first
            reset_count = self.mongo_manager.reset_stuck_documents()
            if reset_count > 0:
                logger.info(f"Reset {reset_count} stuck documents")
            
            # Show initial state
            stats = self.processor.get_processing_stats()
            self._print_system_status(stats)
            
            # Start continuous processing
            self.processor.continuous_processing(
                interval_seconds=interval_seconds,
                max_iterations=max_iterations
            )
            
        except KeyboardInterrupt:
            logger.info("Continuous processing interrupted by user")
        except Exception as e:
            logger.error(f"Continuous processing failed: {e}")
        finally:
            self.shutdown()
    
    def run_until_empty(self, batch_interval: int = 10):
        """Run batches until no more pending documents remain."""
        if not self.initialize_components():
            return
        
        try:
            logger.info("Starting ingestion until no pending documents remain")
            total_processed = 0
            total_successful = 0
            iteration = 0
            
            while True:
                iteration += 1
                logger.info(f"Processing iteration {iteration}")
                
                # Process batch
                batch_result = self.processor.process_batch()
                total_processed += batch_result["processed"]
                total_successful += batch_result["successful"]
                
                # Check if we're done
                if batch_result["processed"] == 0:
                    logger.info("No more pending documents found. Ingestion complete!")
                    break
                
                # Small delay between batches
                if batch_interval > 0:
                    time.sleep(batch_interval)
            
            logger.info(f"Ingestion completed. Total: {total_processed} processed, {total_successful} successful")
            
        except KeyboardInterrupt:
            logger.info("Processing interrupted by user")
        except Exception as e:
            logger.error(f"Processing failed: {e}")
        finally:
            self.shutdown()
    
    def show_status(self):
        """Show current system status without processing."""
        if not self.initialize_components():
            return
        
        try:
            stats = self.processor.get_processing_stats()
            self._print_detailed_status(stats)
        finally:
            self.shutdown()
    
    def reset_stuck_documents(self, reset_after_minutes: int = 30):
        """Reset stuck documents without processing."""
        if not self.initialize_components():
            return
        
        try:
            reset_count = self.mongo_manager.reset_stuck_documents(reset_after_minutes)
            logger.info(f"Reset {reset_count} stuck documents")
            
            # Show updated status
            stats = self.processor.get_processing_stats()
            self._print_system_status(stats)
        finally:
            self.shutdown()
    
    def _print_system_status(self, stats: Dict[str, Any]):
        """Print formatted system status."""
        print("\n" + "="*60)
        print("SYSTEM STATUS")
        print("="*60)
        print(f"🔍 MongoDB Health: {'OK' if stats['mongodb_health'] else 'FAILED'}")
        print(f"🔍 Qdrant Health: {'OK' if stats['qdrant_health'] else 'FAILED'}")
        print("\nINGESTION STATISTICS:")
        
        ingestion_stats = stats.get('ingestion_stats', {})
        for status, info in ingestion_stats.items():
            count = info.get('count', 0)
            print(f"   {status.upper():<12}: {count:>4} documents")
        
        total_docs = sum(info.get('count', 0) for info in ingestion_stats.values())
        print(f"   {'TOTAL':<12}: {total_docs:>4} documents")
        print("="*60)


    
    def debug_document_structure(self, sample_size: int = 5):
        """Debug method to understand document structure."""
        if not self.initialize_components():
            logger.error("Failed to initialize components for debugging")
            return
        
        try:
            documents = self.mongo_manager.get_pending_documents_batch(sample_size)
            
            if not documents:
                logger.info("No documents found for debugging")
                return
            
            logger.info("🔍 DOCUMENT STRUCTURE ANALYSIS:")
            logger.info("=" * 80)
            
            for i, doc in enumerate(documents):
                logger.info(f"\n📄 Document {i+1}/{len(documents)}")
                logger.info("-" * 40)
                logger.info(f"📋 ID: {doc.get('_id', 'Unknown')}")
                logger.info(f"🏷️ Category: {doc.get('category', 'Not set')}")
                logger.info(f"💼 Job Role: {doc.get('job_role', 'Not set')}")
                logger.info("📊 Available fields (excluding _id):")
                
                # Sort fields for consistent output
                fields = sorted([k for k in doc.keys() if k != "_id"])
                
                for field in fields:
                    value = doc[field]
                    if isinstance(value, list):
                        if value:
                            logger.info(f"   📁 {field}: LIST with {len(value)} items")
                            # Show first few items if it's a list of strings
                            if value and isinstance(value[0], str):
                                preview = ", ".join([str(v)[:50] for v in value[:3]])
                                if len(value) > 3:
                                    preview += f" ... and {len(value) - 3} more"
                                logger.info(f"      Sample: {preview}")
                            # If it's experiences, show structure
                            if field.lower() in ['experience', 'experiences', 'work_experience'] and value:
                                first_exp = value[0]
                                logger.info(f"      Experience structure: {list(first_exp.keys())}")
                        else:
                            logger.info(f"   📁 {field}: EMPTY LIST")
                            
                    elif isinstance(value, dict):
                        logger.info(f"   📊 {field}: DICT with keys: {list(value.keys())}")
                        
                    elif isinstance(value, str):
                        if value.strip():
                            preview = value[:100] + "..." if len(value) > 100 else value
                            logger.info(f"{field}: {preview}")
                        else:
                            logger.info(f"{field}: EMPTY STRING")
                            
                    else:
                        logger.info(f"{field}: {type(value).__name__} = {value}")
                
                logger.info("-" * 40)
                
        except Exception as e:
            logger.error(f"Error during document structure debugging: {e}")
        finally:
            self.shutdown()
    
    def _print_detailed_status(self, stats: Dict[str, Any]):
        """Print detailed system status."""
        self._print_system_status(stats)
        
        # Show collection info if available
        if self.qdrant_manager and hasattr(self.qdrant_manager, 'collections_mapping'):
            print("\n QDRANT COLLECTIONS:")
            for key, collection_name in self.qdrant_manager.collections_mapping.items():
                collection_info = self.qdrant_manager.get_collection_info(collection_name)
                if collection_info:
                    print(f"   {collection_name}: {collection_info['points_count']} points")
        
        # Show embedding model info
        if self.embedding_service:
            model_info = self.embedding_service.get_model_info()
            print(f"\n EMBEDDING MODEL: {model_info['model_name']}")
            print(f"   Vector Dimension: {model_info['vector_size']}")
            print(f"   Chunk Size: {model_info['chunk_size']}")
            print(f"   Chunk Overlap: {model_info['chunk_overlap']}")
    
    def shutdown(self):
        """Gracefully shutdown all components."""
        logger.info("Shutting down pipeline...")
        try:
            if self.processor:
                self.processor.close()
            logger.info("Pipeline shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(description='MongoDB to Qdrant Ingestion Pipeline')
    
    # Running modes
    parser.add_argument('--mode', 
                       choices=['single', 'continuous', 'until-empty', 'status', 'reset-stuck', 'debug-structure'],
                       default='single',
                       help='Running mode (default: single)')
    
    # Batch parameters
    parser.add_argument('--batch-size', 
                       type=int, 
                       default=50,
                       help='Number of documents to process per batch (default: 50)')
    
    parser.add_argument('--interval', 
                       type=int, 
                       default=60,
                       help='Interval between batches in seconds for continuous mode (default: 60)')
    
    parser.add_argument('--max-iterations',
                       type=int,
                       help='Maximum number of iterations for continuous mode')
    
    parser.add_argument('--reset-after',
                       type=int,
                       default=30,
                       help='Minutes after which to reset stuck documents (default: 30)')
    
    # Additional options
    parser.add_argument('--verbose', '-v',
                       action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logger.getLogger().setLevel(logger.DEBUG)
        logger.debug("Verbose logging enabled")
    
    # Create pipeline instance
    pipeline = IngestionPipeline(batch_size=args.batch_size)
    
    try:
        # Execute based on mode
        if args.mode == 'single':
            result = pipeline.run_single_batch()
            if not result['success']:
                sys.exit(1)
                
        elif args.mode == 'continuous':
            pipeline.run_continuous(
                interval_seconds=args.interval,
                max_iterations=args.max_iterations
            )
            
        elif args.mode == 'until-empty':
            pipeline.run_until_empty(batch_interval=args.interval)
            
        elif args.mode == 'status':
            pipeline.show_status()
            
        elif args.mode == 'reset-stuck':
            pipeline.reset_stuck_documents(reset_after_minutes=args.reset_after)
        
        elif args.mode == 'debug-structure':  # NEW MODE
            pipeline.debug_document_structure(sample_size=5)

    
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()