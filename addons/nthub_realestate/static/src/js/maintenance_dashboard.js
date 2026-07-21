/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, onMounted, useRef, useState } = owl;

class MaintenanceDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            dashboardData: {},
        });

        // Refs for chart containers
        this.requestTypeChart = useRef('requestTypeChart');
        this.requestStatusChart = useRef('requestStatusChart');
        this.jobStatusChart = useRef('jobStatusChart');
        this.priorityChart = useRef('priorityChart');
        this.monthlyTrendChart = useRef('monthlyTrendChart');
        this.jobTypeChart = useRef('jobTypeChart');

        onWillStart(async () => {
            const data = await this.orm.call(
                'maintenance.dashboard.data',
                'get_maintenance_dashboard_data',
                []
            );
            this.state.dashboardData = data;
        });

        onMounted(() => {
            this.renderRequestTypeChart();
            this.renderRequestStatusChart();
            this.renderJobStatusChart();
            this.renderPriorityChart();
            this.renderMonthlyTrendChart();
            this.renderJobTypeChart();
        });
    }

    // Open list view when KPI card is clicked
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

    // Open form view for specific record
    openFormView(res_model, res_id, name) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: name,
            res_model: res_model,
            res_id: res_id,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    // --- Chart Rendering Functions ---

    renderRequestTypeChart() {
        const data = this.state.dashboardData.request_type_chart;
        if (!data || !data.labels.length) return;
        
        const options = {
            series: data.values,
            labels: data.labels,
            chart: { type: 'donut', height: 300 },
            colors: ['#ff6384', '#36a2eb', '#ffce56', '#4bc0c0', '#9966ff', '#ff9f40'],
            legend: { position: 'bottom' },
            dataLabels: { enabled: true },
            plotOptions: {
                pie: {
                    donut: {
                        labels: {
                            show: true,
                            total: {
                                show: true,
                                label: 'Total',
                                fontSize: '14px',
                            }
                        }
                    }
                }
            }
        };
        this.renderGraph(this.requestTypeChart.el, options);
    }

    renderRequestStatusChart() {
        const data = this.state.dashboardData.request_status_chart;
        if (!data || !data.labels.length) return;
        
        const options = {
            series: [{ name: 'Requests', data: data.values }],
            chart: { type: 'bar', height: 300 },
            xaxis: { categories: data.labels },
            yaxis: { title: { text: 'Number of Requests' } },
            plotOptions: { 
                bar: { 
                    distributed: true, 
                    horizontal: false,
                    borderRadius: 4,
                } 
            },
            colors: ['#6c757d', '#17a2b8', '#ffc107', '#007bff', '#28a745', '#fd7e14', '#dc3545', '#20c997', '#6610f2', '#e83e8c'],
            legend: { show: false },
            dataLabels: { enabled: true },
        };
        this.renderGraph(this.requestStatusChart.el, options);
    }

    renderJobStatusChart() {
        const data = this.state.dashboardData.job_status_chart;
        if (!data || !data.labels.length) return;
        
        const options = {
            series: [{ name: 'Jobs', data: data.values }],
            chart: { type: 'bar', height: 300 },
            xaxis: { categories: data.labels },
            yaxis: { title: { text: 'Number of Jobs' } },
            plotOptions: { 
                bar: { 
                    distributed: true, 
                    horizontal: true,
                    borderRadius: 4,
                } 
            },
            colors: ['#6c757d', '#17a2b8', '#007bff', '#28a745', '#ffc107', '#fd7e14', '#20c997', '#dc3545'],
            legend: { show: false },
            dataLabels: { enabled: true },
        };
        this.renderGraph(this.jobStatusChart.el, options);
    }

    renderPriorityChart() {
        const data = this.state.dashboardData.priority_chart;
        if (!data || !data.labels.length) return;
        
        const options = {
            series: data.values,
            labels: data.labels,
            chart: { type: 'pie', height: 280 },
            colors: ['#28a745', '#17a2b8', '#ffc107', '#dc3545'], // Low, Normal, High, Urgent
            legend: { position: 'bottom' },
            dataLabels: { enabled: true },
        };
        this.renderGraph(this.priorityChart.el, options);
    }

    renderMonthlyTrendChart() {
        const data = this.state.dashboardData.monthly_trend_chart;
        if (!data || !data.labels.length) return;
        
        const options = {
            series: [{ name: 'Requests', data: data.values }],
            chart: { 
                type: 'area', 
                height: 300, 
                zoom: { enabled: false },
                toolbar: { show: true }
            },
            stroke: { curve: 'smooth', width: 3 },
            fill: {
                type: 'gradient',
                gradient: {
                    shadeIntensity: 1,
                    opacityFrom: 0.7,
                    opacityTo: 0.2,
                }
            },
            xaxis: { type: 'category', categories: data.labels },
            yaxis: { title: { text: 'Number of Requests' } },
            dataLabels: { enabled: false },
            colors: ['#007bff'],
        };
        this.renderGraph(this.monthlyTrendChart.el, options);
    }

    renderJobTypeChart() {
        const data = this.state.dashboardData.job_type_chart;
        if (!data || !data.labels.length) return;
        
        const options = {
            series: data.values,
            labels: data.labels,
            chart: { type: 'donut', height: 280 },
            colors: ['#28a745', '#dc3545', '#17a2b8', '#6c757d'],
            legend: { position: 'bottom' },
            dataLabels: { enabled: true },
        };
        this.renderGraph(this.jobTypeChart.el, options);
    }

    // Generic function to render any chart
    renderGraph(el, options) {
        if (!el) return;
        const chart = new ApexCharts(el, options);
        chart.render();
    }
}

MaintenanceDashboard.template = "nthub_realestate.MaintenanceDashboardTemplate";
registry.category("actions").add("maintenance_dashboard_action", MaintenanceDashboard);
