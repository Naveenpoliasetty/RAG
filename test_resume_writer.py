"""
Test script for resume_writer module.
This script allows you to test the resume_writer by providing a sample resume dictionary.
"""

from src.generation.resume_writer import create_resume, generate_and_upload_resume
import json
import os


def test_resume_writer(resume_data: dict, upload_to_gcs: bool = False):
    """
    Test the resume_writer with the provided resume data.
    
    Args:
        resume_data (dict): The resume data dictionary
        upload_to_gcs (bool): Whether to upload to GCS or just create locally
    
    Returns:
        dict: Result containing file paths
    """
    print("=" * 80)
    print("Testing Resume Writer")
    print("=" * 80)
    
    print("\n1. Validating input data...")
    required_fields = ["name", "email", "phone_number", "professional_summary", 
                       "technical_skills", "experiences"]
    
    for field in required_fields:
        if field not in resume_data:
            raise ValueError(f"Missing required field: {field}")
    
    print("✓ All required fields present")
    
    print("\n2. Validating professional_summary...")
    if not isinstance(resume_data["professional_summary"], list):
        raise ValueError("professional_summary must be a list")
    print(f"✓ Found {len(resume_data['professional_summary'])} summary points")
    
    print("\n3. Validating technical_skills...")
    if not isinstance(resume_data["technical_skills"], dict):
        raise ValueError("technical_skills must be a dictionary")
    print(f"✓ Found {len(resume_data['technical_skills'])} skill categories")
    
    print("\n4. Validating experiences...")
    if not isinstance(resume_data["experiences"], list):
        raise ValueError("experiences must be a list")
    
    exp_required_fields = ["client_name", "duration", "job_role", "responsibilities"]
    for i, exp in enumerate(resume_data["experiences"]):
        for field in exp_required_fields:
            if field not in exp:
                raise ValueError(f"Experience {i+1}: Missing required field '{field}'")
        if not isinstance(exp["responsibilities"], list):
            raise ValueError(f"Experience {i+1}: responsibilities must be a list")
    
    print(f"✓ Found {len(resume_data['experiences'])} experiences")
    
    print("\n5. Creating resume document...")
    if upload_to_gcs:
        result = generate_and_upload_resume(resume_data)
        print("✓ Resume created and uploaded to GCS")
        print(f"\n  Local file: {result['local_file']}")
        print(f"  GCS URL: {result['gcs_url']}")
    else:
        local_file = create_resume(resume_data)
        result = {"local_file": local_file}
        print(f"✓ Resume created locally: {local_file}")
    
    print("\n" + "=" * 80)
    print("Test completed successfully!")
    print("=" * 80)
    
    return result


if __name__ == "__main__":
    # Sample resume data structure
    # Replace this with your expected dictionary
    sample_resume_data ={
        "name": "Aasreetha Saggu",
        "phone_number": "469-901-5194",
        "email": "aasreetharao@gmail.com",
        "url": None,
        "designation": "SR. SAP Consultant",
        "professional_summary": [
            "Over 11+ years of experience in development, maintenance, and implementation of Oracle and data warehousing projects.",
            "Hands-on experience in software development methodology and practices, including Agile Methodologies.",
            "Extensive experience in RDBMS concepts with Oracle9i/10g, PL/Sql, core Java, JDBC, Aga (Advent Global Area), RSLs, and UNIX shell scripting.",
            "Experience with ETI, Informatica, Toad, PL/SQL Developer, Eclipse, and Advent Geneva.",
            "Strong background in designing database schemas, handling large databases, and developing data transformations independently.",
            "Extensive experience in performance tuning of Oracle components.",
            "Experience in design and development of multi-tier applications using Java, J2EE, XML, HTML, JavaScript, Tag Libraries, and JUnit.",
            "Experience in web application design using MVC, Spring, and Struts Frameworks.",
            "Strong combination of business analysis, development, and debugging experience in Oracle components, handling performance issues, and exposure to Oracle Apps (O2C and P2P).",
            "Proficient in development and maintenance of applications in financial & capital markets and supply chain domains.",
            "Excellent verbal and written communication skills, with experience leading and mentoring teams, and interacting with clients for scoping, effort estimates, and status reporting.",
            "Implementation and customization expertise in Oracle Sales Cloud modules, including Leads, Opportunities, Accounts, Contacts, and Forecasting.",
            "Strong understanding of sales automation processes and CRM best practices.",
            "Knowledge of OIC, Groovy scripting, and REST/SOAP integrations is a plus.",
            "Proven ability to gather business requirements and translate them into functional solutions.",
            "Experience in developing custom reports and dashboards using OTBI/BIP.",
            "Collaboration and integration expertise with technical teams for integrations and data migration.",
            "Excellent problem-solving skills and ability to provide end-user training, documentation, and post-implementation support."
        ],
        "technical_skills": {
            "Programming Languages & Scripting": [
                "PL/SQL",
                "core java",
                "Groovy"
            ],
            "Databases": [
                "Oracle",
                "AGA (advent global area)"
            ],
            "Platform": [
                "UNIX",
                "Linux",
                "Windows",
                "Solaris"
            ],
            "Tools": [
                "ETI",
                "Informatica",
                "eclipse",
                "tortoise SVN",
                "apache ant",
                "Advent Geneva"
            ],
            "Application Tools": [
                "Toad",
                "PL/SQL Developer",
                "MS Visual Studio"
            ],
            "Integration": [
                "OIC",
                "REST/SOAP"
            ],
            "Reporting & Analytics": [
                "OTBI/BIP"
            ]
        },
        "experiences": [
            {
                "client_name": "Best buy Richfield, MN",
                "duration": "Jul 2021 – Present",
                "job_role": "Oracle Sales Cloud Consultant",
                "responsibilities": [
                    "Designed and developed Oracle database components (Packages, procedures, functions) to meet client requirements, resulting in 30% improvement in database performance.",
                    "Integrated the database layer from source to target systems via Oracle Golden Gate, ensuring seamless data transfer and reducing data latency by 25%.",
                    "Developed and implemented a file upload module to enhance user experience, resulting in a 40% increase in user engagement.",
                    "Configured Single Sign On and integrated it with ServiceNow to streamline request management, reducing request processing time by 35%.",
                    "Designed and developed reports for a 360-degree view and event tracking using dynamic SQL, providing business stakeholders with actionable insights and improving decision-making by 25%.",
                    "Set up cron jobs in Linux servers for data extraction and loading to upstream and downstream applications, ensuring timely data refresh and reducing data inconsistencies by 20%.",
                    "Developed custom reports and dashboards using OTBI/BIP to provide business stakeholders with real-time insights and improving decision-making by 30%.",
                    "Collaborated with technical teams for integrations and data migration, ensuring smooth system transitions and reducing downtime by 25%.",
                    "Provided end-user training, documentation, and post-implementation support, resulting in 95% user adoption and 90% user satisfaction.",
                    "Translated business requirements into functional solutions, ensuring 100% accuracy and meeting client expectations.",
                    "Implemented and configured Oracle Sales Cloud modules (Leads, Opportunities, Accounts, Contacts, and Forecasting) to enhance sales performance and improving sales productivity by 20%.",
                    "Gathered business requirements and worked closely with stakeholders to configure the system, ensuring seamless integration with other Oracle and third-party applications.",
                    "Developed custom solutions to meet client needs, resulting in 40% increase in client satisfaction and 30% increase in client retention.",
                    "Improved data quality by 25% through data validation functions and data transformations in ETL tools, ensuring accurate data reporting and analysis.",
                    "Designed and developed database schemas to meet client requirements, resulting in 20% improvement in database performance and 15% reduction in database size.",
                    "Developed and implemented reporting applications for status monitoring of system logs and debugging, providing business stakeholders with real-time insights and improving decision-making by 25%.",
                    "Provided alternate solutions for business users to maintain data transformation, resulting in 30% reduction in data inconsistencies and 25% improvement in data quality.",
                    "Designed new functionality to meet changing business requirements, resulting in 40% increase in user engagement and 30% improvement in user satisfaction."
                ],
                "environment": "Oracle 12c, Pl/Sql, Toad, Oracle Golden Gate, JDK 1.7, Ant build, Tortoise SVN, Eclipse, Apache Tomcat, UNIX shell scripting, Jenkins GIT, JIRA"
            },
            {
                "client_name": "Caterpillar Inc, Irving, Texas",
                "duration": "May 2019 – Jun 2021",
                "job_role": "Oracle Sales Cloud Consultant",
                "responsibilities": [
                    "Developed and implemented Oracle Sales Cloud modules (Leads, Opportunities, Accounts, Contacts, and Forecasting) to enhance sales automation processes and CRM best practices.",
                    "Translated business requirements into functional solutions, ensuring seamless integration with other Oracle and third-party applications.",
                    "Configured and customized Oracle Sales Cloud to meet specific business needs, resulting in improved sales performance and customer satisfaction.",
                    "Collaborated with technical teams for integrations and data migration, ensuring smooth transition and minimal disruption to business operations.",
                    "Provided end-user training, documentation, and post-implementation support to ensure effective adoption and utilization of Oracle Sales Cloud.",
                    "Developed custom reports and dashboards using OTBI/BIP, providing actionable insights and enhancing decision-making capabilities.",
                    "Analyzed sales data and identified areas for improvement, implementing process changes to increase sales efficiency and effectiveness.",
                    "Designed and developed custom adapters for accounting and performance calculations, ensuring accurate and timely data processing.",
                    "Developed and maintained data transformations in Informatica, ensuring data integrity and consistency across systems.",
                    "Created and implemented tools for data comparison and validation, ensuring accurate and reliable data migration and upgradation.",
                    "Developed custom reports in Geneva for PnL analysis, portfolio positions, and trades, providing critical insights for business decision-making.",
                    "Migrated Advent Geneva from version 7.6 to version 14.2, ensuring seamless transition and minimal disruption to business operations.",
                    "Designed and developed stored procedures and triggers using PL/SQL, enhancing database performance and security.",
                    "Implemented software development life cycle using agile methodologies, ensuring timely and effective delivery of projects.",
                    "Managed data coming from different sources, ensuring accurate and timely data processing and analysis.",
                    "Analyzed data and made required changes to PUTs/GETs components, ensuring smooth run of loads and extracts.",
                    "Participated in all phases of development, including system study, analysis, design, development, deployment, testing, and maintenance.",
                    "Tracked and worked on assignation to team, ensuring effective project management and collaboration."
                ],
                "environment": "Oracle Apps 11, Oracle 9i, PL/SQL, Data Load, UNIX, QTP, Oracle Sales Cloud, OTBI/BIP, Informatica, Geneva 6.0.6/7.6/14.2, AGA (advent global area), RSLs, RDLs"
            },
            {
                "client_name": "Fortis Healthcare, Gurgaon, India",
                "duration": "Aug 2017 – Jan 2019",
                "job_role": "Oracle Sales Cloud Consultant",
                "responsibilities": [
                    "Designed and implemented custom reports using OTBI/BIP, resulting in a 30% reduction in reporting time for business users.",
                    "Configured Oracle Sales Cloud modules, including Leads, Opportunities, Accounts, Contacts, and Forecasting, ensuring seamless integration with other Oracle and third-party applications.",
                    "Translated business requirements into functional solutions, collaborating closely with stakeholders to ensure accurate and efficient system implementation.",
                    "Provided end-user training, documentation, and post-implementation support, ensuring a smooth transition for business users and minimizing disruption to operations.",
                    "Collaborated with technical teams for integrations and data migration, leveraging expertise in OIC, Groovy scripting, and REST/SOAP integrations to ensure successful data transfer.",
                    "Developed and implemented custom dashboards, providing real-time insights and analytics to business stakeholders, resulting in improved decision-making and enhanced business outcomes.",
                    "Ensured seamless integration with other Oracle and third-party applications, utilizing expertise in Oracle Golden Gate and data mapping to optimize system performance.",
                    "Designed and implemented Single Sign-On and service-now integration, streamlining user authentication and request management processes.",
                    "Developed and implemented data validation functions, ensuring data integrity and accuracy, and reducing errors by 25%.",
                    "Designed and developed database schemas, leveraging expertise in Oracle 12c and Pl/SQL to optimize data storage and retrieval.",
                    "Developed and implemented data transformations in ETL tools, extracting and loading data efficiently and accurately, resulting in a 40% reduction in data processing time.",
                    "Integrated flat files and XML files using data mapping, ensuring seamless data transfer and reducing errors by 20%.",
                    "Designed and developed reporting applications for status monitoring of system logs and debugging, providing real-time insights and analytics to technical teams.",
                    "Implemented the system in MVC architecture using the Struts framework, ensuring scalability, maintainability, and efficient system performance.",
                    "Provided alternate solutions for business users, maintaining data transformation and ensuring data accuracy and integrity.",
                    "Designed new functionality for changing business requirements, collaborating closely with stakeholders to ensure accurate and efficient system implementation.",
                    "Unit tested components using JUnit and integration testing, ensuring high-quality code and minimizing bugs.",
                    "Developed and implemented data validation functions for client-side validation, ensuring data accuracy and integrity, and reducing errors by 30%.",
                    "Designed and implemented system log monitoring and debugging, providing real-time insights and analytics to technical teams, resulting in a 50% reduction in system downtime."
                ],
                "environment": "Oracle 12c, Pl/Sql, OTBI/BIP, OIC, Groovy scripting, REST/SOAP integrations, Oracle Golden Gate, data mapping, Jdk1.7, Ant build, tortoise svn, eclipse, apache tomcat, UNIX shell scripting, Jenkins GIT, JIRA"
            },
            {
                "client_name": "Amway Corp, New Delhi, India",
                "duration": "Jun 2014– Jul 2017",
                "job_role": "Oracle Sales Cloud Consultant",
                "responsibilities": [
                    "Designed and developed custom reports and dashboards using OTBI/BIP to provide business stakeholders with real-time insights and data-driven decisions, resulting in a 25% increase in sales team productivity.",
                    "Configured Oracle Sales Cloud modules, including Leads, Opportunities, Accounts, Contacts, and Forecasting, to ensure seamless integration with other Oracle and third-party applications, reducing integration errors by 30%.",
                    "Collaborated with technical teams for integrations and data migration, ensuring smooth data transfer and minimal downtime, resulting in a 99.9% uptime rate.",
                    "Provided end-user training, documentation, and post-implementation support to ensure effective adoption and utilization of Oracle Sales Cloud, resulting in a 95% user satisfaction rate.",
                    "Translated business requirements into functional solutions, leveraging expertise in sales automation processes and CRM best practices, resulting in a 20% increase in sales revenue.",
                    "Developed and maintained adapters for accounting and performance calculations, ensuring accurate and timely data processing, resulting in a 15% reduction in data processing time.",
                    "Handled performance issues related to accounting and performance run times, implementing optimized solutions that resulted in a 25% improvement in system performance.",
                    "Reconciled data between trading systems, Geneva, and pace applications, ensuring data consistency and accuracy, resulting in a 99.5% data reconciliation rate.",
                    "Developed and maintained data transformations in Informatica, ensuring efficient data transfer and minimal data loss, resulting in a 98% data transformation success rate.",
                    "Maintained adapters that loaded data into Geneva, running RSLs automatically and sending data to downstream systems for reporting purposes, resulting in a 95% data loading success rate.",
                    "Developed a utility to calculate performance data (DTD, MTD, QTD, YTD) using Daily Cumulative IRR Data, providing business stakeholders with real-time insights and data-driven decisions, resulting in a 25% increase in sales team productivity.",
                    "Developed tools for data comparison in migration and upgradation, running RSLs on both systems and comparing extracts for data verification and validation, resulting in a 99.9% data comparison success rate.",
                    "Developed tools that reported the status of everyday accounting, providing business stakeholders with real-time insights and data-driven decisions, resulting in a 20% increase in sales revenue.",
                    "Developed custom reports in Geneva for PnL analysis, portfolio positions, and lots, trades, non-trades, corporate actions, realized gain/loss reports, and change in net assets, resulting in a 25% increase in sales team productivity.",
                    "Migrated Advent Geneva from version 7.6 to version 14.2, ensuring seamless transition and minimal downtime, resulting in a 99.9% uptime rate.",
                    "Developed and implemented custom reporting solutions using OTBI/BIP, providing business stakeholders with real-time insights and data-driven decisions, resulting in a 25% increase in sales team productivity.",
                    "Configured and customized Oracle Sales Cloud applications to meet specific business requirements, resulting in a 20% increase in sales revenue.",
                    "Provided expert-level support and training to business stakeholders on Oracle Sales Cloud applications, ensuring effective adoption and utilization, resulting in a 95% user satisfaction rate.",
                    "Collaborated with cross-functional teams to identify and prioritize business requirements, ensuring that Oracle Sales Cloud applications met specific business needs, resulting in a 25% increase in sales team productivity."
                ],
                "environment": "Oracle Sales Cloud, Oracle CX Sales, OTBI/BIP, Informatica, Java, Ant build, tortoise svn, eclipse, UNIX shell scripting, Geneva 6.0.6/7.6/14.2, AGA (advent global area), RSLs, RDLs."
            }
        ],
        "education": [
            "Jawaharlal Nehru Technology University, Hyderabad, TS, India",
            "BTech in Computer Science and Engineering, June 2010 – May 2014"
        ]
    }
    
    print("\n" + "=" * 80)
    print("RESUME DATA STRUCTURE")
    print("=" * 80)
    print(json.dumps(sample_resume_data, indent=2))
    print("\n")
    
    # You can modify this to use your own expected dictionary:
    # Option 1: Replace sample_resume_data above with your data
    # Option 2: Load from a JSON file
    # with open('your_resume_data.json', 'r') as f:
    #     resume_data = json.load(f)
    
    # Test without uploading to GCS (set to True to upload)
    try:
        result = test_resume_writer(sample_resume_data, upload_to_gcs=False)
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
