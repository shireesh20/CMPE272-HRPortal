document.addEventListener('DOMContentLoaded', () => {
    displayLoadingIndicator();
    fetch('/department_histogram')
        .then(response => response.json())
        .then(departmentData => {
            renderHistogramChart('departmentHistogramCanvas', departmentData);
        })
        .catch(error => console.error('Error retrieving department histogram data:', error));

    fetch('/salary_ranges_pie_chart')
        .then(response => response.json())
        .then(salaryData => {
            renderDistributionPieChart('salaryDistributionCanvas', salaryData);
        })
        .catch(error => console.error('Error retrieving salary distribution data:', error))
        .finally(() => removeLoadingIndicator());
});

function renderHistogramChart(chartId, chartData) {
    const chartContext = document.getElementById(chartId).getContext('2d');
    new Chart(chartContext, {
        type: 'bar',
        data: {
            labels: chartData.dept_names,
            datasets: [{
                label: 'Employee Count per Department',
                data: chartData.num_employees,
                backgroundColor: 'rgba(75, 192, 192, 0.5)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            }]
        },
        options: {
            maintainAspectRatio: false,
            scales: {
                yAxes: [{
                    ticks: {
                        beginAtZero: true
                    }
                }]
            }
        }
    });
}

function renderDistributionPieChart(chartId, chartData) {
    const chartContext = document.getElementById(chartId).getContext('2d');
    new Chart(chartContext, {
        type: 'pie',
        data: {
            labels: chartData.range_labels,
            datasets: [{
                data: chartData.range_values,
                backgroundColor: [
                    'rgba(153, 102, 255, 0.5)',
                    'rgba(255, 159, 64, 0.5)',
                    'rgba(255, 99, 132, 0.5)'
                ],
                borderColor: [
                    'rgba(153, 102, 255, 1)',
                    'rgba(255, 159, 64, 1)',
                    'rgba(255, 99, 132, 1)'
                ],
                borderWidth: 1
            }]
        }
    });
}


function showLoader() {
    document.getElementById('preloader').style.display = 'block';
}

function hideLoader() {
    document.getElementById('preloader').style.display = 'none';
}

document.querySelector('.top-nav #verificationNav').addEventListener('click', function (e) {
    e.preventDefault();
    openSidebar();
});

document.querySelector('.sidebar #closeSidebar').addEventListener('click', function () {
    closeSidebar();
});

document.querySelector('.overlay-dialog #closeDialogButton').addEventListener('click', function () {
    closeOverlayDialog();
});

document.querySelector('.overlay-dialog #confirmButton').addEventListener('click', function () {
    executeApproval();
});

document.querySelector('.overlay-dialog #rejectButton').addEventListener('click', function () {
    processRejection();
});

function openSidebar() {
    document.getElementById('sidebar').style.transform = 'translateX(0)';
    document.getElementById('backgroundCover').style.display = 'block';
}

function closeSidebar() {
    document.getElementById('sidebar').style.transform = 'translateX(100%)';
    document.getElementById('backgroundCover').style.display = 'none';
}

function openOverlayDialog() {
    document.getElementById('overlayDialog').style.display = 'block';
    document.getElementById('backgroundCover').style.display = 'block';
}

function closeOverlayDialog() {
    document.getElementById('overlayDialog').style.display = 'none';
    document.getElementById('backgroundCover').style.display = 'none';
}

function executeApproval() {
    // Processing the approval action

    // Retrieve data from the displayed modal
    const supervisorNumber = document.querySelector("#modalDetails p:nth-child(2)").textContent.split(": ")[1];
    const departmentNumber = document.querySelector("#modalDetails p:nth-child(3)").textContent.split(": ")[1];
    const givenName = document.querySelector("#modalDetails p:nth-child(4)").textContent.split(": ")[1];
    const familyName = document.querySelector("#modalDetails p:nth-child(5)").textContent.split(": ")[1];
    const jobTitle = document.querySelector("#modalDetails p:nth-child(6)").textContent.split(": ")[1];
    const payRate = document.getElementById("salary") ? document.getElementById("salary").value : '';
    const requestType = document.getElementById("approvalReqType").value;

    const employeeDetails = {
        supervisor_id: supervisorNumber,
        dept_id: departmentNumber,
        first_name: givenName,
        last_name: familyName,
        position: jobTitle,
        compensation: payRate,
        request_type: requestType
    };

    initiateLoading();
    fetch('/confirm_employee_approval', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(employeeDetails)
    })
    .then(response => response.json())
    .then(result => {
        if (result.message) {
            alert(result.message);
            dismissModal();
            refreshApprovalDashboard();
            fetch('/count_pending_approvals')
            .then(response => response.json())
            .then(result => {
                const approvalCount = result.count;
                if (approvalCount > 0) {
                    document.getElementById('pendingApprovalsCount').textContent = approvalCount;
                } else {
                    // Conceal notification badge if no pending approvals
                    document.getElementById('pendingApprovalsCount').style.display = 'none';
                }
            })
            .catch(error => console.error('Error encountered:', error));
            // Additional UI update logic here
        } else {
            alert('An error occurred: ' + result.error);
        }
    })
    .catch(error => console.error('Error encountered:', error))
    .finally(() => terminateLoading());
}



function processRejection() {
    // Logic for handling rejection

    // Extracting data from the displayed modal
    const mgrNumber = document.querySelector("#modalDetails p:nth-child(2)").textContent.split(": ")[1];
    const departmentNumber = document.querySelector("#modalDetails p:nth-child(3)").textContent.split(": ")[1];
    const givenName = document.querySelector("#modalDetails p:nth-child(4)").textContent.split(": ")[1];
    const surName = document.querySelector("#modalDetails p:nth-child(5)").textContent.split(": ")[1];
    const jobTitle = document.querySelector("#modalDetails p:nth-child(6)").textContent.split(": ")[1];
    const statusOfHire = 2;  // Represents a declined status

    const employeeData = {
        manager_id: mgrNumber,
        department_id: departmentNumber,
        first_name: givenName,
        last_name: surName,
        position_title: jobTitle,
        employment_status: statusOfHire
    };

    initiateLoadingIndicator();
    fetch('/update_employee_status', {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(employeeData)
    })
    .then(response => response.json())
    .then(result => {
        if (result.message) {
            alert(result.message);
            closeActiveModal();
            refreshApprovalSection(); // Optionally, reload the approval section
            fetch('/pending_approvals_count')
            .then(response => response.json())
            .then(result => {
                const approvalCount = result.count; 
                if (approvalCount > 0) {
                    document.getElementById('approvalCountDisplay').textContent = approvalCount;
                } else {
                    // Hide notification if count is zero
                    document.getElementById('approvalCountDisplay').style.display = 'none';
                }
            })
            .catch(error => console.error('Error occurred:', error));
        } else {
            alert('An error occurred: ' + result.error);
        }
    })
    .catch(error => console.error('Error occurred:', error))
    .finally(() => stopLoadingIndicator());
}


