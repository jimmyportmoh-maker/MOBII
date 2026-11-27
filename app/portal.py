import os, uuid, smtplib
from email.message import EmailMessage
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .db import get_db
from .models import *
from .security import current_user, require

router = APIRouter()
UPLOADS = os.path.join(os.path.dirname(__file__), "..", "private_uploads")
os.makedirs(UPLOADS, exist_ok=True)
DOC_TYPES = ["National ID", "Passport", "Selfie with ID", "Business registration", "Professional licence", "Other"]
ALLOWED, MAXB = {".pdf", ".jpg", ".jpeg", ".png"}, 8 * 1024 * 1024
PROFILE_MAXB = 50 * 1024 * 1024
def row(o): return {c.name: getattr(o, c.name) for c in o.__table__.columns if c.name != "password_hash"}
def log(db, e, u, event, note=""): db.add(EscrowEvent(escrow_id=e.id, actor_id=u.id, event=event, note=note))
def audit(db, u, action, tid, detail=""): db.add(AuditLog(admin_id=u.id, action=action, resource="escrow", target_id=tid, detail=detail))

def send_provider_booking_email(provider_email, provider_name, customer, booking, service):
    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", username).strip()
    if not all((host, username, password, sender, provider_email)):
        return False
    msg = EmailMessage()
    msg["Subject"] = f"New MOBI HUB booking request #{booking.id}"
    msg["From"] = sender
    msg["To"] = provider_email
    msg.set_content(
        f"Hello {provider_name},\n\n"
        f"You have received a new service booking request on MOBI HUB.\n\n"
        f"Booking ID: {booking.id}\n"
        f"Service: {service.name if service else 'Service'}\n"
        f"Customer: {customer.name}\n"
        f"Customer email: {customer.email}\n"
        f"Customer phone: {customer.phone or 'Not provided'}\n"
        f"Preferred date/time: {booking.scheduled_at or 'Flexible'}\n"
        f"Work details: {booking.notes}\n\n"
        "Sign in to your MOBI HUB provider dashboard to accept or decline this request."
    )
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
        return True
    except Exception as exc:
        print(f"Provider booking email notification failed: {exc}")
        return False

def prov(db, u):
    p = db.query(ProviderProfile).filter_by(user_id=u.id).first()
    if not p: raise HTTPException(403, "Providers only")
    return p
def view(db, b):
    e = db.query(Escrow).filter_by(booking_id=b.id).first(); s = db.get(Service, b.service_id)
    p = db.get(ProviderProfile, b.provider_id) if b.provider_id else None
    pu = db.get(User, p.user_id) if p else None
    payments = db.query(Payment).filter_by(booking_id=b.id).order_by(Payment.id.desc()).all()
    return {"booking": row(b), "escrow": row(e) if e else None, "service": s.name if s else "",
            "provider": p.business_name if p else "", "provider_phone": (p.payout_info or pu.phone or "") if p and b.status == "completed" else "",
            "payments": [row(x) for x in payments]}

@router.get("/api/me")
def me(u: User = Depends(current_user)): return {"id": u.id, "name": u.name, "email": u.email, "role": u.role}
@router.get("/api/services")
def services(db: Session = Depends(get_db)):
    items = db.query(Service).filter_by(active=True).all()
    result = []
    for s in items:
        item = row(s)
        category = db.get(Category, s.category_id) if s.category_id else None
        item["category_name"] = category.name if category else "Other services"
        result.append(item)
    result.sort(key=lambda x: (x["category_name"].lower(), x["name"].lower()))
    return result
@router.get("/api/escrow/instructions")
def instructions(db: Session = Depends(get_db)):
    s = db.query(Setting).filter_by(key="escrow_instructions").first(); return s.value if s else ""

# ---- Provider
@router.get("/api/provider/me")
def provider_me(u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = prov(db, u)
    docs = db.query(VerificationDoc).filter_by(provider_id=p.id).all()
    jobs = db.query(Booking).filter_by(provider_id=p.id).order_by(Booking.id.desc()).all()
    offers = db.query(ProviderServiceOffer).filter_by(provider_id=p.id).all()
    usr = db.get(User, u.id)
    job_rows = []
    for b in jobs:
        item = view(db, b)
        customer = db.get(User, b.customer_id)
        item["customer_name"] = customer.name if customer else "Customer"
        item["customer_phone"] = customer.phone if customer else ""
        item["customer_email"] = customer.email if customer else ""
        job_rows.append(item)
    return {"profile": row(p), "profile_photo_url": f"/api/provider-photos/{p.id}" if p.profile_photo_path else "", "provider_details": {"name": usr.name, "email": usr.email, "phone": usr.phone}, "doc_types": DOC_TYPES, "jobs": job_rows,
            "docs": [{"id": d.id, "doc_type": d.doc_type, "filename": d.filename, "created_at": str(d.created_at)} for d in docs],
            "offers": [{"id": o.id, "service_id": o.service_id, "service": db.get(Service, o.service_id).name if db.get(Service, o.service_id) else "", "description": o.description, "photo_filename": o.photo_filename} for o in offers]}
class ProfileIn(BaseModel):
    business_name: str = ""; address: str = ""; service_area: str = ""; payout_info: str = ""; service_ids: list[int] = []
@router.patch("/api/provider/me")
def patch_me(b: ProfileIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = prov(db, u)
    if p.verification_status == "approved":
        raise HTTPException(403, "Your profile is already verified. Manage your service listings below.")
    if not b.business_name.strip() or not b.address.strip() or not b.service_area.strip() or not b.payout_info.strip():
        raise HTTPException(400, "Complete business name, address, service area and payout details.")
    types = {d.doc_type for d in db.query(VerificationDoc).filter_by(provider_id=p.id)}
    if not types & {"National ID", "Passport"}:
        raise HTTPException(400, "Upload your National ID or Passport before submitting your profile.")
    p.business_name, p.address, p.service_area, p.payout_info = b.business_name.strip(), b.address.strip(), b.service_area.strip(), b.payout_info.strip()
    p.verification_status = "under_review"
    db.commit(); return row(p)


@router.post("/api/provider/profile-photo")
def upload_provider_profile_photo(file: UploadFile = File(...), u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = prov(db, u)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(400, "Profile photos must be JPG or PNG.")
    data = file.file.read(PROFILE_MAXB + 1)
    if len(data) > PROFILE_MAXB:
        raise HTTPException(400, "Profile photo larger than 50 MB.")
    stored = uuid.uuid4().hex + ext
    with open(os.path.join(UPLOADS, stored), "wb") as f:
        f.write(data)
    old_path = p.profile_photo_path
    p.profile_photo_path = stored
    p.profile_photo_filename = os.path.basename(file.filename or "profile-photo")
    db.commit()
    if old_path:
        try: os.remove(os.path.join(UPLOADS, old_path))
        except OSError: pass
    return {"ok": True, "photo_url": f"/api/provider-photos/{p.id}"}

@router.get("/api/provider-photos/{provider_id}")
def provider_profile_photo(provider_id: int, db: Session = Depends(get_db)):
    p = db.get(ProviderProfile, provider_id)
    if not p or p.verification_status != "approved" or not p.profile_photo_path:
        raise HTTPException(404, "Provider profile photo not found")
    path = os.path.join(UPLOADS, p.profile_photo_path)
    if not os.path.isfile(path):
        raise HTTPException(404, "Provider profile photo is unavailable")
    return FileResponse(path, filename=p.profile_photo_filename or "provider-profile-photo")

@router.get("/api/service-photos/{offer_id}")
def service_photo(offer_id: int, db: Session = Depends(get_db)):
    offer = db.get(ProviderServiceOffer, offer_id)
    if not offer or not offer.photo_path:
        raise HTTPException(404, "Service photo not found")
    path = os.path.join(UPLOADS, offer.photo_path)
    if not os.path.isfile(path):
        raise HTTPException(404, "Service photo is no longer available")
    return FileResponse(path, filename=offer.photo_filename)

@router.post("/api/provider/services")
def provider_service(service_id: int = Form(...), description: str = Form(...), file: UploadFile = File(...),
                     u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = prov(db, u)
    if p.verification_status != "approved": raise HTTPException(403, "Your provider profile must be approved before you can publish services.")
    s = db.get(Service, service_id)
    if not s or not s.active: raise HTTPException(404, "Choose an active catalogue service.")
    if len(description.strip()) < 20: raise HTTPException(400, "Describe your service in at least 20 characters.")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png"}: raise HTTPException(400, "Service photos must be JPG or PNG.")
    data = file.file.read(MAXB + 1)
    if len(data) > MAXB: raise HTTPException(400, "Photo larger than 8 MB.")
    stored = uuid.uuid4().hex + ext
    with open(os.path.join(UPLOADS, stored), "wb") as f: f.write(data)
    offer = db.query(ProviderServiceOffer).filter_by(provider_id=p.id, service_id=s.id).first()
    if offer:
        old_path = offer.photo_path
        offer.description, offer.photo_path, offer.photo_filename = description.strip(), stored, os.path.basename(file.filename or "service-photo")
        if old_path:
            try: os.remove(os.path.join(UPLOADS, old_path))
            except OSError: pass
    else:
        db.add(ProviderServiceOffer(provider_id=p.id, service_id=s.id, description=description.strip(),
                                    photo_path=stored, photo_filename=os.path.basename(file.filename or "service-photo")))
    ids = {x for x in (p.service_ids or "").split(",") if x}
    ids.add(str(s.id)); p.service_ids = ",".join(sorted(ids, key=int))
    db.commit()
    return {"ok": True, "service_id": s.id}

@router.post("/api/provider/documents")
def upload_doc(doc_type: str = Form(...), expires_on: str = Form(""), file: UploadFile = File(...),
               u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = prov(db, u)
    if doc_type not in DOC_TYPES: raise HTTPException(400, "Unknown document type")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED: raise HTTPException(400, "Only JPG, PNG or PDF files")
    data = file.file.read(MAXB + 1)
    if len(data) > MAXB: raise HTTPException(400, "File larger than 8 MB")
    stored = uuid.uuid4().hex + ext
    with open(os.path.join(UPLOADS, stored), "wb") as f: f.write(data)
    db.add(VerificationDoc(provider_id=p.id, doc_type=doc_type, filename=os.path.basename(file.filename), stored_path=stored, expires_on=expires_on))
    db.commit(); return {"ok": True}

# ---- Customer
@router.get("/api/providers")
def providers(service_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for p in db.query(ProviderProfile).filter_by(verification_status="approved"):
        usr = db.get(User, p.user_id)
        if usr and usr.status == "active" and str(service_id) in (p.service_ids or "").split(","):
            offer = db.query(ProviderServiceOffer).filter_by(provider_id=p.id, service_id=service_id).first()
            ratings = db.query(Review).join(Booking, Review.booking_id == Booking.id).filter(
                Booking.provider_id == p.id, Review.hidden == False).all()
            avg = round(sum(r.rating for r in ratings) / len(ratings), 2) if ratings else 0
            out.append({"id": p.id, "business_name": p.business_name, "service_area": p.service_area,
                        "address": p.address, "description": offer.description if offer else "",
                        "photo_id": offer.id if offer else None, "rating": avg, "rating_count": len(ratings)})
    out.sort(key=lambda x: (x["rating_count"] > 0, x["rating"], x["rating_count"]), reverse=True)
    return out

class NewBooking(BaseModel):
    service_id: int
    scheduled_at: str = ""
    notes: str = ""

@router.post("/api/bookings")
def book(b: NewBooking, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.role != "customer": raise HTTPException(403, "Customers only")
    s = db.get(Service, b.service_id)
    if not s or not s.active: raise HTTPException(404, "Service unavailable")
    if len(b.notes.strip()) < 5: raise HTTPException(400, "Please describe what service you need.")
    o = Booking(customer_id=u.id, provider_id=None, service_id=s.id, scheduled_at=b.scheduled_at,
                notes=b.notes.strip(), status="requested")
    db.add(o); db.commit(); db.refresh(o)
    return view(db, o)

@router.get("/api/bookings/mine")
def mine(u: User = Depends(current_user), db: Session = Depends(get_db)):
    result = []
    for b in db.query(Booking).filter_by(customer_id=u.id).order_by(Booking.id.desc()).all():
        item = view(db, b)
        if b.status == "requested" and not b.provider_id:
            item["available_providers"] = providers(b.service_id, u, db)
        result.append(item)
    return result

class ProviderChoice(BaseModel): provider_id: int
@router.post("/api/bookings/{booking_id}/select-provider")
def select_provider(booking_id: int, data: ProviderChoice, u: User = Depends(current_user), db: Session = Depends(get_db)):
    b = db.get(Booking, booking_id)
    if not b or b.customer_id != u.id: raise HTTPException(404, "Request not found")
    if b.status != "requested" or b.provider_id: raise HTTPException(400, "This request is no longer awaiting provider selection.")
    p = db.get(ProviderProfile, data.provider_id)
    if not p or p.verification_status != "approved" or str(b.service_id) not in (p.service_ids or "").split(","):
        raise HTTPException(400, "That provider does not offer the selected service.")
    b.provider_id = p.id
    b.status = "provider_selected"
    db.commit()
    customer = db.get(User, b.customer_id)
    provider_user = db.get(User, p.user_id)
    service = db.get(Service, b.service_id)
    email_sent = send_provider_booking_email(
        provider_user.email if provider_user else "",
        p.business_name,
        customer,
        b,
        service
    ) if customer and provider_user else False
    result = view(db, b)
    result["email_sent"] = email_sent
    return result

@router.post("/api/provider/bookings/{booking_id}/accept")
def accept_request(booking_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = prov(db, u); b = db.get(Booking, booking_id)
    if not b or b.provider_id != p.id: raise HTTPException(404, "Request not found")
    if b.status != "provider_selected": raise HTTPException(400, "This request is no longer awaiting your response.")
    b.status = "confirmed"; db.commit(); return view(db, b)

@router.post("/api/provider/bookings/{booking_id}/decline")
def decline_request(booking_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = prov(db, u); b = db.get(Booking, booking_id)
    if not b or b.provider_id != p.id: raise HTTPException(404, "Request not found")
    if b.status != "provider_selected": raise HTTPException(400, "This request is no longer awaiting your response.")
    b.provider_id = None; b.status = "requested"; db.commit(); return view(db, b)

@router.post("/api/provider/bookings/{booking_id}/complete")
def complete_request(booking_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = prov(db, u); b = db.get(Booking, booking_id)
    if not b or b.provider_id != p.id: raise HTTPException(404, "Request not found")
    if b.status != "confirmed": raise HTTPException(400, "Only accepted requests can be marked complete.")
    b.status = "completed"; db.commit(); return view(db, b)

class ManualPayment(BaseModel): amount: float; receipt: str

@router.post("/api/bookings/{booking_id}/pay/send-money")
def send_money(booking_id: int, data: ManualPayment, u: User = Depends(current_user), db: Session = Depends(get_db)):
    b = db.get(Booking, booking_id)
    if not b or b.customer_id != u.id: raise HTTPException(404, "Booking not found")
    if b.status != "completed" or not b.provider_id: raise HTTPException(400, "Payment is available after the provider marks the work complete.")
    if data.amount < 1 or data.amount > 250000: raise HTTPException(400, "Enter an amount from KSh 1 to KSh 250,000.")
    receipt = data.receipt.strip().upper()
    if len(receipt) < 8 or len(receipt) > 20: raise HTTPException(400, "Enter the M-Pesa confirmation code.")
    if db.query(Payment).filter_by(reference=receipt).first(): raise HTTPException(409, "That M-Pesa code has already been submitted.")
    db.add(Payment(booking_id=b.id, method="send_money", amount=round(data.amount, 2), currency="KES", reference=receipt, status="submitted"))
    db.commit(); return {"ok": True, "status": "submitted", "message": "Payment submitted for verification. It will not show as paid until verified."}

# ---- Escrow transitions
class Ref(BaseModel): ref: str = ""; note: str = ""
def esc_for(db, eid, u, who):
    e = db.get(Escrow, eid)
    if not e: raise HTTPException(404)
    b = db.get(Booking, e.booking_id)
    if who == "customer" and b.customer_id != u.id: raise HTTPException(403)
    if who == "provider" and b.provider_id != prov(db, u).id: raise HTTPException(403)
    return e, b
def move(db, e, u, allowed, new, event, note=""):
    if e.status not in allowed: raise HTTPException(400, f"Not allowed while status is '{e.status}'")
    e.status, e.updated_at = new, datetime.utcnow(); log(db, e, u, event, note)
@router.post("/api/escrow/{eid}/pay")
def pay(eid: int, b: Ref, u: User = Depends(current_user), db: Session = Depends(get_db)):
    ref = b.ref.strip().upper(); e, _ = esc_for(db, eid, u, "customer")
    if not ref: raise HTTPException(400, "Enter the payment reference")
    if db.query(Escrow).filter(Escrow.customer_ref == ref, Escrow.id != e.id).first(): raise HTTPException(409, "That reference was already used")
    move(db, e, u, ["awaiting_payment"], "payment_submitted", "payment_submitted", ref); e.customer_ref = ref; db.commit(); return row(e)
@router.post("/api/escrow/{eid}/deliver")
def deliver(eid: int, b: Ref, u: User = Depends(current_user), db: Session = Depends(get_db)):
    e, _ = esc_for(db, eid, u, "provider"); move(db, e, u, ["funded"], "delivered", "delivered", b.note); db.commit(); return row(e)
@router.post("/api/escrow/{eid}/approve")
def approve(eid: int, b: Ref, u: User = Depends(current_user), db: Session = Depends(get_db)):
    e, _ = esc_for(db, eid, u, "customer"); move(db, e, u, ["delivered"], "approved", "customer_approved"); db.commit(); return row(e)
@router.post("/api/escrow/{eid}/dispute")
def dispute(eid: int, b: Ref, u: User = Depends(current_user), db: Session = Depends(get_db)):
    e, bk = esc_for(db, eid, u, "customer"); move(db, e, u, ["funded", "delivered"], "disputed", "disputed", b.note)
    pu = db.get(ProviderProfile, bk.provider_id)
    db.add(Complaint(raised_by=u.id, against_user=pu.user_id if pu else None, booking_id=bk.id, subject=f"Escrow dispute #{e.id}", details=b.note))
    db.commit(); return row(e)

# ---- Finance admin (manual money handling)
FIN = Depends(require("finance"))
@router.post("/api/admin/escrow/{eid}/confirm")
def confirm(eid: int, b: Ref, u: User = FIN, db: Session = Depends(get_db)):
    e = db.get(Escrow, eid)
    if not e: raise HTTPException(404)
    move(db, e, u, ["payment_submitted"], "funded", "funds_confirmed", b.note)
    bk = db.get(Booking, e.booking_id); bk.status = "confirmed"
    db.add(Payment(booking_id=bk.id, method="manual", amount=e.amount, currency=e.currency, reference=e.customer_ref, status="paid"))
    audit(db, u, "escrow_confirm", eid, e.customer_ref); db.commit(); return row(e)
@router.post("/api/admin/escrow/{eid}/reject")
def reject(eid: int, b: Ref, u: User = FIN, db: Session = Depends(get_db)):
    e = db.get(Escrow, eid)
    if not e: raise HTTPException(404)
    move(db, e, u, ["payment_submitted"], "awaiting_payment", "payment_rejected", b.note); e.customer_ref = ""
    audit(db, u, "escrow_reject", eid, b.note); db.commit(); return row(e)
@router.post("/api/admin/escrow/{eid}/release")
def release(eid: int, b: Ref, u: User = FIN, db: Session = Depends(get_db)):
    e = db.get(Escrow, eid)
    if not e: raise HTTPException(404)
    if not b.ref.strip(): raise HTTPException(400, "Enter the payout reference (M-Pesa/bank code)")
    move(db, e, u, ["approved", "delivered", "disputed"], "released", "released_to_provider", b.ref); e.payout_ref = b.ref.strip()
    db.get(Booking, e.booking_id).status = "completed"; audit(db, u, "escrow_release", eid, b.ref); db.commit(); return row(e)
@router.post("/api/admin/escrow/{eid}/refund")
def refund_escrow(eid: int, b: Ref, u: User = FIN, db: Session = Depends(get_db)):
    e = db.get(Escrow, eid)
    if not e: raise HTTPException(404)
    if not b.ref.strip(): raise HTTPException(400, "Enter the refund reference")
    move(db, e, u, ["funded", "delivered", "disputed"], "refunded", "refunded_to_customer", b.ref); e.refund_ref = b.ref.strip()
    db.get(Booking, e.booking_id).status = "cancelled"
    p = db.query(Payment).filter_by(booking_id=e.booking_id).first()
    if p: p.status = "refunded"
    audit(db, u, "escrow_refund", eid, b.ref); db.commit(); return row(e)
@router.get("/api/admin/escrow/{eid}/events")
def events(eid: int, u: User = Depends(require("finance", "support")), db: Session = Depends(get_db)):
    return [row(x) for x in db.query(EscrowEvent).filter_by(escrow_id=eid).order_by(EscrowEvent.id)]
