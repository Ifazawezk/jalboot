"""Fixed lists the world generator draws from.

Every merchant name here is invented for this project. Doha zone names are public
place names and are used only so the simulation reads naturally.
"""

from __future__ import annotations

# Area, Arabic name, approximate centre. The areas and their fee zones match
# fees.zones in knowledge/rules.json.
ZONES = [
    ("Al Dafna", "الدفنة", 25.310, 51.520), ("West Bay", "الخليج الغربي", 25.320, 51.530),
    ("Msheireb", "مشيرب", 25.286, 51.527), ("Al Sadd", "السد", 25.283, 51.500),
    ("Bin Mahmoud", "بن محمود", 25.280, 51.513), ("Al Mansoura", "المنصورة", 25.270, 51.530),
    ("Najma", "نجمة", 25.270, 51.540), ("Old Airport", "المطار القديم", 25.250, 51.550),
    ("Madinat Khalifa", "مدينة خليفة", 25.320, 51.470), ("Al Gharrafa", "الغرافة", 25.340, 51.450),
    ("Al Waab", "الوعب", 25.260, 51.460), ("Al Aziziyah", "العزيزية", 25.240, 51.450),
    ("Onaiza", "عنيزة", 25.320, 51.510), ("The Pearl", "اللؤلؤة", 25.370, 51.550),
    ("Al Duhail", "الدحيل", 25.350, 51.480), ("Lusail", "لوسيل", 25.420, 51.500),
    ("Al Rayyan", "الريان", 25.290, 51.420), ("Al Wakrah", "الوكرة", 25.170, 51.600),
    ("Al Wukair", "الوكير", 25.130, 51.550), ("Muaither", "معيذر", 25.270, 51.390),
    ("Umm Salal", "أم صلال", 25.420, 51.400), ("Al Khor", "الخور", 25.680, 51.500),
    ("Mesaieed", "مسيعيد", 24.990, 51.550), ("Al Shahaniya", "الشحانية", 25.370, 51.220),
]

FIRST_NAMES = [
    ("Layla", "ليلى"), ("Noura", "نورة"), ("Maryam", "مريم"), ("Huda", "هدى"), ("Salma", "سلمى"),
    ("Dana", "دانة"), ("Reem", "ريم"), ("Aisha", "عائشة"), ("Farah", "فرح"), ("Lina", "لينا"),
    ("Omar", "عمر"), ("Yousef", "يوسف"), ("Khalid", "خالد"), ("Hamad", "حمد"), ("Tariq", "طارق"),
    ("Saad", "سعد"), ("Rashid", "راشد"), ("Ibrahim", "إبراهيم"), ("Ali", "علي"), ("Hassan", "حسن"),
    ("Anjali", "أنجالي"), ("Priya", "بريا"), ("Rahul", "راهول"), ("Arjun", "أرجون"), ("Maria", "ماريا"),
    ("Jose", "خوسيه"), ("Grace", "غريس"), ("Daniel", "دانيال"), ("Sarah", "سارة"), ("Bilal", "بلال"),
]

LAST_NAMES = [
    ("Haddad", "حداد"), ("Mansour", "منصور"), ("Khalil", "خليل"), ("Nasser", "ناصر"), ("Saleh", "صالح"),
    ("Rahman", "رحمن"), ("Yousef", "يوسف"), ("Hassan", "حسن"), ("Ibrahim", "إبراهيم"), ("Karim", "كريم"),
    ("Fernandes", "فرنانديز"), ("Santos", "سانتوس"), ("Thomas", "توماس"), ("Nair", "ناير"), ("Menon", "مينون"),
    ("Qureshi", "قريشي"), ("Siddiqui", "صديقي"), ("Abbas", "عباس"), ("Farouk", "فاروق"), ("Sabry", "صبري"),
]

MERCHANTS = {
    "food": [
        ("Lantern Shawarma", "شاورما الفانوس"), ("Bayt Al Luqma", "بيت اللقمة"),
        ("Clove Yard Biryani", "برياني ساحة القرنفل"), ("Harbour Fish Grill", "مشوى سمك المرفأ"),
        ("Olive Courtyard", "فناء الزيتون"), ("Mandi Lane", "درب المندي"),
        ("Zaatar Oven", "فرن الزعتر"), ("Cardamom Cup", "فنجان الهيل"),
        ("Golden Tray Kitchen", "مطبخ الصينية الذهبية"), ("Date Palm Bakery", "مخبز نخلة التمر"),
        ("Sea Breeze Noodles", "نودلز نسيم البحر"), ("Two Spoons Cafe", "مقهى الملعقتين"),
    ],
    "grocery": [
        ("Daily Basket Mart", "سوق السلة اليومية"), ("Green Crate Grocers", "بقالة الصندوق الأخضر"),
        ("Corner Pantry", "بقالة الزاوية"), ("Fresh Dune Market", "سوق الكثبان"),
    ],
    "pharmacy": [
        ("Crescent Care Pharmacy", "صيدلية الهلال للرعاية"), ("Blue Dhow Pharmacy", "صيدلية المركب الأزرق"),
        ("Mint Leaf Pharmacy", "صيدلية ورقة النعناع"),
    ],
    "parcel": [("Jalboot Parcels", "طرود جالبوت")],
}

# name, Arabic name, lowest and highest price in QAR
ITEMS = {
    "food": [
        ("Chicken shawarma wrap", "شاورما دجاج", 15, 25), ("Mixed grill plate", "مشاوي مشكلة", 55, 85),
        ("Chicken biryani", "برياني دجاج", 28, 42), ("Lamb mandi", "مندي لحم", 48, 72),
        ("Hummus plate", "طبق حمص", 12, 20), ("Falafel box", "علبة فلافل", 10, 18),
        ("Karak tea", "شاي كرك", 3, 6), ("Cheese manakeesh", "مناقيش جبنة", 8, 14),
        ("Grilled hammour", "هامور مشوي", 60, 95), ("Fattoush salad", "سلطة فتوش", 14, 24),
        ("Lentil soup", "شوربة عدس", 9, 16),
    ],
    "grocery": [
        ("Milk 2 L", "حليب 2 لتر", 11, 15), ("Eggs, tray of 30", "بيض طبق 30", 16, 22),
        ("Arabic bread", "خبز عربي", 2, 4), ("Basmati rice 5 kg", "أرز بسمتي 5 كجم", 38, 55),
        ("Tomatoes 1 kg", "طماطم 1 كجم", 5, 9), ("Laban 1 L", "لبن 1 لتر", 6, 9),
        ("Dates 1 kg", "تمر 1 كجم", 25, 45), ("Cooking oil 1.8 L", "زيت طبخ 1.8 لتر", 14, 22),
    ],
    "pharmacy": [
        ("Paracetamol 500 mg", "باراسيتامول 500 ملغ", 6, 12), ("Vitamin D3", "فيتامين د3", 35, 60),
        ("Cough syrup", "شراب للسعال", 18, 32), ("Baby wipes", "مناديل أطفال", 12, 20),
        ("Hand sanitizer", "معقم يدين", 8, 15), ("Antibiotic course", "مضاد حيوي", 45, 90),
    ],
    "parcel": [
        ("Documents envelope", "ظرف مستندات", 15, 20), ("Small parcel", "طرد صغير", 20, 30),
        ("Medium parcel", "طرد متوسط", 30, 45),
    ],
}
PRESCRIPTION_ITEMS = {"Antibiotic course"}

DELAY_REASONS = (
    "merchant_backlog", "driver_traffic", "weather_dust", "high_demand", "address_problem",
    "driver_reassigned",
)

ITEM_TRANSLATIONS = {name: name_ar for group in ITEMS.values() for name, name_ar, _low, _high in group}
ZONE_AR = {name: name_ar for name, name_ar, _lat, _lng in ZONES}

TICKET_TOPICS = [
    # category, weight, English subject, Arabic subject
    ("late_delivery", 26, "Order arrived later than promised", "وصل الطلب متأخرا عن الموعد"),
    ("missing_item", 20, "Item missing from my order", "صنف ناقص من طلبي"),
    ("wrong_item", 11, "Received the wrong item", "استلمت صنفا خاطئا"),
    ("refund_status", 12, "Where is my refund", "أين وصل استرداد المبلغ"),
    ("promo_issue", 9, "Promo code did not work", "رمز الخصم لم يعمل"),
    ("address_change", 7, "Need to change delivery address", "أريد تغيير عنوان التوصيل"),
    ("payment_issue", 6, "Charged twice for one order", "تم خصم المبلغ مرتين"),
    ("driver_conduct", 4, "Complaint about the driver", "شكوى بخصوص المندوب"),
    ("pharmacy_prescription", 3, "Prescription order problem", "مشكلة في طلب وصفة طبية"),
    ("parcel_lost", 2, "Parcel not delivered", "لم يصل الطرد"),
]

SIMULATION_NOTICE = (
    "All customers, merchants, drivers, orders and tickets in this database are simulated. "
    "No record describes a real person or business."
)
