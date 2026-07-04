/**
 * The Rolodex — Client-Side Application Script
 */

// Application State
const state = {
    contacts: [],
    initials: [],
    searchQuery: '',
    sortBy: 'name',
    activeLetter: 'ALL',
    isLoading: false,
    focusedElementBeforeModal: null
};

// DOM Elements
const contactsGrid = document.getElementById('contacts-grid');
const alphabetList = document.getElementById('alphabet-list');
const searchInput = document.getElementById('search-input');
const clearSearchBtn = document.getElementById('clear-search-btn');
const sortAlphaBtn = document.getElementById('sort-alpha');
const sortRecentBtn = document.getElementById('sort-recent');
const newContactBtn = document.getElementById('new-contact-btn');
const emptyCreateBtn = document.getElementById('empty-create-btn');
const contactsCountDisplay = document.getElementById('contacts-count');

// Modal Elements
const cardModal = document.getElementById('card-modal');
const modalTitle = document.getElementById('modal-title');
const modalTabLabel = document.getElementById('modal-tab-label');
const contactForm = document.getElementById('contact-form');
const contactIdInput = document.getElementById('contact-id');
const contactNameInput = document.getElementById('contact-name');
const contactPhoneInput = document.getElementById('contact-phone');
const contactEmailInput = document.getElementById('contact-email');
const contactAddressInput = document.getElementById('contact-address');
const contactNotesInput = document.getElementById('contact-notes');
const contactFavoriteInput = document.getElementById('contact-favorite');
const formErrorBox = document.getElementById('form-error-box');
const formErrorList = document.getElementById('form-error-list');
const closeModalBtn = document.getElementById('close-modal-btn');
const cancelFormBtn = document.getElementById('cancel-form-btn');

// State Screens
const loadingState = document.getElementById('loading-state');
const errorState = document.getElementById('error-state');
const emptyState = document.getElementById('empty-state');
const noResultsState = document.getElementById('no-results-state');
const retryBtn = document.getElementById('retry-btn');
const toastContainer = document.getElementById('toast-container');

// Regex patterns for validation
const PHONE_REGEX = /^\+?[\d\s\-()\.]{3,40}$/;
const EMAIL_REGEX = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    // Event Listeners
    setupEventListeners();
    
    // Initial Load
    fetchContacts();
});

function setupEventListeners() {
    // Search input (debounced)
    searchInput.addEventListener('input', debounce(() => {
        state.searchQuery = searchInput.value.trim();
        clearSearchBtn.style.display = state.searchQuery ? 'block' : 'none';
        fetchContacts();
    }, 300));

    // Clear search
    clearSearchBtn.addEventListener('click', () => {
        searchInput.value = '';
        state.searchQuery = '';
        clearSearchBtn.style.display = 'none';
        searchInput.focus();
        fetchContacts();
    });

    // Sort buttons
    sortAlphaBtn.addEventListener('click', () => changeSort('name'));
    sortRecentBtn.addEventListener('click', () => changeSort('recent'));

    // New Contact Button click
    newContactBtn.addEventListener('click', () => openModal());
    if (emptyCreateBtn) {
        emptyCreateBtn.addEventListener('click', () => openModal());
    }

    // Modal Close
    closeModalBtn.addEventListener('click', closeModal);
    cancelFormBtn.addEventListener('click', closeModal);
    
    // Modal Overlay click to close
    cardModal.addEventListener('click', (e) => {
        if (e.target === cardModal) closeModal();
    });

    // Escape Key to close Modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (cardModal.style.display !== 'none') {
                closeModal();
            }
        }
    });

    // Form Submit
    contactForm.addEventListener('submit', handleFormSubmit);

    // Form input errors clearing on type
    const inputs = [contactNameInput, contactPhoneInput, contactEmailInput, contactAddressInput, contactNotesInput];
    inputs.forEach(input => {
        input.addEventListener('input', () => {
            input.classList.remove('is-invalid');
            const errorSpan = document.getElementById(`error-${input.name}`);
            if (errorSpan) errorSpan.textContent = '';
        });
    });

    // Retry button on error screen
    retryBtn.addEventListener('click', () => {
        fetchContacts();
    });
}

// Debounce helper
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Sorting toggler
function changeSort(method) {
    if (state.sortBy === method) return;
    
    state.sortBy = method;
    if (method === 'name') {
        sortAlphaBtn.classList.add('active');
        sortAlphaBtn.setAttribute('aria-checked', 'true');
        sortRecentBtn.classList.remove('active');
        sortRecentBtn.setAttribute('aria-checked', 'false');
    } else {
        sortRecentBtn.classList.add('active');
        sortRecentBtn.setAttribute('aria-checked', 'true');
        sortAlphaBtn.classList.remove('active');
        sortAlphaBtn.setAttribute('aria-checked', 'false');
    }
    fetchContacts();
}

// Fetch Contacts API
async function fetchContacts() {
    showScreen('loading');
    state.isLoading = true;
    
    try {
        const url = `/api/contacts?q=${encodeURIComponent(state.searchQuery)}&sort=${state.sortBy}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        state.contacts = data.contacts || [];
        state.initials = data.initials || [];
        
        renderUI();
    } catch (err) {
        console.error('Fetch error:', err);
        showScreen('error');
        document.getElementById('error-message').textContent = 'Failed to load card catalog. Please try again.';
    } finally {
        state.isLoading = false;
    }
}

// Render dynamic components
function renderUI() {
    renderAlphabetRail();
    renderCardsGrid();
    
    // Update footer total count
    contactsCountDisplay.textContent = `Total cards: ${state.contacts.length}`;
}

// Render left side index tabs
function renderAlphabetRail() {
    alphabetList.innerHTML = '';
    
    // Create the 'ALL' tab at the top
    const allTab = document.createElement('button');
    allTab.type = 'button';
    allTab.className = `alpha-tab active-letter ${state.activeLetter === 'ALL' ? 'selected-filter' : ''}`;
    allTab.innerHTML = 'ALL';
    allTab.setAttribute('aria-label', 'Show all records');
    allTab.addEventListener('click', () => {
        state.activeLetter = 'ALL';
        renderUI();
    });
    alphabetList.appendChild(allTab);
    
    // Create A to Z tabs
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    alphabet.forEach(letter => {
        const tab = document.createElement('button');
        tab.type = 'button';
        
        const hasContacts = state.initials.includes(letter);
        const isSelected = state.activeLetter === letter;
        
        tab.className = 'alpha-tab';
        if (hasContacts) {
            tab.classList.add('active-letter');
        }
        if (isSelected) {
            tab.classList.add('selected-filter');
        }
        
        tab.textContent = letter;
        tab.setAttribute('aria-label', `Filter by letter ${letter}`);
        
        if (!hasContacts) {
            tab.disabled = true;
            tab.setAttribute('aria-disabled', 'true');
        } else {
            tab.addEventListener('click', () => {
                // Toggle filter
                if (state.activeLetter === letter) {
                    state.activeLetter = 'ALL'; // Reset if clicked again
                } else {
                    state.activeLetter = letter;
                }
                renderUI();
            });
        }
        
        alphabetList.appendChild(tab);
    });
}

// Render the grid of index cards
function renderCardsGrid() {
    contactsGrid.innerHTML = '';
    
    // Apply client-side letter filter if set
    let filteredContacts = state.contacts;
    if (state.activeLetter !== 'ALL') {
        filteredContacts = state.contacts.filter(c => c.name && c.name[0].toUpperCase() === state.activeLetter);
    }
    
    // Determine screen to show
    if (state.contacts.length === 0) {
        if (state.searchQuery) {
            showScreen('no-results');
        } else {
            showScreen('empty');
        }
        return;
    }
    
    if (filteredContacts.length === 0) {
        // letter filter yields nothing (e.g. search + letter combination empty)
        showScreen('no-results');
        return;
    }
    
    showScreen('grid');
    
    filteredContacts.forEach(contact => {
        const card = createContactCardElement(contact);
        contactsGrid.appendChild(card);
    });
}

// Create Card HTML Elements
function createContactCardElement(contact) {
    const card = document.createElement('article');
    card.className = `contact-card ${contact.favorite ? 'is-favorite' : ''}`;
    card.setAttribute('data-id', contact.id);
    
    // Index Card style background elements
    const marginLine = document.createElement('div');
    marginLine.className = 'contact-card-margin';
    card.appendChild(marginLine);
    
    const cardTop = document.createElement('div');
    cardTop.className = 'card-top';
    
    const headerRow = document.createElement('div');
    headerRow.className = 'card-header-row';
    
    const nameHeading = document.createElement('h3');
    nameHeading.className = 'contact-name';
    nameHeading.textContent = contact.name;
    headerRow.appendChild(nameHeading);
    
    // Favorite solid/regular star
    const favoriteBtn = document.createElement('button');
    favoriteBtn.type = 'button';
    favoriteBtn.className = `card-favorite-toggle ${contact.favorite ? 'active' : ''}`;
    favoriteBtn.setAttribute('aria-label', contact.favorite ? 'Remove Pin' : 'Pin to Top');
    favoriteBtn.innerHTML = contact.favorite 
        ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>`
        : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>`;
    favoriteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleFavorite(contact.id);
    });
    headerRow.appendChild(favoriteBtn);
    cardTop.appendChild(headerRow);
    
    // Details
    const detailsDiv = document.createElement('div');
    detailsDiv.className = 'contact-details';
    
    // Phone
    if (contact.phone) {
        const item = document.createElement('div');
        item.className = 'detail-item';
        item.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>
            <span class="detail-value monospace">${escapeHtml(contact.phone)}</span>
        `;
        detailsDiv.appendChild(item);
    }
    
    // Email
    if (contact.email) {
        const item = document.createElement('div');
        item.className = 'detail-item';
        item.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
            <span class="detail-value monospace">${escapeHtml(contact.email)}</span>
        `;
        detailsDiv.appendChild(item);
    }
    
    // Address
    if (contact.address) {
        const item = document.createElement('div');
        item.className = 'detail-item';
        item.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
            <span class="detail-value">${escapeHtml(contact.address)}</span>
        `;
        detailsDiv.appendChild(item);
    }
    
    cardTop.appendChild(detailsDiv);
    
    // Notes
    if (contact.notes) {
        const notesDiv = document.createElement('div');
        notesDiv.className = 'contact-notes';
        notesDiv.textContent = contact.notes;
        cardTop.appendChild(notesDiv);
    }
    
    card.appendChild(cardTop);
    
    // Bottom Controls & Catalog Rod Hole
    const cardBottom = document.createElement('div');
    cardBottom.style.display = 'flex';
    cardBottom.style.flexDirection = 'column';
    
    // Actions Row
    const actionsRow = document.createElement('div');
    actionsRow.className = 'card-actions';
    
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'card-action-btn btn-edit';
    editBtn.setAttribute('aria-label', `Edit card for ${contact.name}`);
    editBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>`;
    editBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openModal(contact);
    });
    actionsRow.appendChild(editBtn);
    
    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'card-action-btn btn-delete';
    deleteBtn.setAttribute('aria-label', `Delete card for ${contact.name}`);
    deleteBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>`;
    deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        showInlineDeleteConfirm(card, contact);
    });
    actionsRow.appendChild(deleteBtn);
    
    cardBottom.appendChild(actionsRow);
    
    // CSS Catalog guide-rod hole
    const hole = document.createElement('div');
    hole.className = 'card-rod-hole';
    cardBottom.appendChild(hole);
    
    card.appendChild(cardBottom);
    
    return card;
}

// Inline card deletion confirmation overlay
function showInlineDeleteConfirm(cardElement, contact) {
    // Check if delete overlay already exists
    if (cardElement.querySelector('.card-delete-overlay')) return;
    
    const overlay = document.createElement('div');
    overlay.className = 'card-delete-overlay';
    
    const text = document.createElement('div');
    text.className = 'delete-overlay-text';
    text.innerHTML = `Purge card for <br><strong>${escapeHtml(contact.name)}</strong>?`;
    overlay.appendChild(text);
    
    const actions = document.createElement('div');
    actions.className = 'delete-overlay-actions';
    
    const confirmBtn = document.createElement('button');
    confirmBtn.type = 'button';
    confirmBtn.className = 'delete-overlay-btn btn-confirm';
    confirmBtn.textContent = 'Purge';
    confirmBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteContact(contact.id, contact.name);
    });
    actions.appendChild(confirmBtn);
    
    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'delete-overlay-btn btn-cancel';
    cancelBtn.textContent = 'Keep';
    cancelBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        overlay.remove();
        cardElement.focus();
    });
    actions.appendChild(cancelBtn);
    
    overlay.appendChild(actions);
    
    // Prevent clicking other things inside the card during overlay
    overlay.addEventListener('click', (e) => {
        e.stopPropagation();
    });
    
    cardElement.appendChild(overlay);
    confirmBtn.focus();
}

// Screen management states
function showScreen(screen) {
    loadingState.style.display = screen === 'loading' ? 'flex' : 'none';
    errorState.style.display = screen === 'error' ? 'flex' : 'none';
    emptyState.style.display = screen === 'empty' ? 'flex' : 'none';
    noResultsState.style.display = screen === 'no-results' ? 'flex' : 'none';
    contactsGrid.style.display = screen === 'grid' ? 'grid' : 'none';
}

// API: Toggle Favorite
async function toggleFavorite(id) {
    try {
        const response = await fetch(`/api/contacts/${id}/favorite`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) {
            throw new Error('Failed to toggle favorite status.');
        }
        
        const updatedContact = await response.json();
        
        // Update local state instantly and re-sort / re-render
        const index = state.contacts.findIndex(c => c.id === id);
        if (index !== -1) {
            state.contacts[index] = updatedContact;
            
            // Re-sort the local array depending on state.sortBy
            sortContactsArray();
            renderUI();
            
            const actionText = updatedContact.favorite ? 'Card pinned' : 'Card unpinned';
            showToast(`${actionText} for ${updatedContact.name}`);
        }
    } catch (err) {
        console.error(err);
        showToast('Error toggling pin status.', 'danger');
    }
}

// Sort contacts helper to make updates instant
function sortContactsArray() {
    state.contacts.sort((a, b) => {
        // Pin favorites to top
        if (a.favorite && !b.favorite) return -1;
        if (!a.favorite && b.favorite) return 1;
        
        if (state.sortBy === 'recent') {
            const dateA = new Date(a.updated_at);
            const dateB = new Date(b.updated_at);
            return dateB - dateA;
        } else {
            return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
        }
    });
}

// API: Delete Contact
async function deleteContact(id, name) {
    try {
        const response = await fetch(`/api/contacts/${id}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Failed to delete contact.');
        }
        
        showToast(`Record purged for ${name}`, 'success');
        fetchContacts();
    } catch (err) {
        console.error(err);
        showToast(`Could not delete record for ${name}.`, 'danger');
        
        // Remove delete overlay to let user try again
        const card = document.querySelector(`.contact-card[data-id="${id}"]`);
        if (card) {
            const overlay = card.querySelector('.card-delete-overlay');
            if (overlay) overlay.remove();
        }
    }
}

// Modal open/close controls
function openModal(contact = null) {
    // Record current focus element
    state.focusedElementBeforeModal = document.activeElement;
    
    // Clear previous errors
    clearFormErrors();
    
    if (contact) {
        // Edit mode
        modalTitle.textContent = 'Edit Catalog Card';
        modalTabLabel.textContent = `ENTRY #${contact.id}`;
        
        contactIdInput.value = contact.id;
        contactNameInput.value = contact.name || '';
        contactPhoneInput.value = contact.phone || '';
        contactEmailInput.value = contact.email || '';
        contactAddressInput.value = contact.address || '';
        contactNotesInput.value = contact.notes || '';
        contactFavoriteInput.checked = !!contact.favorite;
        
        document.getElementById('save-form-btn').textContent = 'Save Changes';
    } else {
        // Create mode
        modalTitle.textContent = 'Add New Catalog Card';
        modalTabLabel.textContent = 'NEW ENTRY';
        
        contactForm.reset();
        contactIdInput.value = '';
        contactFavoriteInput.checked = false;
        
        document.getElementById('save-form-btn').textContent = 'Insert Card';
    }
    
    cardModal.style.display = 'flex';
    document.body.style.overflow = 'hidden'; // Lock body scroll
    
    // Focus first input
    setTimeout(() => {
        contactNameInput.focus();
    }, 50);
    
    // Bind Tab Trap
    cardModal.addEventListener('keydown', trapFocus);
}

function closeModal() {
    cardModal.style.display = 'none';
    document.body.style.overflow = ''; // Unlock body scroll
    
    // Unbind Tab Trap
    cardModal.removeEventListener('keydown', trapFocus);
    
    // Restore focus
    if (state.focusedElementBeforeModal) {
        state.focusedElementBeforeModal.focus();
    }
}

// Focus Trap helper for accessibility
function trapFocus(e) {
    if (e.key !== 'Tab') return;
    
    const focusableElements = cardModal.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    
    if (e.shiftKey) {
        if (document.activeElement === firstElement) {
            lastElement.focus();
            e.preventDefault();
        }
    } else {
        if (document.activeElement === lastElement) {
            firstElement.focus();
            e.preventDefault();
        }
    }
}

// Client Side + Server Side Form validation and submission
async function handleFormSubmit(e) {
    e.preventDefault();
    clearFormErrors();
    
    const id = contactIdInput.value;
    const isEdit = !!id;
    
    const data = {
        name: contactNameInput.value.trim(),
        phone: contactPhoneInput.value.trim(),
        email: contactEmailInput.value.trim(),
        address: contactAddressInput.value.trim(),
        notes: contactNotesInput.value.trim(),
        favorite: contactFavoriteInput.checked
    };
    
    // 1. Client Side Validation
    let hasClientErrors = false;
    
    if (!data.name) {
        showFieldError(contactNameInput, 'name', 'Name is required.');
        hasClientErrors = true;
    } else if (data.name.length > 120) {
        showFieldError(contactNameInput, 'name', 'Name must not exceed 120 characters.');
        hasClientErrors = true;
    }
    
    if (data.phone) {
        if (data.phone.length > 40) {
            showFieldError(contactPhoneInput, 'phone', 'Phone number must not exceed 40 characters.');
            hasClientErrors = true;
        } else if (!PHONE_REGEX.test(data.phone)) {
            showFieldError(contactPhoneInput, 'phone', 'Invalid format. Use numbers, spaces, hyphens, dots, parentheses, and leading +.');
            hasClientErrors = true;
        }
    }
    
    if (data.email) {
        if (data.email.length > 160) {
            showFieldError(contactEmailInput, 'email', 'Email must not exceed 160 characters.');
            hasClientErrors = true;
        } else if (!EMAIL_REGEX.test(data.email)) {
            showFieldError(contactEmailInput, 'email', 'Invalid email format.');
            hasClientErrors = true;
        }
    }
    
    if (data.address && data.address.length > 300) {
        showFieldError(contactAddressInput, 'address', 'Address must not exceed 300 characters.');
        hasClientErrors = true;
    }
    
    if (data.notes && data.notes.length > 2000) {
        showFieldError(contactNotesInput, 'notes', 'Notes must not exceed 2000 characters.');
        hasClientErrors = true;
    }
    
    if (hasClientErrors) {
        // Focus first field with error
        const firstError = contactForm.querySelector('.is-invalid');
        if (firstError) firstError.focus();
        return;
    }
    
    // 2. Submit to Server
    try {
        const url = isEdit ? `/api/contacts/${id}` : '/api/contacts';
        const method = isEdit ? 'PATCH' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        const responseData = await response.json();
        
        if (!response.ok) {
            if (response.status === 409 || response.status === 400) {
                // Validation error or Duplicate from server
                const errors = responseData.errors || ['Server validation failed.'];
                showServerFormErrors(errors);
            } else {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return;
        }
        
        // Success
        closeModal();
        
        const actionMessage = isEdit ? 'Changes saved' : 'Card inserted';
        showToast(`${actionMessage} for ${responseData.name}`, 'success');
        
        // Re-load contacts
        fetchContacts();
        
    } catch (err) {
        console.error('Submit error:', err);
        showToast('Filing failed. Server error occurred.', 'danger');
    }
}

// Field validation display helpers
function showFieldError(inputElement, fieldName, message) {
    inputElement.classList.add('is-invalid');
    const errorSpan = document.getElementById(`error-${fieldName}`);
    if (errorSpan) {
        errorSpan.textContent = message;
    }
}

function showServerFormErrors(errors) {
    formErrorBox.style.display = 'block';
    formErrorList.innerHTML = '';
    
    errors.forEach(err => {
        const li = document.createElement('li');
        li.textContent = err;
        formErrorList.appendChild(li);
    });
    
    // Scroll form to top to see error box
    contactForm.scrollTop = 0;
    
    showToast('Filing failed. Check errors below.', 'danger');
}

function clearFormErrors() {
    formErrorBox.style.display = 'none';
    formErrorList.innerHTML = '';
    
    const inputs = [contactNameInput, contactPhoneInput, contactEmailInput, contactAddressInput, contactNotesInput];
    inputs.forEach(input => {
        input.classList.remove('is-invalid');
        const errorSpan = document.getElementById(`error-${input.name}`);
        if (errorSpan) errorSpan.textContent = '';
    });
}

// Toast Controller
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type === 'danger' ? 'toast-danger' : ''}`;
    
    const textSpan = document.createElement('span');
    textSpan.textContent = message;
    toast.appendChild(textSpan);
    
    const closeBtn = document.createElement('button');
    closeBtn.className = 'toast-close';
    closeBtn.innerHTML = '&times;';
    closeBtn.addEventListener('click', () => toast.remove());
    toast.appendChild(closeBtn);
    
    toastContainer.appendChild(toast);
    
    // Auto remove toast after 4s
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.5s ease';
        setTimeout(() => toast.remove(), 500);
    }, 4000);
}

// Escape HTML utility for security
function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
