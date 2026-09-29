/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatMonetary } from "@web/views/fields/formatters";

const REFRESH_MS = 60000;

// One colour per spot status, reused by every chart and badge on the page.
export const STATUS_COLORS = {
    available: "#2e9d5b",
    reserved: "#2f80c2",
    occupied: "#e8872b",
    client_out: "#7b56c2",
    maintenance: "#8a8f98",
};

export class ParkingChart extends Component {
    static template = "parking_management.ParkingChart";
    static props = {
        config: Object,
        height: { type: Number, optional: true },
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;
        useEffect(
            () => {
                this.chart = new Chart(this.canvasRef.el, this.props.config);
                return () => this.chart && this.chart.destroy();
            },
            () => [this.props.config]
        );
    }
}

export class ParkingDashboard extends Component {
    static template = "parking_management.Dashboard";
    static components = { ParkingChart };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.STATUS_COLORS = STATUS_COLORS;
        this.state = useState({
            data: null,
            loading: true,
            locationId: false,
            period: "month",
            lastUpdate: null,
        });
        this.periods = [
            ["today", _t("Today")],
            ["week", _t("This Week")],
            ["month", _t("This Month")],
            ["quarter", _t("This Quarter")],
            ["year", _t("This Year")],
        ];
        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.load();
        });
        onMounted(() => {
            this.timer = setInterval(() => this.load(true), REFRESH_MS);
        });
        onWillUnmount(() => clearInterval(this.timer));
    }

    // ------------------------------------------------------------------ data
    async load(silent = false) {
        if (!silent) {
            this.state.loading = true;
        }
        const data = await this.orm.call("parking.dashboard", "get_dashboard_data", [], {
            location_id: this.state.locationId || false,
            period: this.state.period,
        });
        this.state.data = data;
        this.state.loading = false;
        this.state.lastUpdate = new Date().toLocaleTimeString();
    }

    onLocationChange(ev) {
        this.state.locationId = parseInt(ev.target.value) || false;
        this.load();
    }

    setPeriod(period) {
        this.state.period = period;
        this.load();
    }

    get data() {
        return this.state.data;
    }

    get periodLabel() {
        return (this.periods.find((p) => p[0] === this.state.period) || [])[1];
    }

    money(value) {
        return formatMonetary(value || 0, { currencyId: this.data.currency_id });
    }

    get locDomain() {
        return [["location_id", "in", this.data.location_ids]];
    }

    // --------------------------------------------------------------- actions
    openList(resModel, name, domain, { views = ["list", "form"], context = {} } = {}) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: resModel,
            views: views.map((v) => [false, v]),
            domain,
            context,
            target: "current",
        });
    }

    openRecord(resModel, resId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openSpots(status) {
        const domain = [...this.locDomain];
        if (status) {
            domain.push(["status", "=", status]);
        }
        this.openList("parking.spot", _t("Parking Spots"), domain, { views: ["kanban", "list", "form"] });
    }

    openContracts(kind) {
        const domain = [...this.locDomain];
        const today = this.data.today;
        const names = {
            active: _t("Active Contracts"),
            confirmed: _t("Contracts to Activate"),
            draft: _t("Draft Contracts"),
            expiring: _t("Contracts Expiring Soon"),
            past_end: _t("Contracts Past End Date"),
            new: _t("New Contracts"),
        };
        if (["active", "confirmed", "draft"].includes(kind)) {
            domain.push(["state", "=", kind]);
        } else if (kind === "expiring") {
            domain.push(["is_expiring_soon", "=", true]);
        } else if (kind === "past_end") {
            domain.push(["state", "in", ["active", "confirmed"]], ["end_date", "<", today]);
        } else if (kind === "new") {
            domain.push(["create_date", ">=", this.data.date_from + " 00:00:00"]);
        }
        this.openList("parking.contract", names[kind] || _t("Contracts"), domain, {
            views: ["list", "kanban", "form"],
        });
    }

    openMovements(kind) {
        const domain = [...this.locDomain];
        const start = this.data.today + " 00:00:00";
        if (kind === "out_today") {
            domain.push(["check_out_time", ">=", start]);
        } else if (kind === "in_today") {
            domain.push(["check_in_time", ">=", start]);
        } else if (kind === "period") {
            domain.push(["check_out_time", ">=", this.data.date_from + " 00:00:00"]);
        }
        this.openList("parking.vehicle.movement", _t("Vehicle Movements"), domain);
    }

    openWashes() {
        this.openList("parking.contract.wash", _t("Car Washes"), [
            ...this.locDomain,
            ["state", "=", "done"],
            ["wash_date", ">=", this.data.date_from + " 00:00:00"],
        ]);
    }

    openLowStock() {
        this.openList("parking.branch.stock", _t("Low Stock"), [...this.locDomain, ["is_low", "=", true]]);
    }

    openInvoices(kind) {
        const domain = [
            ["parking_contract_id", "!=", false],
            ["parking_location_id", "in", this.data.location_ids],
            ["move_type", "in", ["out_invoice", "out_refund"]],
            ["state", "=", "posted"],
        ];
        if (kind === "period") {
            domain.push(["invoice_date", ">=", this.data.date_from]);
        } else if (kind === "open") {
            domain.push(["payment_state", "in", ["not_paid", "partial"]]);
        } else if (kind === "overdue") {
            domain.push(["payment_state", "in", ["not_paid", "partial"]], ["invoice_date_due", "<", this.data.today]);
        }
        this.openList("account.move", _t("Parking Invoices"), domain, { context: { create: false } });
    }

    openPartnerInvoices(partnerId) {
        this.openList("account.move", _t("Open Invoices"), [
            ["parking_contract_id", "!=", false],
            ["partner_id", "=", partnerId],
            ["move_type", "=", "out_invoice"],
            ["state", "=", "posted"],
            ["payment_state", "in", ["not_paid", "partial"]],
        ], { context: { create: false } });
    }

    newContract() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "parking.contract",
            views: [[false, "form"]],
            target: "current",
        });
    }

    reception(operation) {
        this.actionService.doAction("parking_management.action_parking_reception_wizard", {
            additionalContext: { default_operation: operation },
        });
    }

    // ---------------------------------------------------------------- charts
    get statusChart() {
        const rows = this.data.charts.spot_status;
        return {
            type: "doughnut",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [{
                    data: rows.map((r) => r.value),
                    backgroundColor: rows.map((r) => STATUS_COLORS[r.key]),
                    borderWidth: 2,
                }],
            },
            options: {
                maintainAspectRatio: false,
                cutout: "62%",
                plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
                onClick: (ev, elements) => {
                    if (elements.length) {
                        this.openSpots(rows[elements[0].index].key);
                    }
                },
            },
        };
    }

    get branchChart() {
        const branches = this.data.charts.branches;
        const statuses = this.data.charts.spot_status;
        return {
            type: "bar",
            data: {
                labels: branches.map((b) => b.name),
                datasets: statuses.map((s) => ({
                    label: s.label,
                    data: branches.map((b) => b[s.key] || 0),
                    backgroundColor: STATUS_COLORS[s.key],
                    borderRadius: 4,
                })),
            },
            options: {
                maintainAspectRatio: false,
                indexAxis: branches.length > 5 ? "y" : "x",
                scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } },
                plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
                onClick: (ev, elements) => {
                    if (elements.length) {
                        const branch = branches[elements[0].index];
                        this.openList("parking.spot", branch.name, [["location_id", "=", branch.id]], {
                            views: ["kanban", "list", "form"],
                        });
                    }
                },
            },
        };
    }

    get movementChart() {
        const m = this.data.charts.movements;
        return {
            type: "line",
            data: {
                labels: m.labels.map((d) => d.slice(5)),
                datasets: [
                    {
                        label: _t("Delivered (out)"),
                        data: m.out,
                        borderColor: STATUS_COLORS.client_out,
                        backgroundColor: "rgba(123, 86, 194, 0.15)",
                        fill: true,
                        tension: 0.35,
                    },
                    {
                        label: _t("Received (in)"),
                        data: m.in,
                        borderColor: STATUS_COLORS.available,
                        backgroundColor: "rgba(46, 157, 91, 0.12)",
                        fill: true,
                        tension: 0.35,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
                onClick: (ev, elements) => {
                    if (elements.length) {
                        const day = m.labels[elements[0].index];
                        this.openList("parking.vehicle.movement", _t("Vehicle Movements"), [
                            ...this.locDomain,
                            ["check_out_time", ">=", day + " 00:00:00"],
                            ["check_out_time", "<=", day + " 23:59:59"],
                        ]);
                    }
                },
            },
        };
    }

    get trendChart() {
        const revenue = this.data.charts.revenue;
        if (revenue) {
            return {
                type: "bar",
                data: {
                    labels: revenue.labels,
                    datasets: [
                        {
                            label: _t("Invoiced (untaxed)"),
                            data: revenue.invoiced,
                            backgroundColor: "#2f80c2",
                            borderRadius: 4,
                        },
                        {
                            label: _t("Still due"),
                            data: revenue.due,
                            backgroundColor: "#e8872b",
                            borderRadius: 4,
                        },
                    ],
                },
                options: {
                    maintainAspectRatio: false,
                    scales: { y: { beginAtZero: true } },
                    plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
                },
            };
        }
        const c = this.data.charts.contracts_by_month;
        return {
            type: "bar",
            data: {
                labels: c.labels,
                datasets: [{
                    label: _t("New contracts"),
                    data: c.values,
                    backgroundColor: "#2f80c2",
                    borderRadius: 4,
                }],
            },
            options: {
                maintainAspectRatio: false,
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                plugins: { legend: { display: false } },
            },
        };
    }

    formatHours(hours) {
        if (hours >= 24) {
            return _t("%(days)sd %(hours)sh", { days: Math.floor(hours / 24), hours: Math.round(hours % 24) });
        }
        return _t("%(hours)sh", { hours: Math.round(hours * 10) / 10 });
    }

    daysLabel(days) {
        if (days < 0) {
            return _t("%(days)s days late", { days: -days });
        }
        return _t("%(days)s days left", { days });
    }

    invoiceCountLabel(count) {
        return _t("%(count)s invoices", { count });
    }

    waitingClass(hours) {
        if (hours > 24) {
            return "text-bg-danger";
        }
        if (hours > 4) {
            return "text-bg-warning";
        }
        return "text-bg-light";
    }
}

registry.category("actions").add("parking_management.dashboard", ParkingDashboard);
