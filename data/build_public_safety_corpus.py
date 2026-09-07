"""Build a paraphrased, provenance-rich public Australian scam-safety corpus.

This creates 60 retrieval chunks from 15 public sources. It deliberately does
not reproduce the source pages or present customer guidance as bank policy.
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).with_name("public_safety_corpus_v1.jsonl")
REVIEW_DATE = "2026-09-07"


def source(publisher, slug, title, url, trust_tier, cards):
    return {"publisher": publisher, "slug": slug, "document_title": title, "source_url": url, "trust_tier": trust_tier, "cards": cards}


# All summaries are original, short paraphrases of public consumer-safety guidance.
SOURCES = [
 source("Scamwatch", "scamwatch_remote_access", "Hang up on remote access scammers", "https://www.scamwatch.gov.au/about-us/news-and-alerts/scam-alert-hang-up-on-remote-access-scammers", "government_primary", [
  ("Unexpected technical support contact", "An unsolicited caller who claims a device, account or phone problem may be trying to establish remote access. Treat the contact as unverified.", ["unexpected call", "technical support", "device problem"], ["credential_compromise", "urgent_review"]),
  ("Remote software signal", "A request to install screen-sharing or remote-desktop software is a high-risk signal, especially when the request comes from an unsolicited caller.", ["AnyDesk", "TeamViewer", "screen sharing", "remote desktop"], ["credential_compromise", "secure_access"]),
  ("Credential protection", "Customers should not disclose banking passwords or one-time codes to someone who called them. Independent verification is safer than continuing the call.", ["password", "one-time code", "caller", "OTP"], ["credential_compromise", "contact_official"]),
  ("Affected customer action", "If money was transferred or banking information was shared, the customer should contact their financial institution promptly using independently sourced contact details.", ["transferred money", "shared details", "contact bank"], ["urgent_review", "contact_official"]),
 ]),
 source("Scamwatch", "bank_impersonation", "Bank impersonation scams", "https://www.scamwatch.gov.au/about-us/news-and-alerts/bank-impersonation-scams-robbing-australians-of-their-life-savings", "government_primary", [
  ("Impersonation urgency", "Messages alleging an account problem or unauthorised payment can be designed to create urgency and prompt a rushed response.", ["account locked", "unauthorised payment", "urgent call"], ["urgent_review", "general_safety"]),
  ("Spoofed identity warning", "A displayed sender name or phone number is not sufficient proof that a message or caller is genuine.", ["spoofed number", "sender ID", "bank caller"], ["contact_official", "general_safety"]),
  ("Independent callback", "End the unexpected interaction and use contact details found independently in the banking app, card, or official website.", ["call back", "official website", "bank app"], ["contact_official"]),
  ("No security codes", "A legitimate-looking request for a password, PIN, token or verification code should not be satisfied through an unsolicited interaction.", ["PIN", "token", "verification code", "password"], ["credential_compromise", "privacy"]),
 ]),
 source("Australian Cyber Security Centre", "phishing", "Phishing", "https://www.cyber.gov.au/threats/types-threats/phishing", "government_primary", [
  ("Phishing channels", "Fraudulent messages can arrive by email, SMS, social media or other channels while impersonating trusted organisations.", ["phishing", "email", "SMS", "social media"], ["general_safety"]),
  ("Account-access targets", "Phishing can target banking logins, card details, account-linking codes and QR-code device linking flows.", ["banking login", "QR code", "card details", "verification code"], ["credential_compromise", "privacy"]),
  ("Clicked versus not clicked", "The recommended response differs between merely receiving a suspicious message and entering information or losing money; capture that distinction during triage.", ["clicked link", "entered details", "lost money"], ["credential_compromise", "urgent_review"]),
  ("Compromise response", "A suspected credential compromise requires securing affected accounts and contacting relevant providers through verified channels.", ["change password", "secure account", "provider"], ["secure_access", "contact_official"]),
 ]),
 source("Australian Cyber Security Centre", "bank_compromise", "Recovering compromised bank and payment accounts", "https://www.cyber.gov.au/report-and-recover/recover-from/account-compromise/bank", "government_primary", [
  ("Compromise indicators", "Suspicious activity, failed logins, leaked credentials, or unauthorised account changes can indicate account compromise even before a confirmed loss.", ["cannot login", "suspicious activity", "leaked password"], ["credential_compromise", "urgent_review"]),
  ("Provider contact", "Customers who suspect a compromise should contact their bank or payment provider promptly and state that account access may be compromised.", ["bank compromised", "payment provider", "contact"], ["contact_official", "urgent_review"]),
  ("Linked service scope", "If a payment account is affected, related services and linked financial instruments may also need review by the responsible provider.", ["linked card", "payment account", "provider"], ["contact_official"]),
  ("Reporting boundary", "The agent can direct customers toward official reporting pathways but must not claim a report or recovery has been completed.", ["report scam", "ReportCyber", "outcome"], ["no_guarantee", "general_safety"]),
 ]),
 source("Scamwatch", "account_takeover", "Account and identity takeover scams", "https://www.scamwatch.gov.au/types-of-scams/account-or-identity-takeover-scams", "government_primary", [
  ("Takeover path", "Data from phishing, breaches, or social platforms can be used to impersonate a person and access financial accounts.", ["identity theft", "data breach", "impersonation"], ["credential_compromise", "privacy"]),
  ("SIM and authentication risk", "Control of a phone number can expose SMS-based account verification, so reports involving number transfers or missing codes warrant caution.", ["SIM swap", "phone number", "SMS code"], ["credential_compromise", "urgent_review"]),
  ("Remote-control consequence", "Remote access can expose open applications and files, making it an escalation-relevant security signal.", ["remote control", "open apps", "files"], ["credential_compromise", "urgent_review"]),
  ("Recovery support", "Customers may need both financial-provider contact and specialist identity/cyber support; triage should not diagnose or perform those recovery steps.", ["identity support", "IDCARE", "recovery"], ["contact_official", "no_guarantee"]),
 ]),
 source("Scamwatch", "scam_types", "Types of scams", "https://www.scamwatch.gov.au/types-of-scams", "government_primary", [
  ("Channel taxonomy", "Scams may be delivered through text, calls, email, social media, websites, or in person. Channel alone does not establish legitimacy.", ["text", "phone", "email", "social media", "website"], ["general_safety"]),
  ("Consumer scam taxonomy", "Triage should distinguish phishing, relationship, investment, buying and selling, jobs, donation, and payment-redirection scenarios.", ["phishing", "relationship", "investment", "shopping", "job"], ["general_safety"]),
  ("Business email compromise", "A changed payee or invoice detail can be a payment-redirection scenario and needs independent verification before money is sent.", ["invoice", "changed bank details", "payment redirection"], ["payment_scam", "contact_official"]),
  ("Recovery scam risk", "A person previously scammed may be targeted again by someone charging a fee or seeking more payment to recover funds.", ["recovery fee", "get money back", "previous scam"], ["no_guarantee", "payment_scam"]),
 ]),
 source("Scamwatch", "investment", "Investment scams", "https://www.scamwatch.gov.au/types-of-scams/investment-scams", "government_primary", [
  ("Investment red flags", "Promises of unusually high returns, little risk, urgency, or persuasive testimonials are warning signals that deserve independent checking.", ["guaranteed return", "low risk", "urgent investment", "testimonial"], ["general_safety"]),
  ("Online investment approach", "Social-media ads, relationship contacts, and convincing websites can be used to promote fake platforms and cryptocurrency schemes.", ["crypto", "social media ad", "trading platform", "dating"], ["payment_scam"]),
  ("Withdrawal pressure", "A demand for another payment, fee, or top-up before a withdrawal is released is a high-risk scam pattern.", ["withdrawal fee", "top up", "release funds"], ["payment_scam", "no_guarantee"]),
  ("Advice boundary", "The agent should direct people toward verified independent sources and avoid giving personalised investment or legal advice.", ["financial advice", "investment advice", "AFS license"], ["general_safety"]),
 ]),
 source("Scamwatch", "relationship", "Relationship scams", "https://www.scamwatch.gov.au/types-of-scams/relationship-scams", "government_primary", [
  ("Relationship manipulation", "Scammers may build trust through dating, friendship, or gaming platforms before requesting money or investment.", ["dating", "romance", "friendship", "love bombing"], ["payment_scam"]),
  ("Communication move", "A rapid move from a platform to private messaging and pressure for secrecy can be relevant context for a relationship-scam report.", ["WhatsApp", "private chat", "secret"], ["general_safety"]),
  ("Money request", "Requests for transfer, cryptocurrency, gift cards, or an urgent emergency from someone known only online are scam warning signals.", ["gift card", "cryptocurrency", "emergency", "transfer"], ["payment_scam"]),
  ("Supportive language", "Use non-judgmental language. The task is safe triage and support, not assigning blame or proving the relationship is fraudulent.", ["embarrassed", "relationship", "support"], ["general_safety"]),
 ]),
 source("Scamwatch", "jobs", "Jobs and employment scams", "https://www.scamwatch.gov.au/types-of-scams/jobs-and-employment-scams", "government_primary", [
  ("Upfront-payment warning", "A job that requires an upfront transfer, PayID payment, or cryptocurrency payment should be treated as a significant warning signal.", ["job fee", "upfront payment", "PayID", "crypto"], ["payment_scam"]),
  ("Recruiter impersonation", "Unexpected recruiter messages can imitate known companies or agencies and seek payment or identity information.", ["recruiter", "job offer", "WhatsApp", "identity"], ["general_safety", "privacy"]),
  ("Credential request", "A job applicant should not provide online-banking or card credentials to an unverified recruiter.", ["bank details", "card details", "job application"], ["privacy", "credential_compromise"]),
  ("Reporting action", "The person can report a suspicious listing to the platform and public scam-reporting channels after using verified contact methods.", ["report listing", "job ad", "scamwatch"], ["general_safety"]),
 ]),
 source("Scamwatch", "targeting_report", "Targeting scams report", "https://www.scamwatch.gov.au/research-and-resources/targeting-scams-report", "government_primary", [
  ("Priority categories", "Current public reporting highlights investment, payment redirection, romance, phishing, and remote access as high-impact scam categories.", ["investment", "payment redirection", "romance", "phishing", "remote access"], ["general_safety"]),
  ("Risk not proof", "Public trend data can guide coverage and monitoring but must not be used to infer that a specific customer or payment is fraudulent.", ["statistics", "trend", "risk score"], ["no_guarantee", "general_safety"]),
  ("Monitoring use", "Track route distributions and new failure patterns to detect drift, but preserve privacy and avoid storing raw customer data.", ["monitoring", "drift", "privacy", "logs"], ["privacy", "general_safety"]),
  ("Review cadence", "Public scam categories and guidance change over time, so corpus sources require an owner and review date.", ["review date", "source owner", "currency"], ["general_safety"]),
 ]),
 source("Westpac", "payid_marketplace", "PayID and online marketplace scams", "https://www.westpac.com.au/security/articles/using-payid-and-avoid-online-marketplace-scams/", "bank_public_guidance", [
  ("PayID fee warning", "A request to pay a fee, upgrade an account, or send money to activate PayID is inconsistent with safe marketplace use and should raise concern.", ["PayID upgrade", "PayID fee", "activate PayID"], ["payment_scam"]),
  ("Marketplace pressure", "Rushed buyers or sellers, offers above the asking price, and requests to move off-platform are useful marketplace-scam signals.", ["marketplace", "rush", "overpay", "off-platform"], ["payment_scam"]),
  ("Avoid sensitive details", "A marketplace counterparty should not need card details or banking-security information to complete a normal sale.", ["card details", "marketplace buyer", "security code"], ["privacy"]),
  ("Report and contact", "Where a customer suspects a marketplace scam, prompt contact with their financial institution and reporting to the platform are appropriate general next steps.", ["report seller", "marketplace profile", "contact bank"], ["contact_official", "general_safety"]),
 ]),
 source("Westpac", "payid_name", "PayID payment safety", "https://www.westpac.com.au/faq/payid-safe-and-secure/", "bank_public_guidance", [
  ("Name check", "A displayed PayID recipient name that does not match the intended recipient is a warning signal requiring independent verification before payment.", ["PayID name", "recipient name", "name mismatch"], ["payment_scam", "contact_official"]),
  ("Trusted verification", "Verify payment details through a number or contact channel sourced independently, not from the message requesting payment.", ["verify payee", "trusted number", "payment details"], ["contact_official"]),
  ("Payment caution", "The agent can suggest pausing and verifying when facts are uncertain; it must not state that a transaction is definitely fraudulent.", ["pause payment", "uncertain payee", "fraudulent"], ["no_guarantee", "general_safety"]),
  ("Product neutrality", "Public bank product information is provider-specific; treat it as contextual consumer guidance, not a universal bank rule.", ["PayID", "bank product", "provider-specific"], ["general_safety"]),
 ]),
 source("Westpac", "payment_redirection", "Payment redirection scams", "https://www.westpac.com.au/security/types-of-scams/business-email-scams/", "bank_public_guidance", [
  ("Changed-details verification", "A request to change supplier bank details should be confirmed using an independently held contact method before payment.", ["supplier", "changed bank details", "invoice"], ["payment_scam", "contact_official"]),
  ("Pressure and secrecy", "An urgent payment request or instruction to bypass normal checks is a warning signal in a business-payment context.", ["urgent invoice", "bypass process", "secret payment"], ["payment_scam"]),
  ("Business controls", "Dual approval and independent verification are useful organisational controls, but the agent should not pretend to approve or execute a business payment.", ["dual approval", "business payment", "approval"], ["no_guarantee", "general_safety"]),
  ("Payee display", "If available, a payee-name display can support verification but does not replace independently confirming a material payment change.", ["payee name", "payment redirection", "verify"], ["payment_scam", "contact_official"]),
 ]),
 source("Commonwealth Bank", "cba_remote_access", "Remote access scams", "https://www.commbank.com.au/support/security/remote-access-scams.html", "bank_public_guidance", [
  ("Familiar-brand impersonation", "Remote-access scammers can claim to represent a bank, telco, government body, or software company.", ["bank caller", "telco", "government", "software company"], ["credential_compromise"]),
  ("Contact methods", "Pop-ups, phone calls, texts, and phishing emails can all be used to persuade someone to grant remote device control.", ["pop-up", "phone call", "text", "phishing email"], ["credential_compromise", "general_safety"]),
  ("Persistence signal", "Pressure, intimidation, or persistence from an unexpected contact should increase caution and may warrant human support where access was granted.", ["persistent caller", "abusive caller", "pressure"], ["urgent_review", "general_safety"]),
  ("No remote remediation", "The assistant must not offer remote device repair or attempt to perform account-security actions itself.", ["remote repair", "fix device", "account action"], ["no_guarantee", "secure_access"]),
 ]),
 source("Scamwatch", "little_book", "Little book of scams", "https://www.scamwatch.gov.au/system/files/little-book-scams-2024-english.pdf", "government_primary", [
  ("Shopping scam pattern", "Fake stores, listings, profiles, and reviews can make an online purchase look credible while aiming to capture payment or personal data.", ["fake store", "fake review", "online shopping", "listing"], ["payment_scam"]),
  ("Invoice alteration", "Scammers can alter payment details on apparently legitimate invoices so that money goes to a fraudulent recipient.", ["invoice change", "fraudulent recipient", "bank details"], ["payment_scam", "contact_official"]),
  ("Job and romance overlap", "Job, relationship, and investment scams may combine an emotional or financial promise with requests for payment or information.", ["job", "romance", "investment", "payment request"], ["general_safety"]),
  ("Awareness value", "Use broad scam examples to help the customer identify warning signs, while keeping the final response focused on the reported facts.", ["scam examples", "warning signs", "reported facts"], ["general_safety"]),
 ]),
]

records = []
for document in SOURCES:
    for number, (title, summary, keywords, links) in enumerate(document["cards"], 1):
        records.append({
            "node_id": f"public.au.{document['slug']}.{number:03d}", "chunk_id": f"public.au.{document['slug']}.{number:03d}",
            "document_id": f"source.au.{document['slug']}", "title": title, "summary": summary,
            "keywords": keywords, "links": links, "publisher": document["publisher"],
            "document_title": document["document_title"], "source_url": document["source_url"],
            "trust_tier": document["trust_tier"], "jurisdiction": "AU", "content_type": "public_customer_safety_guidance",
            "source_license_note": "Public web guidance; stored as an original paraphrase with provenance, not a reproduced source.",
            "last_reviewed": REVIEW_DATE, "status": "active", "not_bank_policy": True,
        })

assert len(records) == 60
with OUT.open("w", encoding="utf-8") as handle:
    for item in records:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
print(f"Wrote {len(records)} public-safety chunks to {OUT}")
