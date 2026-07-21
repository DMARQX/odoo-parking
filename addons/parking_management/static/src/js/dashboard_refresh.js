import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onWillUnmount } from "@odoo/owl";

patch(FormController.prototype, "parking_management.dashboard_refresh", {
    setup() {
        this._super();
        if (this.props.modelName !== "parking.dashboard") return;

        const orm = useService("orm");
        const timer = setInterval(async () => {
            const root = this.model.root;
            if (!root || root.isNew || !root.resId) return;
            await orm.call(root.resModel, "compute", [[root.resId]]);
            await this.model.load();
        }, 5000);

        onWillUnmount(() => clearInterval(timer));
    },
});
