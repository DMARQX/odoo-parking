/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
// 1. قم باستيراد onMounted
import { Component, onMounted } from "@odoo/owl";

const actionRegistry = registry.category("actions");

class RealEstateDashboard extends Component {
    setup() {
        super.setup();
        this.orm = useService("orm");

        // 2. انقل استدعاء الدالة إلى داخل onMounted
        // هذا يضمن أن الكود سيعمل بعد أن تكون الصفحة جاهزة بالكامل
        onMounted(() => {
            this._loadData();
        });
    }

    async _loadData() {
        try {
            const data = await this.orm.call("rs.project", "get_dashboard_data", [], {});

            // 3. (أفضل ممارسة) تحقق دائمًا من وجود العناصر قبل استخدامها
            const totalSoldEl = document.getElementById("total_sold");
            if (totalSoldEl) {
                totalSoldEl.innerHTML = `<span>${data.total_sold}</span>`;
            }

            const delayedSettlementsEl = document.getElementById("delayed_settlements");
            if (delayedSettlementsEl) {
                delayedSettlementsEl.innerHTML = `<span>${data.delayed}</span>`;
            }
        } catch (error) {
            console.error("Failed to load dashboard data:", error);
        }
    }
}

RealEstateDashboard.template = "nthub_realestate.RealEstateDashboard";
actionRegistry.add("real_estate_dashboard_tag", RealEstateDashboard);