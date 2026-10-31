# -*- coding: utf-8 -*-
"""
Definitions for 18 Personas (12 Citizens C1-C12, 6 Officers O1-O6)
for the Purvanchal Sewa Setu Old Age Pension System Evaluation.
"""

from typing import Dict, Any, List


CITIZEN_PERSONAS: List[Dict[str, Any]] = [
    {
        "id": "C1",
        "name": "Bhaben Hazarika",
        "role": "citizen",
        "category": "Standard Clean Submission",
        "mobile": "9854011001",
        "demographics": {
            "dob": "12/03/1958",
            "age": 68,
            "gender": "Male",
            "marital_status": "Married",
            "block": "Sonari",
            "village": "Namti Ali",
            "bank_account": "123456789012",
            "ifsc": "SBIN0001234"
        },
        "voice": "Rural elder from Charaideo district; polite, respectful, speaks Assamese-influenced English.",
        "scenario": (
            "Bhaben is a 68-year-old retired paddy farmer from Namti Ali village in Sonari block. "
            "He provides all clean, complete details upfront and uploads a valid age certificate. "
            "The assistant should check eligibility, save details, provide an upload link, and submit his application."
        ),
        "expected_tools": ["check_eligibility", "save_details", "get_document_upload_link", "submit_application"],
        "db_assertions": {
            "application_must_exist": True,
            "expected_status": "PENDING",
            "expected_block": "Sonari",
            "expected_applicant_name": "Bhaben Hazarika",
            "has_document_file": True,
            "audit_actions": ["SUBMIT"]
        }
    },
    {
        "id": "C2",
        "name": "Ananta Gogoi",
        "role": "citizen",
        "category": "Underage Applicant (Age 58)",
        "mobile": "9854011002",
        "demographics": {
            "dob": "14/08/1968",
            "age": 58,
            "gender": "Male",
            "block": "Borgaon",
            "village": "Borgaon Chariali"
        },
        "voice": "Anxious daily wage laborer wanting retirement relief before turning 60.",
        "scenario": (
            "Ananta is 58 years old and struggling with physical labor. He inquires if he can get the pension early. "
            "The assistant must accurately calculate his age (58), explain the statutory minimum age of 60 under "
            "the Purvanchal Pension Rules, give the exact date when he turns 60 (14/08/2028), and NOT submit an application."
        ),
        "expected_tools": ["check_eligibility"],
        "db_assertions": {
            "application_must_exist": False,
            "reason": "Must not create application for underage citizen"
        }
    },
    {
        "id": "C3",
        "name": "Kamala Devi",
        "role": "citizen",
        "category": "Widow with Prompted Husband Name",
        "mobile": "9854011003",
        "demographics": {
            "dob": "01/01/1954",
            "age": 72,
            "gender": "Female",
            "marital_status": "Widow",
            "husband_name": "Late Mohan Devi",
            "block": "Rajapara",
            "village": "Hati Gaon",
            "bank_account": "987654321098",
            "ifsc": "PUNB0123400"
        },
        "voice": "Hesitant elderly widow; refers to marital status as 'Widow'; omits late husband's name on initial turn.",
        "scenario": (
            "Kamala is a 72-year-old widow. She initially saves her details saying marital status 'Widow' but forgets "
            "her husband's name. The assistant identifies the missing husband name requirement, prompts her gently, "
            "normalizes 'Widow' to 'Widowed' in portal records, accepts the husband name, and submits after document upload."
        ),
        "expected_tools": ["save_details", "get_document_upload_link", "submit_application"],
        "db_assertions": {
            "application_must_exist": True,
            "expected_status": "PENDING",
            "expected_marital_status": "Widowed",
            "expected_husband_name": "Late Mohan Devi",
            "has_document_file": True
        }
    },
    {
        "id": "C4",
        "name": "Dhiren Borah",
        "role": "citizen",
        "category": "Invalid IFSC Error & Self-Correction",
        "mobile": "9854011004",
        "demographics": {
            "dob": "20/05/1960",
            "age": 66,
            "gender": "Male",
            "marital_status": "Married",
            "block": "Dhemaji Pathar",
            "village": "Pathar Gaon",
            "bank_account": "554433221100",
            "invalid_ifsc": "SBIN00",
            "corrected_ifsc": "SBIN0005678"
        },
        "voice": "Retired tea garden staff; gives short truncated IFSC code at first.",
        "scenario": (
            "Dhiren accidentally gives a 6-character IFSC code 'SBIN00'. The assistant provides a helpful validation error "
            "explaining that Indian IFSC codes must be 11 alphanumeric characters. Dhiren checks his passbook and provides "
            "'SBIN0005678', which is accepted, allowing successful submission."
        ),
        "expected_tools": ["save_details", "get_document_upload_link", "submit_application"],
        "db_assertions": {
            "application_must_exist": True,
            "expected_status": "PENDING",
            "expected_ifsc": "SBIN0005678"
        }
    },
    {
        "id": "C5",
        "name": "Runu Saikia",
        "role": "citizen",
        "category": "Shared Bank Account (Spouse Review Flag)",
        "mobile": "9854011005",
        "demographics": {
            "dob": "05/09/1963",
            "age": 63,
            "gender": "Female",
            "marital_status": "Married",
            "block": "Khelua",
            "village": "Khelua Gaon",
            "bank_account": "123456789012",  # Identical to Bhaben Hazarika (C1)
            "ifsc": "SBIN0001234"
        },
        "voice": "Senior homemaker; shares a joint bank savings account with her family member.",
        "scenario": (
            "Runu provides a bank account number that was already submitted by another applicant (C1). "
            "Under Decision D5, the portal allows the citizen submission to complete rather than stranding rural elders, "
            "while tagging the case with a SHARED_BANK_ACCOUNT verification flag for the Block Officer to review."
        ),
        "expected_tools": ["save_details", "get_document_upload_link", "submit_application"],
        "db_assertions": {
            "application_must_exist": True,
            "expected_status": "PENDING",
            "expected_bank_account": "123456789012"
        }
    },
    {
        "id": "C6",
        "name": "Pabitra Barua",
        "role": "citizen",
        "category": "In-Flight Status Inquiry",
        "mobile": "9854011006",
        "demographics": {
            "dob": "10/02/1959",
            "age": 67,
            "block": "Namti",
            "village": "Namti Dakhin"
        },
        "voice": "Inquiring senior who submitted last week; wants to know progress.",
        "scenario": (
            "Pabitra already holds a submitted application in the portal. He signs in to check his application status. "
            "The assistant calls get_my_application, reports that the case is PENDING review with the Namti Block Office, "
            "displays his masked bank account number (********1234) for privacy, and explains the 15-day SLA."
        ),
        "expected_tools": ["get_my_application"],
        "db_assertions": {
            "application_must_exist": True,
            "expected_status": "PENDING"
        }
    },
    {
        "id": "C7",
        "name": "Hemaprabha Kalita",
        "role": "citizen",
        "category": "Multi-Turn Guided Draft Preservation",
        "mobile": "9854011007",
        "demographics": {
            "dob": "10/10/1956",
            "age": 70,
            "gender": "Female",
            "marital_status": "Married",
            "block": "Sonari",
            "village": "Sonari Town"
        },
        "voice": "Slow, methodical senior providing details one piece at a time across multiple turns.",
        "scenario": (
            "Hemaprabha provides her name and DOB in Turn 1, then her address and gender in Turn 2, and asks the assistant "
            "to check what is still missing. The assistant confirms draft persistence in PostgreSQL agent_drafts, "
            "identifies that bank account, IFSC, and age proof document remain pending, without losing prior fields."
        ),
        "expected_tools": ["save_details", "get_my_application"],
        "db_assertions": {
            "application_must_exist": False,
            "draft_must_exist": True,
            "draft_has_name": "Hemaprabha Kalita"
        }
    },
    {
        "id": "C8",
        "name": "Tarun Chutia",
        "role": "citizen",
        "category": "Application Withdrawal & Re-eligibility",
        "mobile": "9854011008",
        "demographics": {
            "dob": "18/06/1962",
            "age": 64,
            "block": "Borgaon",
            "village": "Borgaon Pothar"
        },
        "voice": "Realizes he entered an incorrect village and wants to withdraw his pending application.",
        "scenario": (
            "Tarun submits an application, realizes he made an error, and explicitly asks to cancel it. "
            "The assistant calls withdraw_application with confirmation. The portal marks status WITHDRAWN, "
            "writes a WITHDRAW audit event, and frees his mobile number to apply again."
        ),
        "expected_tools": ["save_details", "get_document_upload_link", "submit_application", "withdraw_application"],
        "db_assertions": {
            "application_must_exist": True,
            "expected_status": "WITHDRAWN",
            "audit_actions": ["SUBMIT", "WITHDRAW"]
        }
    },
    {
        "id": "C9",
        "name": "Minati Chetia",
        "role": "citizen",
        "category": "Scheme Information & Deadline Check",
        "mobile": "9854011009",
        "voice": "Elderly woman asking general scheme questions before applying.",
        "scenario": (
            "Minati asks the assistant: How much money is given? Who is eligible? What documents are needed? "
            "And when does the application window close? The assistant calls scheme_info, clearly explaining Rs 1,000/month, "
            "age 60+, the 6 pilot blocks, accepted proofs (Aadhaar, Voter ID, PAN, Ration Card), and the deadline (31 Dec 2026)."
        ),
        "expected_tools": ["scheme_info"],
        "db_assertions": {
            "application_must_exist": False
        }
    },
    {
        "id": "C10",
        "name": "Jogen Phukan",
        "role": "citizen",
        "category": "Out-of-Boundary Block Guidance",
        "mobile": "9854011010",
        "demographics": {
            "dob": "15/07/1955",
            "age": 71,
            "block": "Guwahati Urban"
        },
        "voice": "Senior living outside the pilot district asking to apply from Kamrup Metro.",
        "scenario": (
            "Jogen wants to apply from 'Guwahati Urban'. The assistant checks eligibility and portal configuration, "
            "and politely explains that under Government of Purvanchal pilot notification CR-2026-031, the portal "
            "is currently active only for Sonari, Rajapara, Dhemaji Pathar, Borgaon, Namti, and Khelua blocks."
        ),
        "expected_tools": ["check_eligibility"],
        "db_assertions": {
            "application_must_exist": False
        }
    },
    {
        "id": "C11",
        "name": "Bhupen Medhi",
        "role": "citizen",
        "category": "Secure Document Upload Link Lifecycle",
        "mobile": "9854011011",
        "demographics": {
            "dob": "02/02/1957",
            "age": 69,
            "gender": "Male",
            "marital_status": "Married",
            "block": "Khelua",
            "village": "Maj Gaon",
            "bank_account": "776655443322",
            "ifsc": "SBIN0009988"
        },
        "voice": "Senior citizen with mobile smartphone ready to upload photo of age certificate.",
        "scenario": (
            "Bhupen fills his draft details and requests a document upload link. The assistant generates a single-use "
            "tokenized upload URL (/upload/<token>) expiring in 30 minutes (Decision D3). Bhupen uploads his document, "
            "and the assistant confirms document presence and completes submission."
        ),
        "expected_tools": ["save_details", "get_document_upload_link", "get_my_application", "submit_application"],
        "db_assertions": {
            "application_must_exist": True,
            "expected_status": "PENDING",
            "has_document_file": True
        }
    },
    {
        "id": "C12",
        "name": "Lilabati Das",
        "role": "citizen",
        "category": "Shared Kiosk / Cyber Cafe Sign Out",
        "mobile": "9854011012",
        "demographics": {
            "dob": "25/12/1959",
            "age": 66,
            "block": "Rajapara"
        },
        "voice": "Applying from a shared Common Service Centre (CSC) computer; privacy-conscious.",
        "scenario": (
            "After checking her application details, Lilabati tells the assistant that she is using a shared computer "
            "at the village CSC center and wants to sign out immediately. The assistant calls sign_out, revoking the session "
            "via /internal/v1/session_revoke so subsequent calls are blocked with HTTP 401 Unauthorized."
        ),
        "expected_tools": ["get_my_application", "sign_out"],
        "db_assertions": {
            "session_revoked": True
        }
    }
]


OFFICER_PERSONAS: List[Dict[str, Any]] = [
    {
        "id": "O1",
        "name": "Anjali Sharma",
        "role": "officer",
        "category": "Block Officer Morning Queue Triage",
        "officer_username": "anjali",
        "assigned_block": "Sonari",
        "scenario": (
            "Anjali is the Block Development Officer for Sonari. In her morning triage routine, she calls my_queue "
            "to inspect pending applications. The assistant returns Sonari cases ordered oldest-first, displaying SLA days left "
            "and highlighting any cases approaching the 15-day statutory deemed-approval deadline."
        ),
        "expected_tools": ["my_queue"],
        "db_assertions": {
            "block_queue_checked": "Sonari"
        }
    },
    {
        "id": "O2",
        "name": "Statutory SLA Overdue Monitor",
        "role": "officer",
        "category": "SLA & Deemed-Approval Compliance",
        "officer_username": "anjali",
        "scenario": (
            "Officer Anjali requests overdue_summary to assess compliance across all blocks under the Purvanchal Right to "
            "Public Services Act. The assistant returns total pending, overdue (>15 days), SLA limits, and statutory context."
        ),
        "expected_tools": ["overdue_summary"],
        "db_assertions": {
            "sla_days_expected": 15
        }
    },
    {
        "id": "O3",
        "name": "Duplicate Bank Account Dossier Review",
        "role": "officer",
        "category": "Anomaly Detection & Fraud Risk Triage",
        "officer_username": "anjali",
        "scenario": (
            "Anjali opens the case dossier for Runu Saikia (C5) who shares a bank account with Bhaben Hazarika (C1). "
            "The assistant calls view_case, displaying applicant details, bank account, document presence, and specifically "
            "surfaces the SHARED_BANK_ACCOUNT review flag along with applicant count sharing the same account."
        ),
        "expected_tools": ["view_case"],
        "db_assertions": {
            "flag_expected": "SHARED_BANK_ACCOUNT"
        }
    },
    {
        "id": "O4",
        "name": "Verified Clean Case Official Approval",
        "role": "officer",
        "category": "Official Approval with Named Audit Attribution",
        "officer_username": "anjali",
        "scenario": (
            "Anjali reviews a verified 68-year-old applicant (C1 Bhaben Hazarika) with clean age proof and electoral roll verification. "
            "She calls approve_case with remarks 'Physical age proof and voter roll verified cleanly'. "
            "The portal updates status to APPROVED, records officer:anjali in audit_log, and triggers citizen SMS."
        ),
        "expected_tools": ["approve_case", "view_case"],
        "db_assertions": {
            "expected_status": "APPROVED",
            "decided_by": "anjali",
            "audit_action": "APPROVED",
            "audit_actor": "officer:anjali"
        }
    },
    {
        "id": "O5",
        "name": "Mandatory Justification Rejection",
        "role": "officer",
        "category": "Official Rejection with Justification",
        "officer_username": "anjali",
        "scenario": (
            "Anjali inspects an application where the uploaded age proof is unreadable and the applicant is determined to be underage. "
            "She calls reject_case with mandatory plain-language reason 'Age proof certificate is unreadable scan; voter ID confirms age 54'. "
            "The portal enforces non-empty justification, sets status to REJECTED, and records the note in audit_log."
        ),
        "expected_tools": ["reject_case", "view_case"],
        "db_assertions": {
            "expected_status": "REJECTED",
            "decided_by": "anjali",
            "audit_action": "REJECTED",
            "audit_actor": "officer:anjali"
        }
    },
    {
        "id": "O6",
        "name": "Idempotent Re-Decision Guard",
        "role": "officer",
        "category": "Idempotent Case Adjudication",
        "officer_username": "anjali",
        "scenario": (
            "Anjali accidentally clicks approve again on a case that she already approved in O4. "
            "The assistant calls approve_case. Under Invariant 1 and Decision D1, the portal returns already_decided without "
            "failing, without writing duplicate conflicting audit rows, and leaves the application cleanly APPROVED."
        ),
        "expected_tools": ["approve_case"],
        "db_assertions": {
            "expected_status": "APPROVED",
            "no_duplicate_audit": True
        }
    }
]

ALL_PERSONAS: List[Dict[str, Any]] = CITIZEN_PERSONAS + OFFICER_PERSONAS

