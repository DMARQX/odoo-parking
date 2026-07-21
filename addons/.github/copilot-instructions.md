# Copilot Instructions for Saqifaa Real Estate System

## Project Overview
This is an **Odoo 18** workspace containing custom modules for a real estate management system. The system manages properties, rental contracts, ownership contracts, quotations, and portal access for owners and tenants.

## Core Modules

### 1. `nthub_realestate` - Main Real Estate Module
- **Purpose**: Comprehensive real estate management with properties, contracts, reservations, and portals
- **Key Models**:
  - `rs.project` (MainProperty): Projects/buildings with units (`subproperties_ids`)
  - `sub.property` (SubProperty): Individual rental/sale units within projects
  - `rental.contract`: Rental agreements with installment lines (`rental_line_ids`)
  - `ownership.contract`: Sale/ownership contracts with payment schedules
  - `unit.reservation`: Property reservations that convert to contracts
  - `owner.request`, `rental.maintenance.request`: Portal-submitted requests
  
- **Portal Architecture**:
  - **Owner Portal** (`controllers/owner_portal.py`): Property owners view projects, units, payments, submit requests
    - Decorator: `@owner_only` - restricts access to `partner.is_owner` users
    - Routes: `/my/properties`, `/my/property/<id>`, `/my/collected-payments`, `/my/requests`
  - **Tenant Portal** (`controllers/portal.py`): Tenants view contracts, submit maintenance requests
    - Decorator: `@tenant_only` - restricts access to `partner.is_tenant` users
    - Routes: `/my/rental_contracts`, `/my/rental_contract/<id>`, `/my/maintenance_requests`

### 2. `rental_quotation` - Quotation Workflow Module
- **Purpose**: Create rental quotations with multi-level approval workflow before contract conversion
- **Key Features**:
  - Configurable approval rules (`rental.approval.rule`) based on amount, discount, user role
  - State flow: `draft → submitted → under_review → approved → sent → accepted → converted`
  - **Auto-converts to reservations**: When quotation converts to contract, creates `unit.reservation` records for each quotation line (see `QUOTATION_TO_RESERVATION.md`)
  - Configurable terms templates (`quotation.terms.template`) for Arabic/English content

### 3. `hr_contract_allowances` - HR Extension
- Adds allowance types (housing, transport, etc.) to employee contracts
- Separate from real estate logic

## Critical Patterns & Conventions

### Service Fee Calculation Architecture
Service fees are **percentage-based** and computed at multiple levels:

1. **Project Level** (`rs.project.project_service_fee_percent`): Default % for all units in project
2. **Unit Level** (`sub.property.service_fee`): Computed as `rental_fee × (project_service_fee_percent / 100)`
   - Decorated with `@api.depends('rental_fee', 'rs_project_area', 'project_service_fee_percent')`
   - Formula: `rental_fee = (rental_price_per_sqm + electricity_price_per_sqm) × rs_project_area`
3. **Contract Level** (`rental.contract.service_fee`): Can be monthly or one-time
   - `service_monthly` boolean controls if charged every month
   - `total_rental_fee = rental_fee + service_fee` (per period)
   - `total_contract_value` sums all fees over entire contract duration

**When editing pricing**: Always update computed fields with `@api.depends` and use `store=True` for performance.

### Bilingual Implementation (Arabic/English)
- **Field Labels**: Use `string=_("English") / العربية` pattern in models
- **Reports**: Separate templates for Arabic (`report/*_arabic_style_report.xml`) and English
- **Views**: Arabic labels in XML, e.g., `string="Service Fee / رسوم الخدمة"`
- **User Content**: Store Arabic/English in separate fields (e.g., `quotation_terms_template`)

### Odoo 18 Specifics
- **Manifest structure**: Use `'depends'`, `'data'`, `'assets'` (no more `'qweb'`)
- **Assets loading**: Define JS/CSS in `'assets': {'web.assets_backend': [...]}`
- **State selection**: Use tuple format: `[('draft', 'Draft'), ('confirmed', 'Confirmed')]`
- **Sequence generation**: Use `ir.sequence` with `@api.model_create_multi` or default lambda
- **Mail tracking**: Inherit `['mail.thread', 'mail.activity.mixin']` for chatter

### View & Menu Structure
- **Menu hierarchy**: Root → Sections → Actions (see `nthub_realestate/views/menu_views.xml`)
  - Actions must be defined **before** menuitem references them
  - Use `sequence` for ordering (lower = higher priority)
- **Dashboard**: Custom client action with tag `real_estate_dashboard_action` (JS in `static/src/js/`)
- **Smart buttons**: Use `<button>` with `type="object"` and icon/count display

### Security Model
- **ir.model.access.csv**: Most models have full CRUD for all users (`1,1,1,1`)
- **Custom groups**: `rental_quotation` uses hierarchical groups (User → Approver → Manager → Admin)
- **Portal decorators**: Always use `@owner_only` or `@tenant_only` for portal routes
- **Portal user creation**: Use `base.group_portal` and send credentials via email templates

## Development Workflows

### Adding New Features
1. **Model**: Create in `models/` with `_name`, `_inherit`, `_description`
2. **Security**: Add line to `security/ir.model.access.csv` (format: `id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink`)
3. **Views**: Create in `views/` folder, define actions before menus
4. **Manifest**: Add data files in load order: security → data → views → reports

### Testing Contracts & Quotations
- **Test quotation flow**: Draft → Submit → Approve → Convert (creates reservations automatically)
- **Test contract calculations**: Use `action_calculate()` method to regenerate payment lines
- **Check portal access**: Create portal users for owners/tenants to test routes

### Working with Computed Fields
- Always use `@api.depends()` decorator with exact field dependencies
- Add `store=True` for fields used in searches/grouping
- Use `compute_sudo=True` if reading related models with restricted access
- For monetary fields, ensure `currency_id` field exists (usually `related='company_id.currency_id'`)

### Debugging Portal Issues
- Check decorator (`@owner_only` vs `@tenant_only`) matches user type
- Verify `partner.is_owner` or `partner.is_tenant` boolean is set
- Ensure portal user has correct email/login credentials
- Look at `_prepare_home_portal_values()` for counter logic

## Common Pitfalls
- **Don't hardcode user IDs** - use `self.env.user` or `default=lambda self: self.env.user`
- **Don't skip `sudo()`** in portal controllers - portal users have limited access
- **Don't forget `tracking=True`** on important status fields for audit trail
- **Don't modify computed fields directly** - change their dependencies instead
- **Arabic text direction**: Use RTL CSS classes for Arabic content in portal templates

## Key Files for Reference
- **Main menu**: `nthub_realestate/views/menu_views.xml`
- **Service fee logic**: `nthub_realestate/models/sub_property.py` (lines 135-148)
- **Contract calculation**: `nthub_realestate/models/rental_contract.py` (`action_calculate` method)
- **Portal decorators**: `nthub_realestate/controllers/owner_portal.py` (line 10), `portal.py` (line 11)
- **Quotation to reservation**: `rental_quotation/models/rental_quotation.py` (`action_convert_to_contract`)

## Module Structure Convention
```
module_name/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── model_name.py
├── views/
│   ├── model_views.xml
│   └── menu_views.xml
├── security/
│   └── ir.model.access.csv
├── data/
│   └── sequence_data.xml
├── report/
│   └── report_template.xml
└── static/
    └── src/
        ├── js/
        ├── scss/
        └── xml/
```

## Questions for Clarification
- Should new features follow the existing open security model (all users have CRUD) or implement role-based access?
- Are there specific coding standards for Arabic variable names vs English?
- What's the testing/staging deployment process for these modules?
