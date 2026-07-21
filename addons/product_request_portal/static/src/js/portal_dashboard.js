odoo.define('product_request_portal.dashboard', function (require) {
'use strict';

const publicWidget = require('web.public.widget');
const core = require('web.core');

publicWidget.registry.ProductRequestPortalDashboard = publicWidget.Widget.extend({
    selector: '.o_portal_my_doc_table',
    
    start: function () {
        this._super.apply(this, arguments);
        this.initializeCharts();
    },
    
    initializeCharts: function () {
        // Wait for DOM to be ready
        setTimeout(() => {
            this.renderStatusChart();
            this.renderMonthlyChart();
        }, 500);
    },
    
    renderStatusChart: function () {
        const statusEl = document.querySelector('#statusChart');
        if (!statusEl) return;
        
        // Get chart data from the controller
        this._rpc({
            route: '/my/product_requests/dashboard_data',
            params: {}
        }).then((data) => {
            const statusOptions = {
                chart: {
                    type: 'donut',
                    height: 300
                },
                series: data.status_data.values,
                labels: data.status_data.labels,
                colors: ['#6c757d', '#ffc107', '#28a745', '#007bff'],
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    y: {
                        formatter: function(val) {
                            return val + " requests";
                        }
                    }
                },
                plotOptions: {
                    pie: {
                        donut: {
                            labels: {
                                show: true,
                                total: {
                                    show: true,
                                    label: 'Total',
                                    formatter: function (w) {
                                        return w.globals.seriesTotals.reduce((a, b) => a + b, 0);
                                    }
                                }
                            }
                        }
                    }
                }
            };
            
            const statusChart = new ApexCharts(statusEl, statusOptions);
            statusChart.render();
        });
    },
    
    renderMonthlyChart: function () {
        const monthlyEl = document.querySelector('#monthlyChart');
        if (!monthlyEl) return;
        
        this._rpc({
            route: '/my/product_requests/dashboard_data',
            params: {}
        }).then((data) => {
            const monthlyOptions = {
                chart: {
                    type: 'line',
                    height: 300
                },
                series: [{
                    name: 'Requests',
                    data: data.monthly_data.values
                }],
                xaxis: {
                    categories: data.monthly_data.labels
                },
                yaxis: {
                    title: {
                        text: 'Number of Requests'
                    }
                },
                stroke: {
                    curve: 'smooth',
                    width: 3
                },
                colors: ['#007bff'],
                markers: {
                    size: 6,
                    colors: ['#007bff'],
                    strokeColors: '#fff',
                    strokeWidth: 2,
                    hover: {
                        size: 8
                    }
                },
                grid: {
                    borderColor: '#e7e7e7',
                    row: {
                        colors: ['#f3f3f3', 'transparent'],
                        opacity: 0.5
                    }
                },
                tooltip: {
                    y: {
                        formatter: function(val) {
                            return val + " requests";
                        }
                    }
                }
            };
            
            const monthlyChart = new ApexCharts(monthlyEl, monthlyOptions);
            monthlyChart.render();
        });
    }
});

return publicWidget.registry.ProductRequestPortalDashboard;

});