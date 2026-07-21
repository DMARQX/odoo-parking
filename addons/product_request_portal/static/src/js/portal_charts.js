// Product Request Portal Dashboard with ApexCharts
document.addEventListener('DOMContentLoaded', function() {
    if (typeof ApexCharts === 'undefined') {
        console.log('ApexCharts library not loaded');
        return;
    }

    // Load dashboard data
    fetch('/my/product_requests/dashboard_data', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call", 
            params: {},
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.result) {
            renderCharts(data.result);
        }
    })
    .catch(error => console.error('Error:', error));

    function renderCharts(data) {
        // Status Chart
        if (document.querySelector('#statusChart') && data.status_data) {
            var statusOptions = {
                series: data.status_data.map(item => item.value),
                chart: {
                    type: 'donut',
                    height: 250
                },
                labels: data.status_data.map(item => item.name),
                colors: ['#fd7e14', '#28a745', '#007bff', '#6c757d', '#dc3545'],
                legend: {
                    position: 'bottom'
                }
            };
            var statusChart = new ApexCharts(document.querySelector("#statusChart"), statusOptions);
            statusChart.render();
        }

        // Monthly Chart
        if (document.querySelector('#monthlyChart') && data.monthly_data) {
            var monthlyOptions = {
                series: [{
                    name: 'Requests',
                    data: data.monthly_data.map(item => item.count)
                }],
                chart: {
                    type: 'line',
                    height: 250
                },
                xaxis: {
                    categories: data.monthly_data.map(item => item.month)
                },
                stroke: {
                    curve: 'smooth'
                },
                colors: ['#007bff']
            };
            var monthlyChart = new ApexCharts(document.querySelector("#monthlyChart"), monthlyOptions);
            monthlyChart.render();
        }
    }
});