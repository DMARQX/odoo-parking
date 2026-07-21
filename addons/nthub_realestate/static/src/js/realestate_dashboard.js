/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, onMounted, useRef, useState } = owl;

class RealEstateDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            dashboardData: {},
        });

        // Refs for our chart containers in the XML template
        this.unitStatusChart = useRef('unitStatusChart');
        this.projectStatusChart = useRef('projectStatusChart');
        this.monthlyRevenueChart = useRef('monthlyRevenueChart');

        onWillStart(async () => {
            // Call our Python method to get all dashboard data at once
            const data = await this.orm.call(
                'real.estate.dashboard.data',
                'get_real_estate_dashboard_data',
                []
            );
            this.state.dashboardData = data;
        });

        onMounted(() => {
            // When the component is in the DOM, render the charts
            this.renderUnitStatusChart();
            this.renderProjectStatusChart();
            this.renderMonthlyRevenueChart();
        });
    }

    // This function makes the KPI cards clickable
    openListView(res_model, domain, name) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: name,
            res_model: res_model,
            domain: domain,
            views: [[false, 'list'], [false, 'kanban'], [false, 'form']],
            target: 'current',
        });
    }

    // --- Chart Rendering Functions ---

    renderUnitStatusChart() {
        const { labels, values } = this.state.dashboardData.unit_status_chart;
        const options = {
            series: values,
            labels: labels,
            chart: { type: 'donut', height: 350 },
            colors: ['#28a745', '#007bff', '#ffc107', '#dc3545'], // Available, Rented, Booked, Sold
            legend: { position: 'bottom' },
            dataLabels: { enabled: true },
        };
        this.renderGraph(this.unitStatusChart.el, options);
    }

    renderProjectStatusChart() {
        const { labels, values } = this.state.dashboardData.project_status_chart;
        const options = {
            series: [{ name: 'Projects', data: values }],
            chart: { type: 'bar', height: 350 },
            xaxis: { categories: labels },
            yaxis: { title: { text: 'Number of Projects' } },
            plotOptions: { bar: { distributed: true, horizontal: false } },
            legend: { show: false },
            dataLabels: { enabled: false },
        };
        this.renderGraph(this.projectStatusChart.el, options);
    }

    renderMonthlyRevenueChart() {
        const { labels, values } = this.state.dashboardData.monthly_revenue_chart;
        const options = {
            series: [{ name: 'Rental Revenue', data: values }],
            chart: { type: 'area', height: 350, zoom: { enabled: false } },
            stroke: { curve: 'smooth' },
            xaxis: { type: 'category', categories: labels },
            yaxis: { title: { text: 'Revenue' } },
            dataLabels: { enabled: false },
        };
        this.renderGraph(this.monthlyRevenueChart.el, options);
    }

    // Generic function to render any chart
    renderGraph(el, options) {
        if (!el) return;
        const chart = new ApexCharts(el, options);
        chart.render();
    }
}

RealEstateDashboard.template = "nthub_realestate.RealEstateDashboardTemplate";
registry.category("actions").add("real_estate_dashboard_action", RealEstateDashboard);