# وظيفة تحويل الكوتيشن إلى حجوزات
## Quotation to Reservations Conversion Feature

## الوصف / Description

تم إضافة وظيفة تلقائية لإنشاء حجوزات (Reservations) عند تحويل الكوتيشن إلى عقد. عند الضغط على زر "Convert to Contract" في الكوتيشن المقبول، يقوم النظام بالآتي:

When you click "Convert to Contract" on an accepted quotation, the system automatically:

## الخطوات / Steps

### 1. إنشاء حجز لكل وحدة / Create Reservation Per Unit
- يتم إنشاء حجز منفصل لكل سطر (line) في الكوتيشن
- كل حجز يرتبط بوحدة واحدة (unit) من الـ Quotation Lines
- Each quotation line creates one reservation automatically

### 2. البيانات المنقولة / Transferred Data
يتم نقل البيانات التالية من الكوتيشن إلى الحجز:
- **quotation_id**: رابط للكوتيشن الأصلي
- **rs_project**: المشروع
- **rs_project_unit**: الوحدة المحجوزة
- **partner_id**: العميل
- **pricing**: السعر النهائي للوحدة
- **state**: حالة الحجز تصبح "confirmed" مباشرة
- تحديث حالة الوحدة إلى "reserved"

### 3. رقم الكوتيشن في الحجز / Quotation Number in Reservation
- يظهر رقم الكوتيشن في فورم الحجز
- يمكن رؤية رقم الكوتيشن في قائمة الحجوزات (Quotation Number column)
- The quotation number appears in both form and list views

### 4. عرض الحجوزات من الكوتيشن / View Reservations from Quotation
- زر "Reservations" يظهر في فورم الكوتيشن بعد التحويل
- الزر يعرض عدد الحجوزات المنشأة
- الضغط على الزر يفتح قائمة بجميع الحجوزات المرتبطة
- Smart button shows reservation count and opens related reservations

## حقول جديدة / New Fields

### في الحجز (unit.reservation):
- `quotation_id`: Many2one → rental.quotation (readonly)
- `quotation_name`: Char (related field from quotation_id.name)

### في الكوتيشن (rental.quotation):
- `reservation_ids`: One2many → unit.reservation
- `reservation_count`: Integer (computed)

## الأمان / Security
- يتم التحقق من توفر الوحدات قبل الحجز
- إذا كانت أي وحدة غير متاحة (not free)، يظهر خطأ ولا يتم إنشاء أي حجوزات
- All reservations are created in 'confirmed' state
- Properties are marked as 'reserved' automatically

## التحديث / Update Module
لتفعيل الوظيفة الجديدة:

```bash
# تحديث المودويلات
python3 odoo-bin -u rental_quotation,nthub_realestate -d database_name

# أو عبر الواجهة
Apps → Update Apps List → Upgrade rental_quotation & nthub_realestate
```

## مثال / Example

إذا كان الكوتيشن يحتوي على **3 وحدات**:
- Unit A (Floor 1, 100 sqm)
- Unit B (Floor 2, 120 sqm)
- Unit C (Floor 3, 95 sqm)

عند التحويل، يتم إنشاء **3 حجوزات** منفصلة:
1. Reservation RES/001 → Unit A (shows quotation number)
2. Reservation RES/002 → Unit B (shows quotation number)
3. Reservation RES/003 → Unit C (shows quotation number)

جميع الحجوزات تعرض في الكوتيشن عبر زر "Reservations" (3)

## ملاحظات / Notes

1. **متعدد الوحدات**: الكوتيشن يمكن أن يحتوي على أي عدد من الوحدات
2. **التتبع**: يمكن تتبع رقم الكوتيشن من الحجز
3. **الحالة**: الحجوزات تنشأ في حالة "confirmed" مباشرة
4. **الربط الثنائي**: يمكن الانتقال من الكوتيشن → الحجوزات والعكس

---
**التاريخ**: November 29, 2025  
**الإصدار**: 18.0.1.0.0
