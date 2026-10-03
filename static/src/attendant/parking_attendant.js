/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { scanBarcode } from "@web/core/barcode/barcode_dialog";
import { isBarcodeScannerSupported } from "@web/core/barcode/barcode_video_scanner";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const REFRESH_MS = 60000;

export class ParkingAttendant extends Component {
    static template = "parking_management.ParkingAttendant";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.scannerSupported = isBarcodeScannerSupported();
        this.state = useState({
            board: { client_out: [], occupied: [], reserved: [] },
            tab: "client_out",
            search: "",
            selected: null,
            canOperate: false,
            loading: true,
        });
        onWillStart(async () => {
            await this.load();
            const scanned = await this.orm.call("parking.attendant", "pop_scan", []);
            if (scanned) {
                await this.select(scanned);
            }
        });
        this.timer = setInterval(() => this.load(), REFRESH_MS);
        onWillUnmount(() => clearInterval(this.timer));
    }

    get tabs() {
        return [
            { key: "client_out", label: _t("With customers"), icon: "fa-road" },
            { key: "occupied", label: _t("In spots"), icon: "fa-car" },
            { key: "reserved", label: _t("Awaiting arrival"), icon: "fa-bookmark" },
        ];
    }

    get items() {
        return this.state.board[this.state.tab] || [];
    }

    async load() {
        const res = await this.orm.call("parking.attendant", "get_board", [this.state.search]);
        this.state.board = res.board;
        this.state.canOperate = res.can_operate;
        this.state.loading = false;
        if (this.state.selected) {
            const fresh = Object.values(res.board).flat().find((i) => i.spot_id === this.state.selected.spot_id);
            this.state.selected = fresh || null;
        }
    }

    async onSearch(ev) {
        if (ev && ev.key && ev.key !== "Enter") {
            return;
        }
        const code = this.state.search.trim();
        if (code) {
            // A full plate, spot number or pasted QR link opens that car directly.
            const spotId = await this.orm.call("parking.attendant", "resolve", [code]);
            if (spotId) {
                this.state.search = "";
                await this.load();
                return this.select(spotId);
            }
        }
        await this.load();
    }

    async scan() {
        let code;
        try {
            code = await scanBarcode(this.env);
        } catch (e) {
            this.notification.add(e.message || _t("The camera could not be opened."), { type: "danger" });
            return;
        }
        if (!code) {
            return;
        }
        const spotId = await this.orm.call("parking.attendant", "resolve", [code]);
        if (!spotId) {
            this.notification.add(_t("No vehicle or spot found for this code."), { type: "warning" });
            return;
        }
        await this.select(spotId);
    }

    async select(spotId) {
        this.state.selected = await this.orm.call("parking.attendant", "get_spot", [spotId]);
        const tab = this.state.selected.status;
        if (this.state.board[tab]) {
            this.state.tab = tab;
        }
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    setTab(key) {
        this.state.tab = key;
    }

    closeDetail() {
        this.state.selected = null;
    }

    async run(operation) {
        const item = this.state.selected;
        const action = await this.orm.call("parking.attendant", "run", [item.spot_id, operation]);
        if (action) {
            await this.action.doAction(action, {
                onClose: async () => {
                    await this.load();
                    if (this.state.selected) {
                        await this.select(item.spot_id);
                    }
                },
            });
        }
    }

    async newReception() {
        const action = await this.orm.call("parking.attendant", "new_reception", []);
        await this.action.doAction(action, { onClose: () => this.load() });
    }

    daysClass(item) {
        if (item.days_left === false || item.days_left === null) {
            return "";
        }
        return item.days_left < 0 ? "o_pm_days_late" : item.days_left <= 7 ? "o_pm_days_soon" : "";
    }
}

registry.category("actions").add("parking_management.attendant", ParkingAttendant);
