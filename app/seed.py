import os
from .models import *
from .security import hash_pw
CATALOGUE = {
"Healthcare & medical":"Hospitals,Clinics,Doctors,Dentists,Pharmacies,Laboratories,Ambulance,Mental health,Maternity,Nursing,Physiotherapy,Radiology,Telemedicine,Rehabilitation,Home care,Specialist consultations",
"Education & learning":"Schools,Universities,Colleges,Tutors,Online classes,Vocational training,Language schools,Driving schools,Coding academies,Examination centres,Libraries,Educational consultants",
"Transport & mobility":"Matatus,Buses,Taxis,Ride-hailing,Car hire,Motorcycles,Tuk-tuks,Trains,Airlines,Airports,Ferries,Marine transport,Freight,Courier,Moving services",
"Tourism & hospitality":"Hotels,Guest houses,Lodges,Resorts,Tour operators,Travel agencies,Guides,Campsites,Vacation rentals,Restaurants,Catering",
"Retail & commerce":"Supermarkets,Clothing,Electronics,Hardware,Wholesalers,Online sellers,Markets,Distributors,Importers,Exporters,Product delivery",
"Finance & insurance":"Banks,SACCOs,Fintech,Payment providers,Insurance,Accounting,Bookkeeping,Tax preparation,Financial advisors,Remittance,Lending,Investment",
"Legal & compliance":"Lawyers,Legal consultation,Mediation,Arbitration,Notaries,Company registration,Contracts,Immigration services,Intellectual property",
"Technology & digital":"Software development,IT support,Cybersecurity,AI,Cloud services,Web design,Mobile apps,Data science,Computer repair,Networking,Hosting,Digital marketing",
"Construction & property":"Architects,Engineers,Builders,Plumbers,Electricians,Painters,Surveyors,Real estate,Property management,Renovations,Roofing,Interior design",
"Home & personal services":"Cleaning,Laundry,Gardening,Landscaping,Pest control,Handyman,Appliance repair,Home security installation,Furniture assembly,Domestic services",
"Beauty, wellness & fitness":"Barbers,Salons,Makeup,Nail technicians,Spas,Massage,Gyms,Personal trainers,Yoga,Wellness centres",
"Agriculture & livestock":"Farmers,Agronomists,Veterinary services,Animal feeds,Farm equipment,Irrigation,Seeds,Fertilizers,Crop processing,Livestock trading",
"Manufacturing & industry":"Factories,Fabrication,Welding,Packaging,Industrial equipment,Machinery maintenance,Quality control,Materials suppliers",
"Logistics & supply chain":"Warehousing,Shipping,Clearing and forwarding,Customs,Distribution,Cold chain,Inventory,Cargo,Storage",
"Events & entertainment":"Event planners,DJs,Musicians,Photographers,Videographers,Venues,MCs,Decorators,Wedding services,Ticketing,Film production",
"Business & professional services":"Consultants,HR,Recruitment,Marketing,Translation,Research,Secretarial,Business registration,Outsourcing,Corporate training",
"Government & civic":"Permits,Licensing,Registration,Citizen support,Local government,Public utilities,Civic appointments",
"Energy & utilities":"Solar,Electrical services,Power installations,Water,Gas,Energy audits,Renewable energy,Charging stations",
"Automotive & marine":"Mechanics,Garages,Diagnostics,Tyre services,Car wash,Spare parts,Towing,Bodywork,Vehicle inspection,Boat repair",
"Pets & animals":"Veterinarians,Pet grooming,Boarding,Pet sitting,Animal shelters,Animal training,Pet shops,Adoption",
"Sports & recreation":"Sports clubs,Football,Swimming,Coaches,Stadiums,Equipment hire,Recreation centres,Outdoor activities",
"Security & safety":"Security companies,Alarm systems,CCTV installation,Access control,Fire safety,Safety training,Emergency response",
"Environment & sustainability":"Waste collection,Recycling,Sanitation,Environmental assessments,Water treatment,Conservation,Tree planting",
"Creative & media":"Graphic design,Branding,Printing,Publishing,Animation,Content creators,Advertising,Journalism,Social media",
"Community & social":"Faith-based organizations,Community organizations,Funeral services,Childcare,Elderly care,Disability support,Social work",
"Science & emerging":"Scientific research,Mining,Forestry,Fisheries,Telecommunications,Space technology,Emerging technologies"}
def seed(db):
    admin_email = os.getenv("ADMIN_EMAIL", "admin@mobihub.local").lower()
    admin_password = os.getenv("ADMIN_PASSWORD")

    admin = db.query(User).filter_by(role="super").first()

    if admin:
        admin.email = admin_email
        if admin_password:
            admin.password_hash = hash_pw(admin_password)
    else:
        if not admin_password:
            raise ValueError("ADMIN_PASSWORD must be configured")

        db.add(User(
            email=admin_email,
            name="Super Admin",
            role="super",
            password_hash=hash_pw(james3325)
        ))
    if not db.query(Category).first():
        for ind, subs in CATALOGUE.items():
            p = Category(name=ind); db.add(p); db.flush()
            for s in subs.split(","): db.add(Category(name=s.strip(), parent_id=p.id))
    for k, v in {"countries":"KE,UG,TZ,RW,US,GB","currencies":"KES,USD,EUR,GBP","languages":"en,sw,fr","tax_pct":"16","escrow_instructions":"Pay the booking amount by M-Pesa to Paybill 000000 (edit this in Admin > Settings). Use your booking ref (e.g. MH-12) as account, then enter the M-Pesa confirmation code below. Funds stay in escrow until the job is done."}.items():
        if not db.query(Setting).filter_by(key=k).first(): db.add(Setting(key=k, value=v))
    db.commit()
