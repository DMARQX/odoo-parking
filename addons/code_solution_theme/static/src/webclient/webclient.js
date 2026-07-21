/** @odoo-module **/

import { WebClient } from "@web/webclient/webclient";
import { patch } from "@web/core/utils/patch";

// Code Solution Theme - WebClient customization
patch(WebClient.prototype, {
    setup() {
        super.setup();
        console.log("Code Solution Theme loaded successfully");
    }
});
