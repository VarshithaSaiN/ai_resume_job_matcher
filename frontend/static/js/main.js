document.addEventListener('DOMContentLoaded', function() {

    // Initialize Bootstrap Tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Smooth scroll for anchor links
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Bootstrap Form Validation
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(function(form) {

        // On form submit, validate and then enable loading state on button if valid
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
                form.classList.add('was-validated');
                // Do not disable button or show loading if invalid
            } else {
                // Valid form: disable submit buttons and show loading
                const submitButtons = form.querySelectorAll('button[type="submit"]');
                submitButtons.forEach(function(btn) {
                    btn.disabled = true;
                    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Loading...`;
                });
            }
        });
    });

    // Match score color coding
    const matchScores = document.querySelectorAll('.match-score');
    matchScores.forEach(function(score) {
        const value = parseInt(score.textContent);
        if (value >= 80) {
            score.classList.add('high');
        } else if (value >= 60) {
            score.classList.add('medium');
        } else {
            score.classList.add('low');
        }
    });

    // Display Selected File Name for Resume Upload
    const resumeInput = document.getElementById('resume_file');
    if (resumeInput) {
        resumeInput.addEventListener('change', function() {
            const fileName = resumeInput.files.length ? resumeInput.files[0].name : "";
            const label = resumeInput.closest('.mb-3').querySelector('.form-label');
            if (fileName && label) {
                label.textContent = `Selected: ${fileName}`;
            }
        });
    }
});
// Enhanced delete confirmation with loading state
function confirmDelete(resumeId, fileName) {
    // Set the form action to the delete URL
    const form = document.getElementById('deleteForm');
    form.action = '/delete_resume/' + resumeId;
    
    // Set the filename in the modal
    document.getElementById('deleteFileName').textContent = fileName;
    
    // Show the modal
    const deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));
    deleteModal.show();
    
    // Add loading state to delete button
    form.addEventListener('submit', function() {
        const deleteBtn = form.querySelector('button[type="submit"]');
        deleteBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Deleting...';
        deleteBtn.disabled = true;
    });
}
document.querySelectorAll('.toggle-password').forEach(button => {
  button.addEventListener('click', () => {
    const targetId = button.getAttribute('data-target');
    const input = document.getElementById(targetId);
    if (input.type === 'password') {
      input.type = 'text';
      button.innerHTML = '<i class="fas fa-eye-slash"></i>';
    } else {
      input.type = 'password';
      button.innerHTML = '<i class="fas fa-eye"></i>';
    }
  });
});
