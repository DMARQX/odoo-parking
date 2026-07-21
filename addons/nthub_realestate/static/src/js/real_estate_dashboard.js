/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

class RealEstateDashboard extends Component {
    static template = "nthub_realestate.RealEstateDashboardTemplate";
}

registry.category("actions").add("real_estate_dashboard", RealEstateDashboard);
