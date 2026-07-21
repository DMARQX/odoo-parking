/**
 * Owner Portal Dashboard - ApexCharts Integration
 * Professional charts for real estate analytics
 */

odoo.define('nthub_realestate.owner_dashboard_charts', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    publicWidget.registry.OwnerDashboardCharts = publicWidget.Widget.extend({
        selector: '.owner-dashboard-wrapper',
        events: {
            'click .sidebar-toggle': '_onToggleSidebar',
            'click .mobile-menu-toggle': '_onToggleMobileSidebar',
            'click .sidebar-overlay': '_onCloseMobileSidebar',
            'click .btn-chart-action': '_onChartActionClick',
        },

        start: function () {
            this._super.apply(this, arguments);
            this._initCharts();
            this._initAnimations();
        },

        _initCharts: function () {
            var self = this;
            
            // Wait for ApexCharts to be available
            this._waitForApexCharts().then(function() {
                self._renderRevenueChart();
                self._renderUnitsChart();
                self._renderOccupancyChart();
                self._renderCollectionChart();
            });
        },

        _waitForApexCharts: function() {
            return new Promise(function(resolve) {
                if (typeof ApexCharts !== 'undefined') {
                    resolve();
                } else {
                    var checkInterval = setInterval(function() {
                        if (typeof ApexCharts !== 'undefined') {
                            clearInterval(checkInterval);
                            resolve();
                        }
                    }, 100);
                    // Timeout after 5 seconds
                    setTimeout(function() {
                        clearInterval(checkInterval);
                        resolve();
                    }, 5000);
                }
            });
        },

        _renderRevenueChart: function () {
            var chartEl = this.$('#revenue-chart')[0];
            if (!chartEl) return;

            // Get data from data attributes
            var chartData = $(chartEl).data('chart-data') || {};
            var months = chartData.months || ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
            var revenue = chartData.revenue || [0, 0, 0, 0, 0, 0];
            var collected = chartData.collected || [0, 0, 0, 0, 0, 0];

            var options = {
                series: [{
                    name: 'Revenue',
                    data: revenue
                }, {
                    name: 'Collected',
                    data: collected
                }],
                chart: {
                    type: 'area',
                    height: 320,
                    toolbar: { show: false },
                    fontFamily: 'inherit',
                    animations: {
                        enabled: true,
                        easing: 'easeinout',
                        speed: 800
                    }
                },
                colors: ['#5C6BC0', '#66BB6A'],
                fill: {
                    type: 'gradient',
                    gradient: {
                        shadeIntensity: 1,
                        opacityFrom: 0.4,
                        opacityTo: 0.1,
                        stops: [0, 90, 100]
                    }
                },
                stroke: {
                    curve: 'smooth',
                    width: 3
                },
                dataLabels: { enabled: false },
                xaxis: {
                    categories: months,
                    axisBorder: { show: false },
                    axisTicks: { show: false },
                    labels: {
                        style: {
                            colors: '#78909C',
                            fontSize: '12px'
                        }
                    }
                },
                yaxis: {
                    labels: {
                        style: {
                            colors: '#78909C',
                            fontSize: '12px'
                        },
                        formatter: function(val) {
                            return val.toLocaleString();
                        }
                    }
                },
                grid: {
                    borderColor: '#E0E0E0',
                    strokeDashArray: 4
                },
                legend: {
                    position: 'top',
                    horizontalAlign: 'right',
                    fontSize: '13px',
                    markers: { radius: 4 }
                },
                tooltip: {
                    y: {
                        formatter: function(val) {
                            return val.toLocaleString() + ' SAR';
                        }
                    }
                }
            };

            var chart = new ApexCharts(chartEl, options);
            chart.render();
        },

        _renderUnitsChart: function () {
            var chartEl = this.$('#units-chart')[0];
            if (!chartEl) return;

            var chartData = $(chartEl).data('chart-data') || {};
            var available = chartData.available || 0;
            var rented = chartData.rented || 0;
            var sold = chartData.sold || 0;

            var options = {
                series: [available, rented, sold],
                labels: ['Available', 'Rented', 'Sold'],
                chart: {
                    type: 'donut',
                    height: 280,
                    animations: {
                        enabled: true,
                        easing: 'easeinout',
                        speed: 800
                    }
                },
                colors: ['#66BB6A', '#FFA726', '#42A5F5'],
                plotOptions: {
                    pie: {
                        donut: {
                            size: '70%',
                            labels: {
                                show: true,
                                name: {
                                    show: true,
                                    fontSize: '14px',
                                    fontWeight: 600,
                                    color: '#37474F'
                                },
                                value: {
                                    show: true,
                                    fontSize: '24px',
                                    fontWeight: 700,
                                    color: '#37474F'
                                },
                                total: {
                                    show: true,
                                    label: 'Total Units',
                                    fontSize: '14px',
                                    fontWeight: 500,
                                    color: '#78909C'
                                }
                            }
                        }
                    }
                },
                legend: {
                    position: 'bottom',
                    fontSize: '13px',
                    markers: { radius: 4 }
                },
                dataLabels: { enabled: false },
                stroke: { show: false }
            };

            var chart = new ApexCharts(chartEl, options);
            chart.render();
        },

        _renderOccupancyChart: function () {
            var chartEl = this.$('#occupancy-chart')[0];
            if (!chartEl) return;

            var chartData = $(chartEl).data('chart-data') || {};
            var occupancyRate = chartData.rate || 0;

            var options = {
                series: [occupancyRate],
                chart: {
                    type: 'radialBar',
                    height: 280,
                    animations: {
                        enabled: true,
                        easing: 'easeinout',
                        speed: 800
                    }
                },
                colors: ['#5C6BC0'],
                plotOptions: {
                    radialBar: {
                        hollow: {
                            size: '70%'
                        },
                        track: {
                            background: '#E8EAF6',
                            strokeWidth: '100%'
                        },
                        dataLabels: {
                            show: true,
                            name: {
                                show: true,
                                fontSize: '14px',
                                fontWeight: 500,
                                color: '#78909C',
                                offsetY: 20
                            },
                            value: {
                                show: true,
                                fontSize: '32px',
                                fontWeight: 700,
                                color: '#37474F',
                                offsetY: -15,
                                formatter: function(val) {
                                    return val + '%';
                                }
                            }
                        }
                    }
                },
                labels: ['Occupancy Rate'],
                stroke: { lineCap: 'round' }
            };

            var chart = new ApexCharts(chartEl, options);
            chart.render();
        },

        _renderCollectionChart: function () {
            var chartEl = this.$('#collection-chart')[0];
            if (!chartEl) return;

            var chartData = $(chartEl).data('chart-data') || {};
            var projects = chartData.projects || [];
            var collected = chartData.collected || [];
            var receivables = chartData.receivables || [];

            var options = {
                series: [{
                    name: 'Collected',
                    data: collected
                }, {
                    name: 'Receivables',
                    data: receivables
                }],
                chart: {
                    type: 'bar',
                    height: 320,
                    stacked: true,
                    toolbar: { show: false },
                    animations: {
                        enabled: true,
                        easing: 'easeinout',
                        speed: 800
                    }
                },
                colors: ['#66BB6A', '#EF5350'],
                plotOptions: {
                    bar: {
                        horizontal: false,
                        borderRadius: 6,
                        columnWidth: '50%'
                    }
                },
                dataLabels: { enabled: false },
                xaxis: {
                    categories: projects,
                    axisBorder: { show: false },
                    axisTicks: { show: false },
                    labels: {
                        style: {
                            colors: '#78909C',
                            fontSize: '12px'
                        },
                        rotate: -45,
                        rotateAlways: projects.length > 4
                    }
                },
                yaxis: {
                    labels: {
                        style: {
                            colors: '#78909C',
                            fontSize: '12px'
                        },
                        formatter: function(val) {
                            return val.toLocaleString();
                        }
                    }
                },
                grid: {
                    borderColor: '#E0E0E0',
                    strokeDashArray: 4
                },
                legend: {
                    position: 'top',
                    horizontalAlign: 'right',
                    fontSize: '13px',
                    markers: { radius: 4 }
                },
                tooltip: {
                    y: {
                        formatter: function(val) {
                            return val.toLocaleString() + ' SAR';
                        }
                    }
                }
            };

            var chart = new ApexCharts(chartEl, options);
            chart.render();
        },

        _initAnimations: function () {
            // Add animation class to stat cards
            this.$('.stat-card').each(function(index) {
                var $card = $(this);
                setTimeout(function() {
                    $card.addClass('animate-fade-in');
                }, index * 50);
            });
        },

        _onToggleSidebar: function (ev) {
            ev.preventDefault();
            this.$('.owner-sidebar').toggleClass('collapsed');
            
            // Save state in localStorage
            var isCollapsed = this.$('.owner-sidebar').hasClass('collapsed');
            localStorage.setItem('owner_sidebar_collapsed', isCollapsed);
        },

        _onToggleMobileSidebar: function (ev) {
            ev.preventDefault();
            this.$('.owner-sidebar').addClass('mobile-open');
            this.$('.sidebar-overlay').addClass('active');
        },

        _onCloseMobileSidebar: function (ev) {
            ev.preventDefault();
            this.$('.owner-sidebar').removeClass('mobile-open');
            this.$('.sidebar-overlay').removeClass('active');
        },

        _onChartActionClick: function (ev) {
            var $btn = $(ev.currentTarget);
            var $container = $btn.closest('.chart-card-header');
            
            $container.find('.btn-chart-action').removeClass('active');
            $btn.addClass('active');
            
            // Trigger chart update based on action
            var action = $btn.data('action');
            var chartId = $btn.closest('.chart-card').find('[id$="-chart"]').attr('id');
            
            // You can add custom logic here to update charts based on the action
            this.trigger_up('chart_action', {
                action: action,
                chartId: chartId
            });
        }
    });

    return publicWidget.registry.OwnerDashboardCharts;
});
