from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey
from .db import Base
def pk(): return Column(Integer, primary_key=True)
def now(): return Column(DateTime, default=datetime.utcnow)
class User(Base):
    __tablename__="users"; id=pk()
    email=Column(String(200),unique=True,index=True); name=Column(String(200)); phone=Column(String(40))
    password_hash=Column(String(200))
    role=Column(String(30),default="customer")  # customer|provider|super|verification|operations|finance|support|catalogue|analytics
    status=Column(String(20),default="active")  # active|suspended|blocked
    country=Column(String(60),default="Kenya"); created_at=now()
class ProviderProfile(Base):
    __tablename__="providers"; id=pk()
    user_id=Column(Integer,ForeignKey("users.id")); business_name=Column(String(200)); address=Column(String(300))
    service_area=Column(String(300)); payout_info=Column(String(300),default=""); service_ids=Column(String(500),default="")
    profile_photo_path=Column(String(400),default=""); profile_photo_filename=Column(String(300),default="")
    verification_status=Column(String(30),default="pending")  # pending|under_review|more_info|approved|rejected|expired|suspended|blocked
    verification_note=Column(Text,default=""); created_at=now()
class VerificationDoc(Base):
    __tablename__="documents"; id=pk()
    provider_id=Column(Integer,ForeignKey("providers.id")); doc_type=Column(String(60)); filename=Column(String(300))
    stored_path=Column(String(400)); expires_on=Column(String(20),default=""); created_at=now()
class Category(Base):  # self-referencing: industry -> category -> specialty (unlimited depth)
    __tablename__="categories"; id=pk()
    parent_id=Column(Integer,ForeignKey("categories.id"),nullable=True); name=Column(String(200)); active=Column(Boolean,default=True)
class Service(Base):
    __tablename__="services"; id=pk()
    category_id=Column(Integer,ForeignKey("categories.id")); name=Column(String(200)); description=Column(Text,default="")
    provider_type=Column(String(80),default="individual"); booking_method=Column(String(40),default="appointment")
    location_type=Column(String(40),default="physical"); price_type=Column(String(30),default="quotation")
    price=Column(Float,default=0); currency=Column(String(5),default="KES"); verification_required=Column(Boolean,default=True)
    required_documents=Column(String(300),default="National ID"); cancellation_rules=Column(String(300),default="")
    commission_pct=Column(Float,default=10); capacity=Column(Integer,default=1); countries=Column(String(300),default="KE")
    active=Column(Boolean,default=True)
class Booking(Base):
    __tablename__="bookings"; id=pk()
    customer_id=Column(Integer,ForeignKey("users.id")); provider_id=Column(Integer,ForeignKey("providers.id"),nullable=True)
    service_id=Column(Integer,ForeignKey("services.id")); scheduled_at=Column(String(40)); notes=Column(Text,default="")
    status=Column(String(20),default="new")  # new|assigned|confirmed|completed|cancelled
    synced=Column(Boolean,default=True); created_at=now()
class Payment(Base):
    __tablename__="payments"; id=pk()
    booking_id=Column(Integer,ForeignKey("bookings.id")); method=Column(String(20),default="mpesa"); amount=Column(Float)
    currency=Column(String(5),default="KES"); reference=Column(String(100)); status=Column(String(20),default="pending")  # pending|paid|failed|refunded
    created_at=now()
class Review(Base):
    __tablename__="reviews"; id=pk()
    booking_id=Column(Integer,ForeignKey("bookings.id")); author_id=Column(Integer,ForeignKey("users.id"))
    rating=Column(Integer); comment=Column(Text,default=""); hidden=Column(Boolean,default=False); created_at=now()
class Complaint(Base):
    __tablename__="complaints"; id=pk()
    raised_by=Column(Integer,ForeignKey("users.id")); against_user=Column(Integer,nullable=True); booking_id=Column(Integer,nullable=True)
    subject=Column(String(200)); details=Column(Text,default=""); status=Column(String(20),default="open")  # open|investigating|escalated|resolved
    resolution=Column(Text,default=""); created_at=now()
class AuditLog(Base):
    __tablename__="audit_log"; id=pk()
    admin_id=Column(Integer); action=Column(String(60)); resource=Column(String(60)); target_id=Column(Integer,nullable=True)
    detail=Column(Text,default=""); created_at=now()
class Setting(Base):
    __tablename__="settings"; id=pk()
    key=Column(String(100),unique=True); value=Column(Text,default="")  # countries, currencies, languages, taxes, templates...
class Escrow(Base):  # manual escrow: customer pays platform off-platform, finance admin confirms & pays out by hand
    __tablename__="escrow"; id=pk()
    booking_id=Column(Integer,ForeignKey("bookings.id"),unique=True); amount=Column(Float); currency=Column(String(5),default="KES")
    commission_pct=Column(Float,default=10); commission_amount=Column(Float,default=0); payout_amount=Column(Float,default=0)
    customer_ref=Column(String(100),default=""); payout_ref=Column(String(100),default=""); refund_ref=Column(String(100),default="")
    status=Column(String(30),default="awaiting_payment")
    # awaiting_payment|payment_submitted|funded|delivered|approved|disputed|released|refunded
    created_at=now(); updated_at=Column(DateTime,default=datetime.utcnow)
class EscrowEvent(Base):
    __tablename__="escrow_events"; id=pk()
    escrow_id=Column(Integer,ForeignKey("escrow.id")); actor_id=Column(Integer); event=Column(String(40)); note=Column(Text,default=""); created_at=now()


class ProviderServiceOffer(Base):
    __tablename__="provider_service_offers"; id=pk()
    provider_id=Column(Integer,ForeignKey("providers.id")); service_id=Column(Integer,ForeignKey("services.id"))
    description=Column(Text,default=""); photo_path=Column(String(400)); photo_filename=Column(String(300))
    created_at=now()


