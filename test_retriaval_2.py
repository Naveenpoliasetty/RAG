#!/usr/bin/env python3
"""
Clean test script for validating the NEW retrieval pipeline:

    match_resumes_keyword_then_semantic()

Usage:

    python test_new_pipeline.py

or programmatically:

    from test_new_pipeline import quick_test

    results = quick_test(
        job_description="...",
        job_roles=["oracle consultant"],
        top_k=3
    )
"""

import asyncio
import json
from typing import Dict, Any, List

from src.core.db_manager import get_qdrant_manager, get_mongodb_manager
from src.retriever.get_ids import ResumeIdsRetriever
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_new_retrieval(
    job_description: str,
    job_roles: List[str],
    top_k: int = 3
) -> Dict[str, Any]:
    """
    Test ONLY the new keyword-first → semantic-next retrieval pipeline.
    """

    print("=" * 80)
    print("NEW RETRIEVAL PIPELINE TEST")
    print("=" * 80)

    # ----------------------------------------------------------
    # 1. Initialize DB managers
    # ----------------------------------------------------------
    print("\n[1] Initializing database connections...")
    qdrant_manager = get_qdrant_manager()
    mongodb_manager = get_mongodb_manager()
    retriever = ResumeIdsRetriever(
        mongo_manager=mongodb_manager,
        qdrant_manager=qdrant_manager
    )
    print("✓ Connections established")

    # ----------------------------------------------------------
    # 2. Filter resumes by job roles
    # ----------------------------------------------------------
    print(f"\n[2] Filtering resumes by job roles: {job_roles}")
    filtered_resume_object_ids = retriever.get_resume_ids_by_job_roles(job_roles)
    filtered_resume_ids = [str(oid) for oid in filtered_resume_object_ids]
    print(f"✓ Found {len(filtered_resume_ids)} resumes matching job roles")

    if not filtered_resume_ids:
        print("⚠️ No resumes found for these job roles!")
        return {
            "filtered_resume_ids": [],
            "final_results": [],
            "final_data": []
        }

    # ----------------------------------------------------------
    # 3. Run the NEW retrieval pipeline
    # ----------------------------------------------------------
    print(f"\n[3] Running NEW retrieval pipeline (top_k={top_k})...")
    final_results = qdrant_manager.match_resumes_keyword_then_semantic(
        job_description=job_description,
        resume_ids_filter=filtered_resume_ids,
        top_k=top_k
    )

    if not final_results:
        print("⚠️ Retrieval returned no results!")
        return {
            "filtered_resume_ids": filtered_resume_ids,
            "final_results": [],
            "final_data": []
        }

    final_rids = [rid for rid, score in final_results]
    print(f"✓ Final top {len(final_rids)} resumes: {final_rids}")

    print("\nTop scores:")
    for rid, score in final_results:
        print(f"   - Resume {rid}: {score:.4f}")

    # ----------------------------------------------------------
    # 4. Fetch MongoDB data for final resumes
    # ----------------------------------------------------------
    print("\n[4] Fetching data from MongoDB...")
    final_data = mongodb_manager.get_sections_by_resume_ids(final_rids, "professional_summary")
    print(f"✓ Retrieved {len(final_data)} documents")

    # ----------------------------------------------------------
    # 5. Compile results
    # ----------------------------------------------------------
    results = {
        "input": {
            "job_description": job_description,
            "job_roles": job_roles,
            "top_k": top_k
        },
        "filtered_resume_ids": filtered_resume_ids,
        "final_results": final_results,
        "final_data": final_data
    }

    return results


def print_results(results: Dict[str, Any], show_data: bool = True):
    """Pretty-print pipeline results."""

    print("\n" + "=" * 80)
    print("NEW RETRIEVAL PIPELINE RESULTS")
    print("=" * 80)

    print(f"\nFiltered Resume IDs ({len(results['filtered_resume_ids'])}):")
    print(f"  {results['filtered_resume_ids'][:10]}")

    final = results["final_results"]
    if not final:
        print("\n⚠️ No results returned.")
        return

    print("\nTop Final Resumes:")
    for rid, score in final:
        print(f"  - {rid}: {score:.4f}")

    if show_data:
        print("\n" + "=" * 80)
        print("RETRIEVED MONGODB DATA (first few)")
        print("=" * 80)

        for doc in results["final_data"][:5]:
            print(f"\nResume ID: {doc.get('resume_id')}")
            for k, v in doc.items():
                if k != "resume_id":
                    print(f"  {k}: {str(v)[:200]}...")


def quick_test(
    job_description: str,
    job_roles: List[str],
    top_k: int = 3,
    show_data: bool = True,
    save_to_file: bool = True
) -> Dict[str, Any]:
    """
    Run new retrieval test from other scripts.
    """

    results = asyncio.run(
        test_new_retrieval(job_description, job_roles, top_k)
    )

    print_results(results, show_data=show_data)

    if save_to_file:
        print("\nSaving results → test_new_pipeline_results.json")
        with open("test_new_pipeline_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        print("✓ Saved")

    return results


async def main():
    """Main entry point for command-line usage."""

    # Load example resume dictionary (optional, not used)
    try:
        with open("/Users/naveenpoliasetty/Downloads/RAG-1/resume_text.json") as f:
            resume_dict = json.load(f)
    except:
        resume_dict = {}

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

    results = await test_new_retrieval(
        job_description=job_description,
        job_roles=job_roles,
        top_k=3
    )

    print_results(results, show_data=True)

    with open("test_new_pipeline_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    asyncio.run(main())