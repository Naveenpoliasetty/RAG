#!/usr/bin/env python3
"""
Test script for testing the retrieval process.

Usage:
    # Run with default example
    python test_retrieval.py
    
    # Or use programmatically
    from test_retrieval import quick_test
    
    results = quick_test(
        job_description="Your job description here...",
        job_roles=["oracle consultant", "data engineer"],
        top_k_summary=3,
        top_k_skills=3,
        top_k_experience=12
    )

This script allows you to test the retrieval process by providing:
- A job description string
- A list of related job roles

It will show:
- How many resume IDs were found for each job role
- How many unique resume IDs were retrieved for each section
- The actual retrieved data (summary, skills, experiences)
- Scores for each retrieved resume

The results are also saved to test_retrieval_results.json for further analysis.
"""

import asyncio
import json
from typing import Dict, List, Any

from src.core.db_manager import get_qdrant_manager, get_mongodb_manager
from src.retriever.get_ids import ResumeIdsRetriever
from src.utils.logger import get_logger
from qdrant_client import models as qmodels

logger = get_logger(__name__)


async def diagnose_qdrant_collection(
    qdrant_manager,
    collection_name: str,
    resume_ids: List[str],
    job_description: str
):
    """
    Diagnose why Qdrant is only returning 1 result.
    Checks how many documents exist for the resume IDs and their scores.
    """
    print(f"\n{'='*80}")
    print(f"DIAGNOSIS: {collection_name}")
    print(f"{'='*80}")
    
    # Check how many documents exist for these resume IDs
    print(f"\n[1] Checking documents in Qdrant for {len(resume_ids)} resume IDs...")
    
    try:
        # Build filter
        search_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="resume_id",
                    match=qmodels.MatchAny(any=resume_ids)
                )
            ]
        )
        
        # Scroll through all documents with these resume IDs
        points, _ = qdrant_manager.client.scroll(
            collection_name=collection_name,
            scroll_filter=search_filter,
            limit=1000,
            with_payload=True,
            with_vectors=False
        )
        
        print(f"✓ Found {len(points)} documents in Qdrant for these resume IDs")
        
        # Count unique resume IDs
        unique_resume_ids = set()
        for point in points:
            payload = point.payload or {}
            rid = payload.get("resume_id")
            if rid:
                unique_resume_ids.add(rid)
        
        print(f"✓ Found {len(unique_resume_ids)} unique resume IDs in Qdrant")
        print(f"  Unique IDs: {list(unique_resume_ids)[:10]}...")
        
        # Now do a search and see what scores we get
        print(f"\n[2] Performing semantic search to see scores...")
        
        # Embed job description
        jd_vecs = qdrant_manager.embedding_service.encode_texts([job_description])
        if not jd_vecs or len(jd_vecs) == 0:
            print("⚠️  Failed to embed job description")
            return
        
        jd_vector = jd_vecs[0]
        
        # Search with a very high limit to see all scores
        search_results = qdrant_manager.client.search(
            collection_name=collection_name,
            query_vector=jd_vector,
            limit=100,  # Request up to 100 results
            with_payload=True,
            with_vectors=False,
            query_filter=search_filter,
            score_threshold=None  # No threshold - get all results
        )
        
        print(f"✓ Qdrant returned {len(search_results)} search results")
        
        if search_results:
            print(f"\n[3] Score distribution:")
            scores = [r.score for r in search_results]
            print(f"  • Min score: {min(scores):.4f}")
            print(f"  • Max score: {max(scores):.4f}")
            print(f"  • Mean score: {sum(scores)/len(scores):.4f}")
            print(f"  • Median score: {sorted(scores)[len(scores)//2]:.4f}")
            
            print(f"\n[4] Top 10 results:")
            for i, result in enumerate(search_results[:10], 1):
                payload = result.payload or {}
                rid = payload.get("resume_id", "N/A")
                print(f"  {i}. Resume {rid}: score={result.score:.4f}")
            
            # Check if results are filtered by resume_id
            result_resume_ids = set()
            for result in search_results:
                payload = result.payload or {}
                rid = payload.get("resume_id")
                if rid:
                    result_resume_ids.add(rid)
            
            print(f"\n[5] Unique resume IDs in search results: {len(result_resume_ids)}")
            print(f"  IDs: {list(result_resume_ids)}")
            
            if len(result_resume_ids) < len(unique_resume_ids):
                print(f"\n⚠️  WARNING: Only {len(result_resume_ids)} resume IDs in search results, but {len(unique_resume_ids)} exist in collection!")
                print(f"   This suggests some resumes have very low similarity scores.")
        else:
            print("⚠️  No search results returned!")
            
    except Exception as e:
        print(f"❌ Error during diagnosis: {e}")
        import traceback
        traceback.print_exc()


async def test_retrieval(
    resume_dict: Dict[str, Any],
    job_description: str,
    job_roles: List[str],
    top_k_summary: int = 3,
    top_k_skills: int = 3,
    top_k_experience: int = 12,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3
) -> Dict[str, Any]:
    """
    Test the retrieval process without generating the resume.
    
    Args:
        resume_dict: Resume dictionary (for reference, not used in retrieval)
        job_description: Job description string
        job_roles: List of related job role strings
        top_k_summary: Number of top summaries to retrieve
        top_k_skills: Number of top skills to retrieve
        top_k_experience: Number of top experiences to retrieve
        semantic_weight: Weight for semantic similarity (0.0-1.0)
        keyword_weight: Weight for keyword matching (0.0-1.0)
    
    Returns:
        Dictionary containing retrieval results and statistics
    """
    print("=" * 80)
    print("RETRIEVAL TEST")
    print("=" * 80)
    
    # Initialize managers
    print("\n[1] Initializing database connections...")
    qdrant_manager = get_qdrant_manager()
    mongodb_manager = get_mongodb_manager()
    retriever = ResumeIdsRetriever(mongo_manager=mongodb_manager, qdrant_manager=qdrant_manager)
    print("✓ Connections established")
    
    # Filter by job roles
    print(f"\n[2] Filtering resumes by job roles: {job_roles}")
    filtered_resume_object_ids = retriever.get_resume_ids_by_job_roles(job_roles)
    filtered_resume_ids = [str(oid) for oid in filtered_resume_object_ids]
    print(f"✓ Found {len(filtered_resume_ids)} resume IDs matching job roles")
    
    if not filtered_resume_ids:
        print("⚠️  No resumes found for the given job roles!")
        return {
            "filtered_resume_ids": [],
            "summary_results": [],
            "skills_results": [],
            "experience_results": [],
            "summary_data": [],
            "skills_data": [],
            "experience_data": []
        }
    
    # DIAGNOSIS: Check what's actually in Qdrant
    print("\n" + "="*80)
    print("DIAGNOSING QDRANT COLLECTIONS")
    print("="*80)
    
    collections_mapping = {
        "professional_summary": "professional_summaries",
        "technical_skills": "technical_skills",
        "experiences": "experiences"
    }
    
    for section_key, collection_name in collections_mapping.items():
        await diagnose_qdrant_collection(
            qdrant_manager=qdrant_manager,
            collection_name=collection_name,
            resume_ids=filtered_resume_ids,
            job_description=job_description
        )
    
    # Section-specific searches
    print(f"\n[3] Performing section-specific searches...")
    print(f"   - Summary: top_k={top_k_summary}")
    print(f"   - Skills: top_k={top_k_skills}")
    print(f"   - Experience: top_k={top_k_experience}")
    
    # Summary search
    print("\n[3a] Searching for professional summaries...")
    summary_results = qdrant_manager.match_resumes_by_section(
        job_description=job_description,
        section_key="professional_summary",
        top_k=top_k_summary,
        resume_ids_filter=filtered_resume_ids,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )
    summary_rids = [rid for rid, score in summary_results]
    print(f"✓ Found {len(summary_results)} summary results")
    print(f"✓ Extracted {len(summary_rids)} unique resume IDs: {summary_rids}")
    if summary_results:
        print("   Top scores:")
        for rid, score in summary_results[:3]:
            print(f"     - Resume {rid}: {score:.4f}")
    
    # Skills search
    print("\n[3b] Searching for technical skills...")
    skills_results = qdrant_manager.match_resumes_by_section(
        job_description=job_description,
        section_key="technical_skills",
        top_k=top_k_skills,
        resume_ids_filter=filtered_resume_ids,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )
    skills_rids = [rid for rid, score in skills_results]
    print(f"✓ Found {len(skills_results)} skills results")
    print(f"✓ Extracted {len(skills_rids)} unique resume IDs: {skills_rids}")
    if skills_results:
        print("   Top scores:")
        for rid, score in skills_results[:3]:
            print(f"     - Resume {rid}: {score:.4f}")
    
    # Experience search
    print("\n[3c] Searching for experiences...")
    exp_results = qdrant_manager.match_resumes_by_section(
        job_description=job_description,
        section_key="experiences",
        top_k=top_k_experience,
        resume_ids_filter=filtered_resume_ids,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )
    exp_rids = [rid for rid, score in exp_results]
    print(f"✓ Found {len(exp_results)} experience results")
    print(f"✓ Extracted {len(exp_rids)} unique resume IDs: {exp_rids}")
    if exp_results:
        print("   Top scores:")
        for rid, score in exp_results[:5]:
            print(f"     - Resume {rid}: {score:.4f}")
    
    # Fetch data from MongoDB
    print("\n[4] Fetching data from MongoDB...")
    
    print("\n[4a] Fetching professional summaries...")
    summary_data = mongodb_manager.get_sections_by_resume_ids(summary_rids, "professional_summary")
    print(f"✓ Retrieved {len(summary_data)} summary documents")
    
    print("\n[4b] Fetching technical skills...")
    skills_data = mongodb_manager.get_sections_by_resume_ids(skills_rids, "technical_skills")
    print(f"✓ Retrieved {len(skills_data)} skills documents")
    
    print("\n[4c] Fetching experiences...")
    exp_data = mongodb_manager.get_sections_by_resume_ids(exp_rids, "experiences")
    print(f"✓ Retrieved {len(exp_data)} experience documents")
    
    # Compile results
    results = {
        "input": {
            "job_description": job_description,
            "job_roles": job_roles,
            "top_k_summary": top_k_summary,
            "top_k_skills": top_k_skills,
            "top_k_experience": top_k_experience,
            "semantic_weight": semantic_weight,
            "keyword_weight": keyword_weight
        },
        "filtered_resume_ids": {
            "count": len(filtered_resume_ids),
            "ids": filtered_resume_ids[:10]  # Show first 10
        },
        "summary_results": {
            "count": len(summary_results),
            "unique_resume_ids": len(summary_rids),
            "resume_ids": summary_rids,
            "scores": [(rid, score) for rid, score in summary_results],
            "data": summary_data
        },
        "skills_results": {
            "count": len(skills_results),
            "unique_resume_ids": len(skills_rids),
            "resume_ids": skills_rids,
            "scores": [(rid, score) for rid, score in skills_results],
            "data": skills_data
        },
        "experience_results": {
            "count": len(exp_results),
            "unique_resume_ids": len(exp_rids),
            "resume_ids": exp_rids,
            "scores": [(rid, score) for rid, score in exp_results],
            "data": exp_data
        }
    }
    
    return results


def print_results(results: Dict[str, Any], show_data: bool = True):
    """Pretty print the retrieval results."""
    print("\n" + "=" * 80)
    print("RETRIEVAL RESULTS SUMMARY")
    print("=" * 80)
    
    print("\n📊 STATISTICS:")
    print(f"  • Filtered Resume IDs: {results['filtered_resume_ids']['count']}")
    print(f"  • Summary Results: {results['summary_results']['count']} (unique: {results['summary_results']['unique_resume_ids']})")
    print(f"  • Skills Results: {results['skills_results']['count']} (unique: {results['skills_results']['unique_resume_ids']})")
    print(f"  • Experience Results: {results['experience_results']['count']} (unique: {results['experience_results']['unique_resume_ids']})")
    
    print("\n📝 SUMMARY RETRIEVAL:")
    print(f"  Resume IDs: {results['summary_results']['resume_ids']}")
    if results['summary_results']['scores']:
        print("  Scores:")
        for rid, score in results['summary_results']['scores']:
            print(f"    - {rid}: {score:.4f}")
    
    print("\n🛠️  SKILLS RETRIEVAL:")
    print(f"  Resume IDs: {results['skills_results']['resume_ids']}")
    if results['skills_results']['scores']:
        print("  Scores:")
        for rid, score in results['skills_results']['scores']:
            print(f"    - {rid}: {score:.4f}")
    
    print("\n💼 EXPERIENCE RETRIEVAL:")
    print(f"  Resume IDs: {results['experience_results']['resume_ids']}")
    if results['experience_results']['scores']:
        print("  Top 5 Scores:")
        for rid, score in results['experience_results']['scores'][:5]:
            print(f"    - {rid}: {score:.4f}")
    
    if show_data:
        print("\n" + "=" * 80)
        print("RETRIEVED DATA")
        print("=" * 80)
        
        print("\n📄 PROFESSIONAL SUMMARIES:")
        for i, item in enumerate(results['summary_results']['data'], 1):
            print(f"\n  [{i}] Resume ID: {item.get('resume_id', 'N/A')}")
            summary = item.get('professional_summary', [])
            if isinstance(summary, list):
                print(f"     Bullet points: {len(summary)}")
                for j, bullet in enumerate(summary[:3], 1):  # Show first 3
                    print(f"       {j}. {bullet[:100]}..." if len(bullet) > 100 else f"       {j}. {bullet}")
            else:
                print(f"     Data: {str(summary)[:200]}...")
        
        print("\n🛠️  TECHNICAL SKILLS:")
        for i, item in enumerate(results['skills_results']['data'], 1):
            print(f"\n  [{i}] Resume ID: {item.get('resume_id', 'N/A')}")
            skills = item.get('technical_skills', [])
            if isinstance(skills, list):
                print(f"     Skills entries: {len(skills)}")
                for j, skill_entry in enumerate(skills[:3], 1):  # Show first 3
                    print(f"       {j}. {skill_entry[:100]}..." if len(str(skill_entry)) > 100 else f"       {j}. {skill_entry}")
            else:
                print(f"     Data: {str(skills)[:200]}...")
        
        print("\n💼 EXPERIENCES:")
        for i, item in enumerate(results['experience_results']['data'], 1):
            print(f"\n  [{i}] Resume ID: {item.get('resume_id', 'N/A')}")
            experiences = item.get('experiences', [])
            if isinstance(experiences, list):
                print(f"     Experience entries: {len(experiences)}")
                for j, exp in enumerate(experiences[:2], 1):  # Show first 2
                    job_role = exp.get('job_role', 'N/A') if isinstance(exp, dict) else 'N/A'
                    print(f"       {j}. Job Role: {job_role}")
                    if isinstance(exp, dict):
                        responsibilities = exp.get('responsibilities', [])
                        if isinstance(responsibilities, list):
                            print(f"          Responsibilities: {len(responsibilities)}")
                        else:
                            print(f"          Responsibilities: {str(responsibilities)[:100]}...")
            else:
                print(f"     Data: {str(experiences)[:200]}...")


def quick_test(
    job_description: str,
    job_roles: List[str],
    top_k_summary: int = 3,
    top_k_skills: int = 3,
    top_k_experience: int = 12,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
    show_data: bool = True,
    save_to_file: bool = True
) -> Dict[str, Any]:
    """
    Quick test function that can be called directly.
    
    Args:
        job_description: Job description string
        job_roles: List of related job role strings
        top_k_summary: Number of top summaries to retrieve
        top_k_skills: Number of top skills to retrieve
        top_k_experience: Number of top experiences to retrieve
        semantic_weight: Weight for semantic similarity (0.0-1.0)
        keyword_weight: Weight for keyword matching (0.0-1.0)
        show_data: Whether to print the retrieved data
        save_to_file: Whether to save results to JSON file
    
    Returns:
        Dictionary containing retrieval results
    """
    resume_dict = {}  # Not used in retrieval, just for API compatibility
    
    results = asyncio.run(test_retrieval(
        resume_dict=resume_dict,
        job_description=job_description,
        job_roles=job_roles,
        top_k_summary=top_k_summary,
        top_k_skills=top_k_skills,
        top_k_experience=top_k_experience,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    ))
    
    print_results(results, show_data=show_data)
    
    if save_to_file:
        print("\n" + "=" * 80)
        print("Saving results to test_retrieval_results.json...")
        with open("test_retrieval_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        print("✓ Results saved!")
    
    return results


async def main():
    """Main function with example usage."""
    
    # Example inputs
    with open("/Users/naveenpoliasetty/Downloads/RAG-1/resume_text.json", "r") as f:
        resume_dict = json.load(f)
    
    job_description = """
            Job Description:
        We are seeking an experienced Oracle Sales Cloud Consultant to support implementation, customization, and optimization of Oracle CX Sales applications. The ideal candidate will work closely with business stakeholders to gather requirements, configure the system, and ensure seamless integration with other Oracle and third-party applications.
        Key Responsibilities:
        Implement and configure Oracle Sales Cloud modules (Leads, Opportunities, Accounts, Contacts, and Forecasting).
        Gather business requirements and translate them into functional solutions.
        Develop custom reports and dashboards using OTBI/BIP.
        Collaborate with technical teams for integrations and data migration.
        Provide end-user training, documentation, and post-implementation support.
        Required Skills:
        Hands-on experience in Oracle Sales Cloud (B2B/B2C) implementation and support.
        Strong understanding of sales automation processes and CRM best practices.
        Knowledge of OIC, Groovy scripting, and REST/SOAP integrations is a plus.
        Excellent communication and problem-solving skills.

    """
    
    job_roles = ["oracle & informatica developer",
    "oracle & sql database administrator",
    "oracle & sql server developer",
    "oracle + actimize trade surveillance developer",
    "oracle / postgresql database administrator",
    "oracle access manager",
    "oracle accounts payable consultant",
    "oracle adf consultant profile",
    "oracle adf developer",
    "oracle adf technical consultant",
    "oracle adf/web center developer",
    "oracle administrator",
    "oracle agile plm lead consultant",
    "oracle application consultant",
    "oracle application database administrator",
    "oracle application developer",
    "oracle applications (ebs) technical consultant",
    "oracle applications database administrator",
    "oracle applications database administrator & middleware administrator",
    "oracle applications database administrator/oracle database administrator",
    "oracle applications developer",
    "oracle applications engineer",
    "oracle applications financial developer",
    "oracle applications functional analyst",
    "oracle applications functional consultant",
    "oracle applications functional consultant profile",
    "oracle applications r12 / fusion middleware / fusion applications database administrator",
    "oracle applications r12 database administrator",
    "oracle applications scm / crm lead consultant",
    "oracle applications tech lead",
    "oracle applications technical consultant",
    "oracle applications technical developer",
    "oracle applications techno functional consultant",
    "oracle applications techno-functional",
    "oracle applications techno-functional consultant",
    "oracle applications/fmw consultant",
    "oracle applition technil developer",
    "oracle applitions techno-functional consultant",
    "oracle apps admin & demantra admin",
    "oracle apps architect/database consultant",
    "oracle apps consultant",
    "oracle apps consultant (r12)",
    "oracle apps database - consultant",
    "oracle apps database administrator",
    "oracle apps database administrator consultant",
    "oracle apps database administrator/ lead oracle database administrator",
    "oracle apps database administrator/bi database administrator/admin",
    "oracle apps database administrator/oracle database administrator",
    "oracle apps database consultant",
    "oracle apps developer",
    "oracle apps financial functional consultant",
    "oracle apps functional analyst",
    "oracle apps functional consultant",
    "oracle apps r12 order management & supply chain",
    "oracle apps senior. finance consultant & team lead",
    "oracle apps soa consultant",
    "oracle apps technical analyst",
    "oracle apps technical consultant",
    "oracle apps technical consultant & pl/sql developer",
    "oracle apps technical consultant profile",
    "oracle apps technical developer",
    "oracle apps technical lead",
    "oracle apps technical oaf consultant",
    "oracle apps techno - functional cdh consultant",
    "oracle apps techno functional",
    "oracle apps techno functional analyst",
    "oracle apps techno functional consultant",
    "oracle apps techno functional developer",
    "oracle apps techno futional consultant",
    "oracle apps techno-functional consultant",
    "oracle atg developer profile",
    "oracle bi consultant",
    "oracle bi developer",
    "oracle biee developer",
    "oracle bpel/osb developer",
    "oracle bpm consultant",
    "oracle bpm developer",
    "oracle business intelligence consultant",
    "oracle business intelligence developer/analyst",
    "oracle business process consultant",
    "oracle cdc developer",
    "oracle certified programmer/analyst",
    "oracle cloud analyst",
    "oracle cloud applications architect",
    "oracle cloud erp / techno functional consultant",
    "oracle cloud financial implementation consultant",
    "oracle cloud financials lead consultant",
    "oracle cloud hcm consultant",
    "oracle cloud hcm techno functional consultant",
    "oracle cloud process manufacturing functional analyst",
    "oracle cloud procurement sme",
    "oracle consultant",
    "oracle consultant & data lead",
    "oracle consultant (oracle database administrator)",
    "oracle consultant profile",
    "oracle consultant/hadoop developer",
    "oracle core database administrator",
    "oracle customer care & billing designer",
    "oracle database admin",
    "oracle database administration",
    "oracle database administrator",
    "oracle database administrator & aws consultant",
    "oracle database administrator & cloud architect",
    "oracle database administrator & hadoop administrator",
    "oracle database administrator & microsoft db",
    "oracle database administrator & oracle golden gate admin",
    "oracle database administrator & pl/sql developer",
    "oracle database administrator (sme)",
    "oracle database administrator / application database administrator",
    "oracle database administrator administartor",
    "oracle database administrator consultant",
    "oracle database administrator l3",
    "oracle database administrator lead",
    "oracle database administrator profile",
    "oracle database administrator support",
    "oracle database administrator team lead",
    "oracle database administrator, oracle golden gate admin, multi db admin",
    "oracle database administrator/ data modeler",
    "oracle database administrator/ data modelor",
    "oracle database administrator/architect",
    "oracle database administrator/cassandra administrator",
    "oracle database administrator/database analyst",
    "oracle database administrator/developer",
    "oracle database administrator/developer instructor",
    "oracle database administrator/technical architect",
    "oracle database consultant",
    "oracle database developer",
    "oracle database developer/data analyst",
    "oracle database engineer",
    "oracle database manager profile",
    "oracle db lead",
    "oracle developer",
    "oracle developer & production support",
    "oracle developer / analyst",
    "oracle developer profile",
    "oracle developer, profile",
    "oracle developer/ support database administrator",
    "oracle developer/analyst",
    "oracle developer/database administrator",
    "oracle developer/designer",
    "oracle developer/eagle developer",
    "oracle developer/oracle database administrator",
    "oracle developer/report writer",
    "oracle developer/reports developer",
    "oracle e-biz technical consultant",
    "oracle e-business applications database administrator",
    "oracle e-business consultant",
    "oracle e-business suite",
    "oracle e-business suite r12 performance test consultant",
    "oracle e-business suite test consultant",
    "oracle ebiz/fusion hcm consultant, project lead",
    "oracle ebs analyst",
    "oracle ebs analyst/developer",
    "oracle ebs apps technical consultant",
    "oracle ebs consultant",
    "oracle ebs database administrator",
    "oracle ebs developer",
    "oracle ebs finance functional business analyst",
    "oracle ebs financial functional consultant",
    "oracle ebs financials production support",
    "oracle ebs functional analyst",
    "oracle ebs functional consultant",
    "oracle ebs functional lead",
    "oracle ebs production support lead",
    "oracle ebs project lead",
    "oracle ebs project manager",
    "oracle ebs project manager & senior business analyst",
    "oracle ebs r12.3 otc functional/qa consultant",
    "oracle ebs senior techno functional consultant",
    "oracle ebs supply chain wms function lead",
    "oracle ebs tech consultant",
    "oracle ebs technical consultant",
    "oracle ebs technical lead",
    "oracle ebs techno functional consultant",
    "oracle ebs techno-functional senior. developer",
    "oracle ebusiness",
    "oracle enterprise programmer analyst/r12 support",
    "oracle epm hyperion lead",
    "oracle erp & data warehouse application developer",
    "oracle erp consultant",
    "oracle erp financials/scm developer",
    "oracle erp functional tester",
    "oracle erp qa engineer",
    "oracle finance analyst",
    "oracle finance functional lead consultant",
    "oracle finance techno functional consultant",
    "oracle financial /business system analyst",
    "oracle financial analyst",
    "oracle financial consultant",
    "oracle financial consultant -general ledger lead",
    "oracle financial functional analyst",
    "oracle financial functional consultant",
    "oracle financials",
    "oracle financials analyst",
    "oracle financials business analyst",
    "oracle financials consultant",
    "oracle financials functional",
    "oracle financials functional analyst",
    "oracle financials functional analyst/project management office",
    "oracle financials functional consultant",
    "oracle financials functional lead",
    "oracle financials techno functional consultant",
    "oracle financls functional analyst",
    "oracle forms & pl/sql developer",
    "oracle functional analyst",
    "oracle functional bsa",
    "oracle functional consultant",
    "oracle functional cosultant",
    "oracle functional lead consutlant",
    "oracle fusion cloud consultant",
    "oracle fusion cloud hcm",
    "oracle fusion cloud hcm technical consultant",
    "oracle fusion consultant",
    "oracle fusion financial functional consultant",
    "oracle fusion functional consultant",
    "oracle fusion hcm cloud & taleo implementation specialist",
    "oracle fusion hcm consultant, project lead",
    "oracle fusion hcm functional consultant",
    "oracle fusion middleware (soa/bpm) consultant",
    "oracle fusion middleware / release engineer",
    "oracle fusion middleware / soa/ weblogic admin",
    "oracle fusion middleware administrator",
    "oracle fusion middleware soa administrator",
    "oracle fusion middleware weblogic-soa administrator",
    "oracle hcm cloud consultant",
    "oracle hcm cloud techno-functional lead",
    "oracle hcm consultant",
    "oracle hcm functional analyst",
    "oracle hcm payroll analyst",
    "oracle hrms consultant",
    "oracle identify management (oim) - consultant",
    "oracle identity & access manager 11g r2 /siteminder administrator",
    "oracle identity management consultant",
    "oracle identity management, java/j2ee engineer",
    "oracle identity manager consultant",
    "oracle identity nager consultant",
    "oracle idm consultant",
    "oracle lead",
    "oracle lead & senior trainer",
    "oracle lead developer",
    "oracle lead financials functional analyst",
    "oracle oic technical consultant",
    "oracle order to cash functional consultant",
    "oracle osb developer",
    "oracle p/sql developer",
    "oracle pl/sql /apex developer",
    "oracle pl/sql developer",
    "oracle pl/sql developer / database administrator",
    "oracle pl/sql developer profile",
    "oracle pl/sql developer/support/production engineer",
    "oracle pl/sql lead",
    "oracle production database administrator",
    "oracle programmer",
    "oracle project & financial functional consultant",
    "oracle projects functional consultant",
    "oracle r12 ebs developer",
    "oracle rac database administrator",
    "oracle retail technical consultant",
    "oracle scm consultant",
    "oracle scm functional analyst",
    "oracle senior database administrator/ oracle application developer/ oracle soa developer/ informatica power center developer",
    "oracle senior. scm techno functional consultant",
    "oracle senior. software engineer",
    "oracle siebel ctms (eclinical / oracle siebel ctms)",
    "oracle sme/senior. oracle database administrator",
    "oracle soa",
    "oracle soa / weblogic administrator",
    "oracle soa bpel developer",
    "oracle soa consultant",
    "oracle soa developer",
    "oracle soa lead",
    "oracle soa lead, java developer (fusion middleware)",
    "oracle soa lead/systems architect",
    "oracle soa sme, service transition lead.",
    "oracle soa suite developer",
    "oracle soa-bpel developer",
    "oracle soa-osb developer",
    "oracle soa/b2b developer",
    "oracle soa/bpel/osb developer",
    "oracle soa/bpel/sql developer",
    "oracle soa/bpm developer",
    "oracle soa/odi/report lead developer",
    "oracle soa/osb developer",
    "oracle soa/osb/bam lead (fusion middleware)",
    "oracle software engineer",
    "oracle specialist",
    "oracle sql database administrator profile",
    "oracle sql, pl/sql developer",
    "oracle technical consultant",
    "oracle technical lead",
    "oracle techno functional consultant",
    "oracle techno-functional analyst",
    "oracle techno-functional consultant",
    "oracle techno-functional consultant & on-site co-ordinator",
    "oracle vcp production support",
    "oracle warehouse management solution architect",
    "oracle weblogic/soa admin",
    "oracle xml gate architect",
    "oracle/ sql server database administrator",
    "oracle/aws database administrator",
    "oracle/microstrategy architect",
    "oracle/mysql database administrator",
    "oracle/obiee data warehousing data modeler & etl architect & developer (technical lead)",
    "oracle/sql database admin",
    "oracle/sql database administrator",
    "oracle/teradata database administrator",
    "oralce pl/sql developer"]
    
    # Run retrieval test
    results = await test_retrieval(
        resume_dict=resume_dict,
        job_description=job_description,
        job_roles=job_roles,
        top_k_summary=3,
        top_k_skills=3,
        top_k_experience=12,
        semantic_weight=0.7,
        keyword_weight=0.3
    )
    
    # Print results
    print_results(results, show_data=True)
    
    # Optionally save to file
    print("\n" + "=" * 80)
    print("Saving results to test_retrieval_results.json...")
    with open("test_retrieval_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("✓ Results saved!")


if __name__ == "__main__":
    asyncio.run(main())

