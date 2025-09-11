/**
 * Password Strength Meter
 * Provides real-time password strength assessment and visual feedback
 */

class PasswordStrengthMeter {
    constructor(passwordInput, options = {}) {
        this.passwordInput = passwordInput;
        this.options = {
            showRequirements: true,
            showStrengthBar: true,
            showStrengthText: true,
            minLength: 8,
            requireUppercase: true,
            requireLowercase: true,
            requireNumbers: true,
            requireSpecialChars: false,
            ...options
        };
        
        this.strengthLevels = {
            veryWeak: { score: 0, text: 'Very Weak', class: 'very-weak', width: '25%' },
            weak: { score: 1, text: 'Weak', class: 'weak', width: '50%' },
            fair: { score: 2, text: 'Fair', class: 'fair', width: '75%' },
            good: { score: 3, text: 'Good', class: 'good', width: '100%' },
            strong: { score: 4, text: 'Strong', class: 'strong', width: '100%' }
        };
        
        this.init();
    }
    
    init() {
        this.createStrengthMeter();
        this.bindEvents();
        this.updateStrength('');
    }
    
    createStrengthMeter() {
        // Create container
        this.container = document.createElement('div');
        this.container.className = 'password-strength-container';
        
        // Create strength meter
        if (this.options.showStrengthBar) {
            this.strengthMeter = document.createElement('div');
            this.strengthMeter.className = 'password-strength-meter';
            
            this.strengthBar = document.createElement('div');
            this.strengthBar.className = 'password-strength-bar';
            this.strengthMeter.appendChild(this.strengthBar);
            
            this.container.appendChild(this.strengthMeter);
        }
        
        // Create strength text
        if (this.options.showStrengthText) {
            this.strengthText = document.createElement('div');
            this.strengthText.className = 'password-strength-text';
            this.container.appendChild(this.strengthText);
        }
        
        // Create requirements checklist
        if (this.options.showRequirements) {
            this.requirementsContainer = document.createElement('div');
            this.requirementsContainer.className = 'password-requirements';
            this.createRequirementsList();
            this.container.appendChild(this.requirementsContainer);
        }
        
        // Insert after password input
        this.passwordInput.parentNode.insertBefore(this.container, this.passwordInput.nextSibling);
    }
    
    createRequirementsList() {
        const title = document.createElement('h6');
        title.textContent = 'Password Requirements';
        this.requirementsContainer.appendChild(title);
        
        this.requirementsList = document.createElement('ul');
        this.requirementsContainer.appendChild(this.requirementsList);
        
        this.requirements = [
            {
                id: 'length',
                text: `At least ${this.options.minLength} characters`,
                test: (password) => password.length >= this.options.minLength
            }
        ];
        
        if (this.options.requireUppercase) {
            this.requirements.push({
                id: 'uppercase',
                text: 'At least one uppercase letter (A-Z)',
                test: (password) => /[A-Z]/.test(password)
            });
        }
        
        if (this.options.requireLowercase) {
            this.requirements.push({
                id: 'lowercase',
                text: 'At least one lowercase letter (a-z)',
                test: (password) => /[a-z]/.test(password)
            });
        }
        
        if (this.options.requireNumbers) {
            this.requirements.push({
                id: 'numbers',
                text: 'At least one number (0-9)',
                test: (password) => /\d/.test(password)
            });
        }
        
        if (this.options.requireSpecialChars) {
            this.requirements.push({
                id: 'special',
                text: 'At least one special character (!@#$%^&*)',
                test: (password) => /[!@#$%^&*(),.?":{}|<>]/.test(password)
            });
        }
        
        // Create requirement items
        this.requirementItems = {};
        this.requirements.forEach(req => {
            const li = document.createElement('li');
            li.id = `req-${req.id}`;
            li.className = 'requirement-unmet';
            li.textContent = req.text;
            this.requirementsList.appendChild(li);
            this.requirementItems[req.id] = li;
        });
    }
    
    bindEvents() {
        this.passwordInput.addEventListener('input', (e) => {
            this.updateStrength(e.target.value);
        });
        
        this.passwordInput.addEventListener('focus', () => {
            this.container.style.display = 'block';
        });
        
        // Hide requirements when password field loses focus and is empty
        this.passwordInput.addEventListener('blur', () => {
            if (!this.passwordInput.value) {
                this.container.style.display = 'none';
            }
        });
    }
    
    updateStrength(password) {
        const strength = this.calculateStrength(password);
        this.updateStrengthBar(strength);
        this.updateStrengthText(strength);
        this.updateRequirements(password);
    }
    
    calculateStrength(password) {
        if (!password) return this.strengthLevels.veryWeak;
        
        let score = 0;
        
        // Length score
        if (password.length >= this.options.minLength) score++;
        if (password.length >= this.options.minLength + 4) score++;
        
        // Character variety score
        if (/[a-z]/.test(password)) score++;
        if (/[A-Z]/.test(password)) score++;
        if (/\d/.test(password)) score++;
        if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) score++;
        
        // Bonus for longer passwords
        if (password.length >= 12) score++;
        if (password.length >= 16) score++;
        
        // Cap the score
        score = Math.min(score, 4);
        
        // Map score to strength level
        if (score <= 1) return this.strengthLevels.veryWeak;
        if (score <= 2) return this.strengthLevels.weak;
        if (score <= 3) return this.strengthLevels.fair;
        if (score <= 4) return this.strengthLevels.good;
        return this.strengthLevels.strong;
    }
    
    updateStrengthBar(strength) {
        if (!this.strengthBar) return;
        
        // Remove all strength classes
        this.strengthBar.className = 'password-strength-bar';
        this.strengthBar.classList.add(strength.class);
        
        // Set width using CSS custom property
        this.strengthBar.style.setProperty('--strength-width', strength.width);
    }
    
    updateStrengthText(strength) {
        if (!this.strengthText) return;
        
        this.strengthText.textContent = `Password Strength: ${strength.text}`;
        this.strengthText.className = `password-strength-text ${strength.class}`;
    }
    
    updateRequirements(password) {
        if (!this.requirementItems) return;
        
        this.requirements.forEach(req => {
            const item = this.requirementItems[req.id];
            if (req.test(password)) {
                item.className = 'requirement-met';
            } else {
                item.className = 'requirement-unmet';
            }
        });
    }
    
    getStrength() {
        const password = this.passwordInput.value;
        return this.calculateStrength(password);
    }
    
    isValid() {
        const password = this.passwordInput.value;
        if (!password) return false;
        
        return this.requirements.every(req => req.test(password));
    }
    
    destroy() {
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
    }
}

// Auto-initialize password strength meters for common password fields
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize for password fields that are NOT on login/forgot password pages
    const passwordFields = document.querySelectorAll('input[type="password"]');
    
    passwordFields.forEach(field => {
        // Skip if already has a strength meter
        if (field.nextElementSibling && field.nextElementSibling.classList.contains('password-strength-container')) {
            return;
        }
        
        // Skip login page password fields
        if (field.id === 'login-password') {
            return;
        }
        
        // Skip forgot password page (no password fields there)
        // Skip any password fields that are just for authentication, not creation
        
        // Only initialize for password creation/change fields
        const shouldHaveStrengthMeter = field.id && (
            field.id === 'new-password' ||
            field.id === 'register-password' ||
            field.id === 'reset-password' ||
            field.id === 'set-password'
        );
        
        if (shouldHaveStrengthMeter) {
            new PasswordStrengthMeter(field);
        }
    });
});

// Make PasswordStrengthMeter globally available
window.PasswordStrengthMeter = PasswordStrengthMeter;

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PasswordStrengthMeter;
}
