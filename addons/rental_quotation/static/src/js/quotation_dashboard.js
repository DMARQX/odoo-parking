/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, onMounted, useRef, useState } = owl;

class RentalQuotationDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            dashboardData: {},
        });

        // المراجع لحاويات الرسوم البيانية في template
        this.quotationStatusChart = useRef('quotationStatusChart');
        this.monthlyQuotationsChart = useRef('monthlyQuotationsChart');
        this.monthlyValueChart = useRef('monthlyValueChart');

        onWillStart(async () => {
            // استدعاء الطريقة في Python لجلب جميع بيانات dashboard
            const data = await this.orm.call(
                'rental.quotation.dashboard.data',
                'get_rental_quotation_dashboard_data',
                []
            );
            this.state.dashboardData = data;
        });

        onMounted(() => {
            // عندما يكون المكون في DOM، رسم الرسوم البيانية
            this.renderQuotationStatusChart();
            this.renderMonthlyQuotationsChart();
            this.renderMonthlyValueChart();
        });
    }

    // هذه الدالة تجعل KPI cards قابلة للنقر
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

    // فتح كوتيشن معين
    openQuotation(quotationId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'rental.quotation',
            res_id: quotationId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    // --- دوال رسم الرسوم البيانية ---

    renderQuotationStatusChart() {
        const { labels, values } = this.state.dashboardData.quotation_status_chart;
        const options = {
            series: values,
            labels: labels,
            chart: { 
                type: 'donut', 
                height: 350,
                fontFamily: 'Arial, sans-serif'
            },
            colors: ['#6c757d', '#ffc107', '#17a2b8', '#28a745', '#dc3545', '#6f42c1'], // مسودة، مُرسل، مراجعة، موافق، مرفوض، منتهي
            legend: { 
                position: 'bottom',
                fontSize: '14px'
            },
            dataLabels: { 
                enabled: true,
                style: {
                    fontSize: '12px'
                }
            },
            plotOptions: {
                pie: {
                    donut: {
                        labels: {
                            show: true,
                            total: {
                                show: true,
                                label: 'Total Quotations',
                                fontSize: '16px',
                                color: '#373d3f'
                            }
                        }
                    }
                }
            }
        };
        this.renderGraph(this.quotationStatusChart.el, options);
    }

    renderMonthlyQuotationsChart() {
        const { labels, values } = this.state.dashboardData.monthly_quotations_chart;
        const options = {
            series: [{ name: 'Quotations Count', data: values }],
            chart: { 
                type: 'bar', 
                height: 350,
                fontFamily: 'Arial, sans-serif'
            },
            xaxis: { 
                categories: labels,
                labels: {
                    style: {
                        fontSize: '12px'
                    }
                }
            },
            yaxis: { 
                title: { 
                    text: 'Number of Quotations',
                    style: {
                        fontSize: '14px'
                    }
                }
            },
            plotOptions: { 
                bar: { 
                    distributed: false, 
                    horizontal: false,
                    borderRadius: 4,
                    columnWidth: '60%'
                } 
            },
            colors: ['#007bff'],
            dataLabels: { enabled: true },
            grid: {
                show: true,
                borderColor: '#e0e6ed'
            }
        };
        this.renderGraph(this.monthlyQuotationsChart.el, options);
    }

    renderMonthlyValueChart() {
        const { labels, values } = this.state.dashboardData.monthly_value_chart;
        const options = {
            series: [{ name: 'Quotation Value', data: values }],
            chart: { 
                type: 'area', 
                height: 350, 
                zoom: { enabled: false },
                fontFamily: 'Arial, sans-serif'
            },
            stroke: { 
                curve: 'smooth',
                width: 3
            },
            xaxis: { 
                type: 'category', 
                categories: labels,
                labels: {
                    style: {
                        fontSize: '12px'
                    }
                }
            },
            yaxis: { 
                title: { 
                    text: 'Total Value',
                    style: {
                        fontSize: '14px'
                    }
                },
                labels: {
                    formatter: function(value) {
                        return new Intl.NumberFormat('en-SA', {
                            style: 'currency',
                            currency: 'SAR',
                            minimumFractionDigits: 0
                        }).format(value);
                    }
                }
            },
            dataLabels: { enabled: false },
            fill: {
                type: 'gradient',
                gradient: {
                    shade: 'light',
                    type: 'vertical',
                    shadeIntensity: 0.25,
                    gradientToColors: ['#28a745'],
                    opacityFrom: 0.8,
                    opacityTo: 0.3
                }
            },
            colors: ['#007bff'],
            grid: {
                show: true,
                borderColor: '#e0e6ed'
            }
        };
        this.renderGraph(this.monthlyValueChart.el, options);
    }

    // دالة عامة لرسم أي رسم بياني
    renderGraph(el, options) {
        if (!el) return;
        const chart = new ApexCharts(el, options);
        chart.render();
    }

    // تنسيق العملة للعرض
    formatCurrency(amount) {
        return new Intl.NumberFormat('en-SA', {
            style: 'currency',
            currency: 'SAR',
            minimumFractionDigits: 0
        }).format(amount);
    }

    // تنسيق الأرقام الكبيرة
    formatNumber(number) {
        return new Intl.NumberFormat('en-US').format(number);
    }
}

RentalQuotationDashboard.template = "rental_quotation.RentalQuotationDashboardTemplate";
registry.category("actions").add("rental_quotation_dashboard_action", RentalQuotationDashboard);