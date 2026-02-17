// subject_detail.js - Edit/Delete functionality for materials and assignments
// Full path: static/js/courses/subject_detail.js

document.addEventListener('DOMContentLoaded', function() {
    console.log('Subject detail JS loaded');

    // Material Edit Buttons - Updated selector to match template  
    document.querySelectorAll('.btn-warning-clean[title="Edit"][data-material-id]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const materialId = this.getAttribute('data-material-id');
            const materialTitle = this.getAttribute('data-material-title');
            console.log('Edit material clicked:', materialId, materialTitle);
            editMaterial(materialId);
        });
    });

    // Material Delete Buttons - Updated selector to match template
    document.querySelectorAll('.btn-danger-clean[title="Delete"][data-material-id]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const materialId = this.getAttribute('data-material-id');
            const materialTitle = this.getAttribute('data-material-title');
            console.log('Delete material clicked:', materialId, materialTitle);
            deleteMaterial(materialId, materialTitle);
        });
    });

    // Assignment Edit Buttons - Updated selector to match template
    document.querySelectorAll('.btn-warning-clean[title="Edit"][data-assignment-id]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const assignmentId = this.getAttribute('data-assignment-id');
            const assignmentTitle = this.getAttribute('data-assignment-title');
            console.log('Edit assignment clicked:', assignmentId, assignmentTitle);
            editAssignment(assignmentId);
        });
    });

    // Assignment Delete Buttons - Updated selector to match template
    document.querySelectorAll('.btn-danger-clean[title="Delete"][data-assignment-id]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const assignmentId = this.getAttribute('data-assignment-id');
            const assignmentTitle = this.getAttribute('data-assignment-title');
            console.log('Delete assignment clicked:', assignmentId, assignmentTitle);
            deleteAssignment(assignmentId, assignmentTitle);
        });
    });
});

// Material Functions
function editMaterial(materialId) {
    console.log('editMaterial called with ID:', materialId);
    
    // Get current material data from the table row
    const button = document.querySelector(`[data-material-id="${materialId}"][title="Edit"]`);
    const row = button.closest('tr');
    const currentTitle = row.cells[0].textContent.trim();
    const currentDescription = row.cells[1].textContent.trim();
    
    console.log('Current material data:', { currentTitle, currentDescription });
    
    // Create modal HTML
    const modalHtml = `
        <div id="editMaterialModal" class="modal fade" tabindex="-1" role="dialog">
            <div class="modal-dialog" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Edit Material</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="editMaterialForm">
                            <div class="mb-3">
                                <label for="materialTitle" class="form-label">Title *</label>
                                <input type="text" class="form-control" id="materialTitle" value="${escapeHtml(currentTitle)}" required>
                            </div>
                            <div class="mb-3">
                                <label for="materialDescription" class="form-label">Description</label>
                                <textarea class="form-control" id="materialDescription" rows="3">${escapeHtml(currentDescription === 'No description' ? '' : currentDescription)}</textarea>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" onclick="saveMaterialChanges('${materialId}')">Save Changes</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('editMaterialModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show modal - Try Bootstrap 5 first, fallback to Bootstrap 4
    try {
        const modal = new bootstrap.Modal(document.getElementById('editMaterialModal'));
        modal.show();
    } catch (e) {
        // Fallback for Bootstrap 4 or jQuery
        $('#editMaterialModal').modal('show');
    }
}

function saveMaterialChanges(materialId) {
    console.log('saveMaterialChanges called with ID:', materialId);
    
    const title = document.getElementById('materialTitle').value.trim();
    const description = document.getElementById('materialDescription').value.trim();
    
    if (!title) {
        alert('Please enter a title for the material.');
        return;
    }
    
    // Show loading
    const saveButton = document.querySelector('#editMaterialModal .btn-primary');
    const originalText = saveButton.textContent;
    saveButton.textContent = 'Saving...';
    saveButton.disabled = true;
    
    console.log('Sending data:', { title, description });
    
    // Send AJAX request
    fetch(`/courses/material/${materialId}/edit/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            title: title,
            description: description
        })
    })
    .then(response => {
        console.log('Response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Response data:', data);
        if (data.success) {
            // Update the table row
            const button = document.querySelector(`[data-material-id="${materialId}"][title="Edit"]`);
            const row = button.closest('tr');
            row.cells[0].textContent = title;
            row.cells[1].textContent = description || 'No description';
            
            // Close modal
            try {
                const modal = bootstrap.Modal.getInstance(document.getElementById('editMaterialModal'));
                modal.hide();
            } catch (e) {
                $('#editMaterialModal').modal('hide');
            }
            
            // Show success message
            showAlert('success', 'Material updated successfully!');
        } else {
            showAlert('error', data.error || 'Failed to update material');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('error', 'An error occurred while updating the material');
    })
    .finally(() => {
        saveButton.textContent = originalText;
        saveButton.disabled = false;
    });
}

function deleteMaterial(materialId, materialTitle) {
    console.log('deleteMaterial called:', materialId, materialTitle);
    
    if (!confirm(`Are you sure you want to delete "${materialTitle}"?\n\nThis action cannot be undone and will permanently remove the material file.`)) {
        return;
    }
    
    // Send AJAX request
    fetch(`/courses/material/${materialId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(response => {
        console.log('Delete response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Delete response data:', data);
        if (data.success) {
            // Remove the table row
            const button = document.querySelector(`[data-material-id="${materialId}"][title="Delete"]`);
            const row = button.closest('tr');
            row.remove();
            
            // Update material count in header
            updateMaterialCount(-1);
            
            // Show success message
            showAlert('success', data.message || 'Material deleted successfully!');
            
            // Check if no materials left, show empty state
            checkAndShowEmptyState('materials');
        } else {
            showAlert('error', data.error || 'Failed to delete material');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('error', 'An error occurred while deleting the material');
    });
}

// Assignment Functions
function editAssignment(assignmentId) {
    console.log('editAssignment called with ID:', assignmentId);
    
    // Get current assignment data from the table row
    const button = document.querySelector(`[data-assignment-id="${assignmentId}"][title="Edit"]`);
    const row = button.closest('tr');
    const currentTitle = row.cells[0].textContent.trim();
    const currentDescription = row.cells[1].textContent.trim();
    const currentDueDateText = row.cells[2].textContent.trim(); // Get due date text
    const currentMarks = row.cells[4].textContent.trim();
    
    console.log('Current assignment data:', { currentTitle, currentDescription, currentDueDateText, currentMarks });
    
    // Parse the due date from the table (format: "Jul 15, 2025 11:59 PM")
    let formattedDueDate = '';
    try {
        // Convert the display date to a proper datetime-local format
        const dateObj = new Date(currentDueDateText);
        if (!isNaN(dateObj.getTime())) {
            // Format for datetime-local input (YYYY-MM-DDTHH:MM)
            const year = dateObj.getFullYear();
            const month = String(dateObj.getMonth() + 1).padStart(2, '0');
            const day = String(dateObj.getDate()).padStart(2, '0');
            const hours = String(dateObj.getHours()).padStart(2, '0');
            const minutes = String(dateObj.getMinutes()).padStart(2, '0');
            formattedDueDate = `${year}-${month}-${day}T${hours}:${minutes}`;
        }
    } catch (e) {
        console.log('Could not parse due date:', e);
        // Set to tomorrow as default if parsing fails
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        const year = tomorrow.getFullYear();
        const month = String(tomorrow.getMonth() + 1).padStart(2, '0');
        const day = String(tomorrow.getDate()).padStart(2, '0');
        formattedDueDate = `${year}-${month}-${day}T23:59`;
    }
    
    console.log('Formatted due date:', formattedDueDate);
    
    // Create modal HTML
    const modalHtml = `
        <div id="editAssignmentModal" class="modal fade" tabindex="-1" role="dialog">
            <div class="modal-dialog modal-lg" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Edit Assignment</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="editAssignmentForm">
                            <div class="mb-3">
                                <label for="assignmentTitle" class="form-label">Title *</label>
                                <input type="text" class="form-control" id="assignmentTitle" value="${escapeHtml(currentTitle)}" required>
                            </div>
                            <div class="mb-3">
                                <label for="assignmentDescription" class="form-label">Description *</label>
                                <textarea class="form-control" id="assignmentDescription" rows="4" required>${escapeHtml(currentDescription === 'No description' ? '' : currentDescription)}</textarea>
                            </div>
                            <div class="row">
                                <div class="col-md-6">
                                    <label for="assignmentDueDate" class="form-label">Due Date *</label>
                                    <input type="datetime-local" class="form-control" id="assignmentDueDate" value="${formattedDueDate}" required>
                                </div>
                                <div class="col-md-6">
                                    <label for="assignmentMarks" class="form-label">Maximum Marks *</label>
                                    <input type="number" class="form-control" id="assignmentMarks" value="${currentMarks}" min="1" required>
                                </div>
                            </div>
                            <div class="mt-3">
                                <small class="text-muted">
                                    <i class="fas fa-info-circle me-1"></i>
                                    Note: Only basic assignment details can be edited. To change the assignment file, you'll need to create a new assignment.
                                </small>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" onclick="saveAssignmentChanges('${assignmentId}')">Save Changes</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('editAssignmentModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show modal
    try {
        const modal = new bootstrap.Modal(document.getElementById('editAssignmentModal'));
        modal.show();
    } catch (e) {
        $('#editAssignmentModal').modal('show');
    }
}

function saveAssignmentChanges(assignmentId) {
    console.log('saveAssignmentChanges called with ID:', assignmentId);
    
    const title = document.getElementById('assignmentTitle').value.trim();
    const description = document.getElementById('assignmentDescription').value.trim();
    const dueDate = document.getElementById('assignmentDueDate').value;
    const maxMarks = document.getElementById('assignmentMarks').value;
    
    if (!title || !description || !dueDate || !maxMarks) {
        alert('Please fill in all required fields.');
        return;
    }
    
    // Show loading
    const saveButton = document.querySelector('#editAssignmentModal .btn-primary');
    const originalText = saveButton.textContent;
    saveButton.textContent = 'Saving...';
    saveButton.disabled = true;
    
    console.log('Sending assignment data:', { title, description, dueDate, maxMarks });
    
    // Send AJAX request
    fetch(`/courses/assignment/${assignmentId}/edit/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            title: title,
            description: description,
            due_date: dueDate,
        })
    })
    .then(response => {
        console.log('Assignment edit response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Assignment edit response data:', data);
        if (data.success) {
            // Update the table row
            const button = document.querySelector(`[data-assignment-id="${assignmentId}"][title="Edit"]`);
            const row = button.closest('tr');
            row.cells[0].textContent = title;
            row.cells[1].textContent = description;
            row.cells[4].textContent = maxMarks;
            
            // Update due date (format it properly)
            const dueDateObj = new Date(dueDate);
            const formattedDate = dueDateObj.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            });
            row.cells[2].textContent = formattedDate;
            
            // Close modal
            try {
                const modal = bootstrap.Modal.getInstance(document.getElementById('editAssignmentModal'));
                modal.hide();
            } catch (e) {
                $('#editAssignmentModal').modal('hide');
            }
            
            // Show success message
            showAlert('success', 'Assignment updated successfully!');
        } else {
            showAlert('error', data.error || 'Failed to update assignment');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('error', 'An error occurred while updating the assignment');
    })
    .finally(() => {
        saveButton.textContent = originalText;
        saveButton.disabled = false;
    });
}

function deleteAssignment(assignmentId, assignmentTitle) {
    console.log('deleteAssignment called:', assignmentId, assignmentTitle);
    
    if (!confirm(`Are you sure you want to delete "${assignmentTitle}"?\n\nThis will also delete all student submissions for this assignment.\nThis action cannot be undone.`)) {
        return;
    }
    
    // Send AJAX request
    fetch(`/courses/assignment/${assignmentId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(response => {
        console.log('Assignment delete response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Assignment delete response data:', data);
        if (data.success) {
            // Remove the table row
            const button = document.querySelector(`[data-assignment-id="${assignmentId}"][title="Delete"]`);
            const row = button.closest('tr');
            row.remove();
            
            // Update assignment count in header
            updateAssignmentCount(-1);
            
            // Show success message
            showAlert('success', data.message || 'Assignment deleted successfully!');
            
            // Check if no assignments left, show empty state
            checkAndShowEmptyState('assignments');
        } else {
            showAlert('error', data.error || 'Failed to delete assignment');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('error', 'An error occurred while deleting the assignment');
    });
}

// Utility Functions
function getCsrfToken() {
    // Try multiple ways to get CSRF token
    let token = '';
    
    // Method 1: From input field
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfInput) {
        token = csrfInput.value;
    }
    
    // Method 2: From meta tag
    if (!token) {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (csrfMeta) {
            token = csrfMeta.getAttribute('content');
        }
    }
    
    // Method 3: From cookie (if available)
    if (!token) {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                token = value;
                break;
            }
        }
    }
    
    console.log('CSRF Token:', token ? 'Found' : 'Not found');
    return token;
}

function showAlert(type, message) {
    console.log('showAlert:', type, message);
    
    // Create alert HTML
    const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
    const iconClass = type === 'success' ? 'fa-check-circle' : 'fa-exclamation-triangle';
    
    const alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show" style="position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 350px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <i class="fas ${iconClass} me-2"></i>
            <strong>${type === 'success' ? 'Success!' : 'Error!'}</strong> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    
    // Remove any existing alerts
    const existingAlerts = document.querySelectorAll('.alert[style*="position: fixed"]');
    existingAlerts.forEach(alert => alert.remove());
    
    // Add alert to body
    document.body.insertAdjacentHTML('afterbegin', alertHtml);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        const alert = document.querySelector('.alert[style*="position: fixed"]');
        if (alert) {
            alert.remove();
        }
    }, 5000);
}

function updateMaterialCount(change) {
    const sectionTitles = document.querySelectorAll('.section-title');
    for (let title of sectionTitles) {
        if (title.textContent.includes('Course Materials')) {
            const badge = title.querySelector('.badge');
            if (badge) {
                const currentCount = parseInt(badge.textContent) || 0;
                const newCount = Math.max(0, currentCount + change);
                badge.textContent = newCount;
                console.log('Updated material count to:', newCount);
                break;
            }
        }
    }
}

function updateAssignmentCount(change) {
    const sectionTitles = document.querySelectorAll('.section-title');
    for (let title of sectionTitles) {
        if (title.textContent.includes('Assignments')) {
            const badge = title.querySelector('.badge');
            if (badge) {
                const currentCount = parseInt(badge.textContent) || 0;
                const newCount = Math.max(0, currentCount + change);
                badge.textContent = newCount;
                console.log('Updated assignment count to:', newCount);
                break;
            }
        }
    }
}

function checkAndShowEmptyState(type) {
    const tableClass = type === 'materials' ? 'materials-table' : 'assignments-table';
    const table = document.querySelector(`.${tableClass} tbody`);
    
    if (table && table.children.length === 0) {
        console.log(`No ${type} left, showing empty state`);
        
        // Hide table and show empty state
        const tableContainer = table.closest('.table-responsive');
        if (tableContainer) {
            tableContainer.style.display = 'none';
        }
        
        // Show empty state
        const cardBody = table.closest('.card-body');
        if (cardBody) {
            const icon = type === 'materials' ? 'book-open' : 'tasks';
            const title = type === 'materials' ? 'Materials' : 'Assignments';
            const description = type === 'materials' ? 'Course materials' : 'Assignment submissions';
            const action = type === 'materials' ? 'uploaded' : 'created';
            
            const emptyStateHtml = `
                <div class="empty-state">
                    <i class="fas fa-${icon}"></i>
                    <h5>No ${title} Available</h5>
                    <p>${description} will appear here when ${action} by the teacher.</p>
                </div>
            `;
            cardBody.innerHTML = emptyStateHtml;
        }
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}