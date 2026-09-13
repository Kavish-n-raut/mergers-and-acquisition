from __future__ import annotations

from app.schemas import LocalDraftRequest, LocalDraftResponse


def _build_nda(request: LocalDraftRequest) -> LocalDraftResponse:
    key_terms = {
        "purpose": f"Evaluate potential transaction for {request.deal_name}",
        "term_months": 24,
        "jurisdiction": request.jurisdiction,
        "exclusivity_days": request.exclusivity_days,
    }
    body = (
        f"Mutual Non-Disclosure Agreement\n\n"
        f"This NDA is entered into by {request.buyer_name} and {request.seller_name} for {request.deal_name}.\n\n"
        "1. Confidential Information: non-public financial, legal, commercial, operational, and technical data.\n"
        "2. Permitted Use: solely for evaluating and negotiating the proposed transaction.\n"
        "3. Non-Disclosure: each party will protect information with at least reasonable care.\n"
        "4. Exclusions: public information, independently developed information, and lawfully obtained third-party information.\n"
        "5. Compelled Disclosure: receiving party must notify disclosing party where legally permitted.\n"
        "6. Return/Destruction: confidential materials must be returned or destroyed on request.\n"
        f"7. Governing Law: {request.jurisdiction}.\n"
        "8. Remedies: unauthorized disclosure may cause irreparable harm and permit equitable relief."
    )
    return LocalDraftResponse(
        document_type="NDA",
        title=f"NDA Draft - {request.deal_name}",
        key_terms=key_terms,
        body=body,
    )


def _build_loi(request: LocalDraftRequest) -> LocalDraftResponse:
    purchase_price = request.purchase_price or 0.0
    price_text = f"${purchase_price:,.2f}" if purchase_price > 0 else "To be finalized after diligence"
    key_terms = {
        "deal_name": request.deal_name,
        "indicative_purchase_price": price_text,
        "exclusivity_days": request.exclusivity_days,
        "jurisdiction": request.jurisdiction,
        "structure": "To be determined (cash/equity/hybrid) after confirmatory diligence",
    }
    body = (
        f"Letter of Intent\n\n"
        f"Buyer: {request.buyer_name}\nSeller: {request.seller_name}\nTransaction: {request.deal_name}\n\n"
        "1. Transaction Overview: buyer proposes to acquire substantially all equity or assets of the target.\n"
        f"2. Indicative Consideration: {price_text}.\n"
        "3. Consideration Mix: subject to valuation, risk allocation, and financing constraints.\n"
        "4. Due Diligence: legal, financial, tax, regulatory, technology, cybersecurity, and HR diligence required.\n"
        f"5. Exclusivity: seller agrees to negotiate exclusively for {request.exclusivity_days} days.\n"
        "6. Definitive Agreements: completion subject to negotiated SPA/APA and ancillary documentation.\n"
        f"7. Governing Law: {request.jurisdiction}.\n"
        "8. Non-Binding Nature: this LOI is non-binding except confidentiality, exclusivity, expenses, and governing law."
    )
    return LocalDraftResponse(
        document_type="LOI",
        title=f"LOI Draft - {request.deal_name}",
        key_terms=key_terms,
        body=body,
    )


def generate_local_draft(request: LocalDraftRequest) -> LocalDraftResponse:
    if request.document_type == "NDA":
        return _build_nda(request)
    return _build_loi(request)

