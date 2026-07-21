# Terms & Conditions Template Feature - README

## ✅ Feature Successfully Implemented!

### 📋 What Was Added

A complete **Terms & Conditions Template System** for rental quotations with the following components:

---

## 🎯 Features

### 1. **Template Management**
- Create reusable terms & conditions templates
- Support for **Arabic** and **English** content
- HTML rich text editor for formatting
- Template types: Residential, Commercial, General
- Active/Inactive status control

### 2. **Quotation Integration**
- Select template from dropdown in quotation form
- Auto-fill terms & conditions when template is selected
- Edit terms after selection (fully customizable per quotation)
- Bilingual interface (Arabic/English)

### 3. **Print Reports**
- Terms & conditions appear in **Arabic PDF Report**
- Terms & conditions appear in **English PDF Report**
- Professional formatting with border and styling
- Only shows if terms_conditions field has content

### 4. **Security & Access**
- Users: Read templates only
- Managers: Full CRUD access
- Admins: Full CRUD access

---

## 🚀 How to Use

### **Step 1: Create Templates**
1. Go to: `Real Estate → Configuration → Terms & Conditions`
2. Click **Create**
3. Fill in:
   - **Template Name**: e.g., "شروط العقود السكنية"
   - **Template Type**: Residential/Commercial/General
   - **Content**: Write your terms in HTML editor (supports Arabic/English)
4. Save

### **Step 2: Use in Quotations**
1. Open any quotation (new or existing)
2. Go to **"Terms & Conditions / الشروط والأحكام"** tab
3. Select template from **"اختر قالب / Select Template"** dropdown
4. Content auto-fills into the editor
5. Modify if needed
6. Save quotation

### **Step 3: Print**
1. Click **Print** button on quotation
2. Select **"Arabic Rental Quotation"** or **"English Rental Quotation"**
3. PDF will include terms & conditions at the bottom

---

## 📦 Pre-loaded Templates

The system comes with **4 demo templates**:

1. **شروط العقود السكنية** (Arabic Residential)
   - Payment terms
   - Subletting policy
   - Maintenance responsibilities
   - Security deposit rules

2. **شروط العقود التجارية** (Arabic Commercial)
   - Payment schedule
   - License requirements
   - Signage policies
   - Operating hours

3. **Residential Terms & Conditions** (English)
   - Same as Arabic residential (translated)

4. **Commercial Terms & Conditions** (English)
   - Same as Arabic commercial (translated)

---

## 📁 Files Modified/Created

### **New Files:**
```
rental_quotation/
├── models/quotation_terms_template.py          ✅ NEW
├── views/quotation_terms_template_views.xml    ✅ NEW
└── data/quotation_terms_templates.xml          ✅ NEW (4 demo templates)
```

### **Modified Files:**
```
rental_quotation/
├── models/__init__.py                          ✏️ Added import
├── models/rental_quotation.py                  ✏️ Added fields + onchange
├── views/rental_quotation_views.xml            ✏️ Added template selector
├── report/rental_quotation_arabic_style_report.xml  ✏️ Added terms section
├── security/ir.model.access.csv                ✏️ Added permissions
└── __manifest__.py                             ✏️ Added new files
```

---

## 🎨 User Interface

### **Quotation Form (Terms Tab):**
```
┌──────────────────────────────────────┐
│ Template Selection / اختيار القالب  │
├──────────────────────────────────────┤
│ [Select Template ▼]                  │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ Terms & Conditions / الشروط والأحكام │
├──────────────────────────────────────┤
│ [Rich HTML Editor]                   │
│ - Bold, Italic, Lists                │
│ - Arabic/English support             │
└──────────────────────────────────────┘
```

### **Printed Report:**
```
┌──────────────────────────────────────┐
│   [Quotation Header & Table]         │
├──────────────────────────────────────┤
│                                      │
│   الشروط والأحكام                    │
│   ═══════════════════════════════   │
│                                      │
│   1. الدفع: يجب دفع المبلغ...       │
│   2. التأخير: في حالة التأخر...     │
│   3. التنازل: لا يحق للمستأجر...    │
│                                      │
└──────────────────────────────────────┘
```

---

## ⚙️ Technical Details

### **Model: `quotation.terms.template`**
```python
Fields:
- name: Template name (translatable)
- content_html: HTML content (translatable)
- template_type: residential/commercial/general
- sequence: Display order
- active: Active/Archive status
- company_id: Multi-company support
```

### **Added to `rental.quotation`:**
```python
Fields:
- terms_template_id: Many2one to template
- terms_conditions: Html field (enhanced)

Methods:
- @api.onchange('terms_template_id'): Auto-fill content
```

---

## 🔧 Troubleshooting

**Q: Template not appearing in dropdown?**
- Check if template is **Active** (not archived)
- Verify user has read permissions

**Q: Terms not showing in PDF?**
- Make sure `terms_conditions` field has content
- Re-print the quotation

**Q: Can't edit templates?**
- Contact system administrator for Manager/Admin access

---

## 📞 Support

For issues or questions, contact the development team.

---

**Version:** 18.0.1.0.0  
**Last Updated:** December 6, 2025  
**Status:** ✅ Production Ready
