/**
 * Admin Common JavaScript Utilities
 * Shared functions and configurations for admin portal
 */

// Common DataTables configuration
const ADMIN_DATATABLES_CONFIG = {
    paging: true,
    searching: true,
    info: true,
    order: [],
    responsive: true,
    fixedHeader: false,
    scrollY: '400px',
    scrollCollapse: true,
    lengthMenu: [[25, 50, 100, 250, 500], [25, 50, 100, 250, 500]],
    pageLength: 25,
    language: { lengthMenu: 'Show _MENU_ entries per page' },
    serverSide: true,
    processing: true,
    // Add better error handling and request throttling
    ajax: {
        error: function(xhr, error, thrown) {
            if (xhr.status === 429) {
                // Rate limit exceeded - show user-friendly message
                showErrorMessage('Rate Limit Exceeded', 'Too many requests. Please wait a moment and try again.');
            } else {
                // Other errors
                showErrorMessage('Data Loading Error', 'Failed to load data. Please refresh the page and try again.');
            }
            console.error('DataTables AJAX error:', error, thrown);
        }
    },
    // Add request throttling
    deferRender: true,
    // Reduce search delay to prevent rapid requests
    searchDelay: 500
};

/**
 * Initialize a server-side DataTable with common configuration
 * @param {string} tableId - The table ID selector (e.g., '#users-table')
 * @param {string} ajaxUrl - The AJAX endpoint URL
 * @param {Array} columns - Array of column definitions
 * @param {Array} columnDefs - Optional column definitions for customization
 * @returns {DataTable} The initialized DataTable instance
 */
function initServerSideTable(tableId, ajaxUrl, columns, columnDefs = []) {
    const config = {
        ...ADMIN_DATATABLES_CONFIG,
        ajax: { url: ajaxUrl, type: 'GET' },
        columns: columns,
        columnDefs: columnDefs
    };
    
    return $(tableId).DataTable(config);
}

/**
 * Show a success message using SweetAlert2
 * @param {string} title - The title of the message
 * @param {string} text - The message text
 * @param {number} timer - Auto-close timer in milliseconds (default: 2000)
 */
function showSuccessMessage(title, text, timer = 2000) {
    Swal.fire({
        title: title,
        text: text,
        icon: 'success',
        timer: timer,
        showConfirmButton: false
    });
}

/**
 * Show an error message using SweetAlert2
 * @param {string} title - The title of the message
 * @param {string} text - The message text
 */
function showErrorMessage(title, text) {
    Swal.fire({
        title: title,
        text: text,
        icon: 'error',
        confirmButtonText: 'OK'
    });
}

/**
 * Show a confirmation dialog using SweetAlert2
 * @param {string} title - The title of the dialog
 * @param {string} text - The confirmation text
 * @param {Function} onConfirm - Callback function to execute on confirmation
 * @param {string} confirmButtonText - Text for confirm button (default: 'Yes, delete it!')
 */
function showConfirmDialog(title, text, onConfirm, confirmButtonText = 'Yes, delete it!') {
    Swal.fire({
        title: title,
        text: text,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: confirmButtonText,
        cancelButtonText: 'Cancel'
    }).then((result) => {
        if (result.isConfirmed) {
            onConfirm();
        }
    });
}

/**
 * Handle AJAX form submission with common error handling
 * @param {string} url - The endpoint URL
 * @param {string} method - HTTP method (POST, PUT, DELETE)
 * @param {Object} data - Data to send
 * @param {Function} onSuccess - Success callback
 * @param {Function} onError - Optional error callback
 */
function submitAjaxForm(url, method, data, onSuccess, onError = null) {
    const ajaxConfig = {
        url: url,
        method: method,
        success: onSuccess,
        error: function(xhr) {
            const errorMsg = xhr.responseJSON?.error || 
                           xhr.responseJSON?.message || 
                           'An unknown error occurred';
            
            if (onError) {
                onError(errorMsg, xhr);
            } else {
                showErrorMessage('Error', errorMsg);
            }
        }
    };
    
    // Add content type and data for POST/PUT requests
    if (method === 'POST' || method === 'PUT') {
        ajaxConfig.contentType = 'application/json';
        ajaxConfig.data = JSON.stringify(data);
    }
    
    $.ajax(ajaxConfig);
}

/**
 * Handle delete action with confirmation
 * @param {number} id - The ID of the item to delete
 * @param {string} itemName - Name of the item for confirmation message
 * @param {string} deleteUrl - The delete endpoint URL
 * @param {string} tableId - The DataTable ID to reload after deletion
 * @param {string} itemType - Type of item (user, retailer, event, etc.)
 */
function handleDelete(id, itemName, deleteUrl, tableId, itemType = 'item') {
    const confirmText = `You are about to delete "${itemName}". This action cannot be undone!`;
    
    showConfirmDialog(
        'Are you sure?',
        confirmText,
        function() {
            submitAjaxForm(
                deleteUrl,
                'DELETE',
                null,
                function(resp) {
                    $(tableId).DataTable().ajax.reload();
                    showSuccessMessage('Deleted!', `${itemType} has been deleted successfully.`);
                }
            );
        }
    );
}

/**
 * Populate form fields from data object
 * @param {string} formSelector - jQuery selector for the form
 * @param {Object} data - Data object with field values
 */
function populateForm(formSelector, data) {
    const form = $(formSelector);
    
    Object.keys(data).forEach(key => {
        const field = form.find(`[name="${key}"]`);
        if (field.length > 0) {
            const value = data[key];
            
            if (field.is('select[multiple]')) {
                // Handle multi-select fields
                field.val(Array.isArray(value) ? value : [value]);
            } else if (field.is('select')) {
                // Handle single select fields
                field.val(value);
            } else if (field.is('input[type="checkbox"]')) {
                // Handle checkboxes
                field.prop('checked', Boolean(value));
            } else {
                // Handle regular input fields
                field.val(value || '');
            }
        }
    });
}

/**
 * Serialize form data to object, with special handling for different field types
 * @param {string} formSelector - jQuery selector for the form
 * @param {Array} nullableFields - Fields that should be null if empty
 * @returns {Object} Serialized form data
 */
function serializeFormData(formSelector, nullableFields = []) {
    const form = $(formSelector);
    const data = {};
    
    form.find('input, select, textarea').each(function() {
        const field = $(this);
        const name = field.attr('name');
        
        if (!name) return;
        
        let value = field.val();
        
        if (field.is('select[multiple]')) {
            // Handle multi-select
            data[name] = value || [];
        } else if (field.is('input[type="checkbox"]')) {
            // Handle checkboxes
            data[name] = field.is(':checked');
        } else if (value === '' && nullableFields.includes(name)) {
            // Handle nullable fields
            data[name] = null;
        } else {
            // Handle regular fields
            data[name] = value;
        }
    });
    
    return data;
}

/**
 * Initialize Bootstrap tooltips
 */
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Format date for display in forms (YYYY-MM-DD format)
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted date string
 */
function formatDateForInput(dateString) {
    if (!dateString) return '';
    try {
        return new Date(dateString).toISOString().split('T')[0];
    } catch (e) {
        return '';
    }
}

/**
 * Format datetime for display
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted datetime string
 */
function formatDateTime(dateString) {
    if (!dateString) return 'Never';
    try {
        return new Date(dateString).toLocaleString();
    } catch (e) {
        return 'Invalid Date';
    }
}

// Initialize common functionality when document is ready
$(document).ready(function() {
    // Initialize tooltips
    initTooltips();
    
    // Add common event handlers
    $(document).on('show.bs.modal', '.modal', function() {
        // Ensure tooltips work in modals
        initTooltips();
    });
    
    // Mark as loaded for debugging
    window.adminCommonLoaded = true;
    console.log('✅ admin-common.js loaded and initialized');
}); 