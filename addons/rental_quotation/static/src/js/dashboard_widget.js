/** @odoo-module **/

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

/**
 * Rental Quotation Dashboard Widget
 */
export class RentalQuotationDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            dashboardData: {},
            loading: true,
            filters: {
                date_from: null,
                date_to: null,
                salesperson_ids: [],
                state_filter: 'all'
            }
        });
        
        onMounted(async () => {
            try {
                await loadJS("https://cdn.jsdelivr.net/npm/chart.js");
                await this.loadDashboardData();
                this.renderCharts();
            } catch (error) {
                console.error("Failed to initialize dashboard:", error);
                this.state.loading = false;
            }
        });
    }

    async loadDashboardData() {
        try {
            this.state.loading = true;
            const data = await this.orm.call("rental.quotation.dashboard", "get_dashboard_data", [], {
                context: this.state.filters
            });
            
            this.state.dashboardData = data;
            this.state.loading = false;
            
            // Update DOM elements
            this.updateKPIElements(data);
            
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            this.state.loading = false;
        }
    }

    updateKPIElements(data) {
        // Update KPI elements if they exist
        const totalQuotationsEl = document.getElementById("total_quotations");
        if (totalQuotationsEl) {
            totalQuotationsEl.innerHTML = `<span>${data.total_quotations || 0}</span>`;
        }

        const pendingApprovalsEl = document.getElementById("pending_approvals");
        if (pendingApprovalsEl) {
            pendingApprovalsEl.innerHTML = `<span>${data.pending_approvals || 0}</span>`;
        }

        const approvedQuotationsEl = document.getElementById("approved_quotations");
        if (approvedQuotationsEl) {
            approvedQuotationsEl.innerHTML = `<span>${data.approved_quotations || 0}</span>`;
        }

        const conversionRateEl = document.getElementById("conversion_rate");
        if (conversionRateEl) {
            conversionRateEl.innerHTML = `<span>${data.conversion_rate || 0}%</span>`;
        }
    }

    renderCharts() {
        if (!this.state.dashboardData || this.state.loading) return;
        
        // Render Monthly Trends Chart
        this.renderMonthlyChart();
        
        // Render Status Pie Chart
        this.renderStatusPieChart();
        
        // Render Top Performers Chart
        this.renderTopPerformersChart();
    }

    renderMonthlyChart() {
        const container = document.getElementById('monthly_chart_container');
        if (!container || !this.state.dashboardData.monthly_chart_data) return;

        // Create canvas if not exists
        let canvas = container.querySelector('canvas');
        if (!canvas) {
            canvas = document.createElement('canvas');
            container.appendChild(canvas);
        }

        new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: this.state.dashboardData.monthly_chart_data,
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Monthly Quotation Trends'
                    },
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Number of Quotations'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Month'
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
    }

    renderStatusPieChart() {
        const container = document.getElementById('status_pie_container');
        if (!container || !this.state.dashboardData.status_pie_data) return;

        let canvas = container.querySelector('canvas');
        if (!canvas) {
            canvas = document.createElement('canvas');
            container.appendChild(canvas);
        }

        new Chart(canvas.getContext('2d'), {
            type: 'doughnut',
            data: this.state.dashboardData.status_pie_data,
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Quotation Status Distribution'
                    },
                    legend: {
                        display: true,
                        position: 'bottom'
                    }
                }
            }
        });
    }

    renderTopPerformersChart() {
        const container = document.getElementById('top_performers_container');
        if (!container || !this.state.dashboardData.top_salesperson_data) return;

        const performers = this.state.dashboardData.top_salesperson_data.slice(0, 5);
        
        let canvas = container.querySelector('canvas');
        if (!canvas) {
            canvas = document.createElement('canvas');
            container.appendChild(canvas);
        }

        new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: performers.map(p => p.name),
                datasets: [{
                    label: 'Total Value',
                    data: performers.map(p => p.total_value),
                    backgroundColor: 'rgba(54, 162, 235, 0.8)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }, {
                    label: 'Conversion Rate %',
                    data: performers.map(p => p.conversion_rate),
                    backgroundColor: 'rgba(255, 99, 132, 0.8)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1,
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Top Performers'
                    },
                    legend: {
                        display: true
                    }
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Total Value'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Conversion Rate %'
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                }
            }
        });
    }

    async onFilterChange() {
        await this.loadDashboardData();
        this.renderCharts();
    }

    async refreshDashboard() {
        await this.loadDashboardData();
        this.renderCharts();
    }
}

RentalQuotationDashboard.template = "rental_quotation.Dashboard";

// Register the widget
registry.category("actions").add("rental_quotation_dashboard", RentalQuotationDashboard);