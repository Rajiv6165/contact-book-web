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
    selectedTag: '',
    isSelectMode: false,
    selectedContactIds: [],
    userTags: [], // list of all tags for suggestions/dropdown
    birthdayExpanded: true,
    isLoading: false,
    focusedElementBeforeModal: null,
    theme: 'light',
    modalSelectedTags: [] // tags currently added in the add/edit modal
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
const contactBirthdayInput = document.getElementById('contact-birthday');
const contactTagInput = document.getElementById('contact-tag-input');
const tagSuggestions = document.getElementById('tag-suggestions');
const modalTagsList = document.getElementById('modal-tags-list');
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

// New organizational DOM Elements
const tagFilterSelect = document.getElementById('tag-filter-select');
const selectModeBtn = document.getElementById('select-mode-btn');
const birthdayPanel = document.getElementById('birthday-panel');
const birthdayPanelToggle = document.getElementById('birthday-panel-toggle');
const birthdayPanelContent = document.getElementById('birthday-panel-content');

// Bulk action bar elements
const bulkActionBar = document.getElementById('bulk-action-bar');
const bulkSelectedCount = document.getElementById('bulk-selected-count');
const bulkTagInput = document.getElementById('bulk-tag-input');
const bulkTagApplyBtn = document.getElementById('bulk-tag-apply-btn');
const bulkExportBtn = document.getElementById('bulk-export-btn');
const bulkDeleteBtn = document.getElementById('bulk-delete-btn');
const bulkCancelBtn = document.getElementById('bulk-cancel-btn');

// Regex patterns for validation
const PHONE_REGEX = /^\+?[\d\s\-()\.]{3,40}$/;
const EMAIL_REGEX = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    fetchTags();
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

    // Theme toggle button
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    if (themeToggleBtn) {
        themeToggleBtn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
        `;
        themeToggleBtn.setAttribute('aria-label', 'Switch to After Hours dark theme');
        themeToggleBtn.addEventListener('click', toggleTheme);
    }

    // CSV Export button (Unselected global)
    const exportCsvBtn = document.getElementById('export-csv-btn');
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener('click', () => {
            window.location.href = '/api/contacts/export';
        });
    }

    // CSV Import button and file input
    const importCsvBtn = document.getElementById('import-csv-btn');
    const importCsvFile = document.getElementById('import-csv-file');
    if (importCsvBtn && importCsvFile) {
        importCsvBtn.addEventListener('click', () => {
            importCsvFile.click();
        });
        importCsvFile.addEventListener('change', handleImportCsv);
    }

    // --- Phase 2: Organization Listeners ---
    
    // Tag filter dropdown change
    if (tagFilterSelect) {
        tagFilterSelect.addEventListener('change', (e) => {
            state.selectedTag = e.target.value;
            fetchContacts();
        });
    }

    // Select mode toggle
    if (selectModeBtn) {
        selectModeBtn.addEventListener('click', toggleSelectMode);
    }

    // Collapsible birthday panel
    if (birthdayPanelToggle) {
        birthdayPanelToggle.addEventListener('click', () => {
            state.birthdayExpanded = !state.birthdayExpanded;
            birthdayPanelToggle.setAttribute('aria-expanded', state.birthdayExpanded);
            birthdayPanelContent.style.display = state.birthdayExpanded ? 'flex' : 'none';
        });
    }

    // Tag suggestions logic in Add/Edit modal
    if (contactTagInput) {
        contactTagInput.addEventListener('input', showTagSuggestions);
        contactTagInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const value = contactTagInput.value.trim();
                if (value) {
                    addModalTag(value);
                    contactTagInput.value = '';
                    hideTagSuggestions();
                }
            }
        });
        
        // Hide suggestions when clicking outside
        document.addEventListener('click', (e) => {
            if (!contactTagInput.contains(e.target) && !tagSuggestions.contains(e.target)) {
                hideTagSuggestions();
            }
        });
    }

    // Bulk actions bar setup
    if (bulkCancelBtn) {
        bulkCancelBtn.addEventListener('click', () => {
            toggleSelectMode();
        });
    }
    if (bulkTagApplyBtn) {
        bulkTagApplyBtn.addEventListener('click', applyBulkTag);
    }
    if (bulkDeleteBtn) {
        bulkDeleteBtn.addEventListener('click', applyBulkDelete);
    }
    if (bulkExportBtn) {
        bulkExportBtn.addEventListener('click', applyBulkExport);
    }
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

// Fetch all available tags
async function fetchTags() {
    try {
        const response = await fetch('/api/tags');
        if (!response.ok) throw new Error('Failed to fetch tags.');
        const data = await response.json();
        state.userTags = data.tags || [];
        renderTagsDropdown();
    } catch (err) {
        console.error('Error loading tags:', err);
    }
}

// Render dynamic tag dropdown options
function renderTagsDropdown() {
    if (!tagFilterSelect) return;
    const currentValue = tagFilterSelect.value;
    tagFilterSelect.innerHTML = '<option value="">All Tags</option>';
    state.userTags.forEach(tag => {
        const option = document.createElement('option');
        option.value = tag.name;
        option.textContent = tag.name;
        tagFilterSelect.appendChild(option);
    });
    tagFilterSelect.value = currentValue;
}

// Fetch Contacts API
async function fetchContacts() {
    showScreen('loading');
    state.isLoading = true;
    
    try {
        let url = `/api/contacts?q=${encodeURIComponent(state.searchQuery)}&sort=${state.sortBy}`;
        if (state.selectedTag) {
            url += `&tag=${encodeURIComponent(state.selectedTag)}`;
        }
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        state.contacts = data.contacts || [];
        state.initials = data.initials || [];
        
        renderUI();
        renderBirthdayPanel(data.upcoming_birthdays || []);
    } catch (err) {
        console.error('Fetch error:', err);
        showScreen('error');
        document.getElementById('error-message').textContent = 'Failed to load card catalog. Please try again.';
    } finally {
        state.isLoading = false;
    }
}

// Render upcoming birthdays drawer
function renderBirthdayPanel(upcomingBirthdays) {
    if (!birthdayPanel || !birthdayPanelContent) return;
    
    if (upcomingBirthdays.length === 0) {
        birthdayPanel.style.display = 'none';
        return;
    }
    
    birthdayPanel.style.display = 'block';
    birthdayPanelContent.innerHTML = '';
    
    upcomingBirthdays.forEach(item => {
        const row = document.createElement('div');
        row.className = 'birthday-item';
        
        const nameSpan = document.createElement('span');
        nameSpan.className = 'birthday-item-name';
        nameSpan.textContent = item.name;
        
        const dateSpan = document.createElement('span');
        dateSpan.className = 'birthday-item-date';
        dateSpan.textContent = formatBirthdayLabel(item.birthday);
        
        row.appendChild(nameSpan);
        row.appendChild(dateSpan);
        birthdayPanelContent.appendChild(row);
    });
}

// Convert YYYY-MM-DD into short clean format e.g. "Jul 12"
function formatBirthdayLabel(dateStr) {
    if (!dateStr) return '';
    try {
        const parts = dateStr.split('-');
        if (parts.length === 3) {
            const date = new Date(parts[0], parts[1] - 1, parts[2]);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        }
    } catch (e) {
        console.error('Date parsing error', e);
    }
    return dateStr;
}

// Render dynamic components
function renderUI() {
    renderAlphabetRail();
    renderCardsGrid();
    
    contactsCountDisplay.textContent = `Total cards: ${state.contacts.length}`;
}

// Render left side index tabs
function renderAlphabetRail() {
    alphabetList.innerHTML = '';
    
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
                if (state.activeLetter === letter) {
                    state.activeLetter = 'ALL';
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
    
    let filteredContacts = state.contacts;
    if (state.activeLetter !== 'ALL') {
        filteredContacts = state.contacts.filter(c => c.name && c.name[0].toUpperCase() === state.activeLetter);
    }
    
    if (state.contacts.length === 0) {
        if (state.searchQuery || state.selectedTag) {
            showScreen('no-results');
        } else {
            showScreen('empty');
        }
        return;
    }
    
    if (filteredContacts.length === 0) {
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
    
    if (state.isSelectMode) {
        card.classList.add('select-mode-active');
        
        // Add checkbox
        const chkContainer = document.createElement('div');
        chkContainer.className = 'card-select-checkbox-container';
        
        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.className = 'card-select-checkbox';
        chk.value = contact.id;
        chk.checked = state.selectedContactIds.includes(contact.id);
        chk.addEventListener('change', (e) => {
            const cid = parseInt(e.target.value);
            if (e.target.checked) {
                if (!state.selectedContactIds.includes(cid)) {
                    state.selectedContactIds.push(cid);
                }
            } else {
                state.selectedContactIds = state.selectedContactIds.filter(id => id !== cid);
            }
            updateBulkActionBar();
        });
        
        chkContainer.appendChild(chk);
        card.appendChild(chkContainer);
    }
    
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
    
    const favoriteBtn = document.createElement('button');
    favoriteBtn.type = 'button';
    favoriteBtn.className = `card-favorite-toggle ${contact.favorite ? 'active' : ''}`;
    favoriteBtn.setAttribute('aria-label', contact.favorite ? 'Remove Pin' : 'Pin to Top');
    favoriteBtn.innerHTML = contact.favorite 
        ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>`
        : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>`;
    
    if (state.isSelectMode) {
        favoriteBtn.disabled = true;
    } else {
        favoriteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleFavorite(contact.id);
        });
    }
    
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

    // Birthday indication
    if (contact.birthday) {
        const item = document.createElement('div');
        item.className = 'birthday-indicator';
        item.innerHTML = `🎂 ${formatBirthdayLabel(contact.birthday)}`;
        detailsDiv.appendChild(item);
    }
    
    cardTop.appendChild(detailsDiv);
    
    // Notes preview
    if (contact.notes && contact.notes.trim()) {
        const notesDiv = document.createElement('div');
        notesDiv.className = 'contact-notes';
        
        const trimmed = contact.notes.trim();
        if (trimmed.length > 60) {
            notesDiv.textContent = trimmed.substring(0, 60) + '...';
        } else {
            notesDiv.textContent = trimmed;
        }
        cardTop.appendChild(notesDiv);
    }

    // Render tag chips
    if (contact.tags && contact.tags.length > 0) {
        const tagsDiv = document.createElement('div');
        tagsDiv.className = 'card-tags-list';
        contact.tags.forEach(tag => {
            const chip = document.createElement('span');
            chip.className = 'tag-chip';
            chip.style.backgroundColor = tag.color;
            chip.textContent = tag.name;
            tagsDiv.appendChild(chip);
        });
        cardTop.appendChild(tagsDiv);
    }
    
    card.appendChild(cardTop);
    
    // Bottom Controls & Catalog Rod Hole
    const cardBottom = document.createElement('div');
    cardBottom.style.display = 'flex';
    cardBottom.style.flexDirection = 'column';
    
    const actionsRow = document.createElement('div');
    actionsRow.className = 'card-actions';
    
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'card-action-btn btn-edit';
    editBtn.setAttribute('aria-label', `Edit card for ${contact.name}`);
    editBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>`;
    
    if (state.isSelectMode) {
        editBtn.disabled = true;
    } else {
        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            openModal(contact);
        });
    }
    actionsRow.appendChild(editBtn);
    
    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'card-action-btn btn-delete';
    deleteBtn.setAttribute('aria-label', `Delete card for ${contact.name}`);
    deleteBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>`;
    
    if (state.isSelectMode) {
        deleteBtn.disabled = true;
    } else {
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            showInlineDeleteConfirm(card, contact);
        });
    }
    actionsRow.appendChild(deleteBtn);
    
    cardBottom.appendChild(actionsRow);
    
    const hole = document.createElement('div');
    hole.className = 'card-rod-hole';
    cardBottom.appendChild(hole);
    
    card.appendChild(cardBottom);
    
    return card;
}

// Inline card deletion confirmation overlay
function showInlineDeleteConfirm(cardElement, contact) {
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
        
        const index = state.contacts.findIndex(c => c.id === id);
        if (index !== -1) {
            state.contacts[index] = updatedContact;
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
        
        const card = document.querySelector(`.contact-card[data-id="${id}"]`);
        if (card) {
            const overlay = card.querySelector('.card-delete-overlay');
            if (overlay) overlay.remove();
        }
    }
}

// Modal open/close controls
function openModal(contact = null) {
    state.focusedElementBeforeModal = document.activeElement;
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
        contactBirthdayInput.value = contact.birthday || '';
        contactNotesInput.value = contact.notes || '';
        contactFavoriteInput.checked = !!contact.favorite;
        
        state.modalSelectedTags = (contact.tags || []).map(t => t.name);
        
        document.getElementById('save-form-btn').textContent = 'Save Changes';
    } else {
        // Create mode
        modalTitle.textContent = 'Add New Catalog Card';
        modalTabLabel.textContent = 'NEW ENTRY';
        
        contactForm.reset();
        contactIdInput.value = '';
        contactFavoriteInput.checked = false;
        state.modalSelectedTags = [];
        
        document.getElementById('save-form-btn').textContent = 'Insert Card';
    }
    
    renderModalTags();
    cardModal.style.display = 'flex';
    document.body.style.overflow = 'hidden'; // Lock body scroll
    
    setTimeout(() => {
        contactNameInput.focus();
    }, 50);
    
    cardModal.addEventListener('keydown', trapFocus);
}

function closeModal() {
    cardModal.style.display = 'none';
    document.body.style.overflow = ''; // Unlock body scroll
    cardModal.removeEventListener('keydown', trapFocus);
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

// Render currently selected tags in the Modal
function renderModalTags() {
    if (!modalTagsList) return;
    modalTagsList.innerHTML = '';
    
    state.modalSelectedTags.forEach(tname => {
        const tagObj = state.userTags.find(t => t.name.toLowerCase() === tname.toLowerCase());
        const color = tagObj ? tagObj.color : '#8C7866'; // fallback color if new
        
        const chip = document.createElement('span');
        chip.className = 'modal-tag-chip';
        chip.style.backgroundColor = color;
        chip.textContent = tname;
        
        const remove = document.createElement('span');
        remove.className = 'modal-tag-remove';
        remove.innerHTML = '&times;';
        remove.addEventListener('click', () => {
            removeModalTag(tname);
        });
        
        chip.appendChild(remove);
        modalTagsList.appendChild(chip);
    });
}

function addModalTag(tname) {
    tname = tname.trim();
    if (!tname) return;
    
    if (!state.modalSelectedTags.some(t => t.toLowerCase() === tname.toLowerCase())) {
        state.modalSelectedTags.push(tname);
        renderModalTags();
    }
}

function removeModalTag(tname) {
    state.modalSelectedTags = state.modalSelectedTags.filter(t => t.toLowerCase() !== tname.toLowerCase());
    renderModalTags();
}

function showTagSuggestions() {
    if (!tagSuggestions || !contactTagInput) return;
    
    const query = contactTagInput.value.trim().toLowerCase();
    if (!query) {
        hideTagSuggestions();
        return;
    }
    
    // Filter tags not already selected
    const filtered = state.userTags.filter(t => 
        t.name.toLowerCase().includes(query) && 
        !state.modalSelectedTags.some(selected => selected.toLowerCase() === t.name.toLowerCase())
    );
    
    if (filtered.length === 0) {
        hideTagSuggestions();
        return;
    }
    
    tagSuggestions.innerHTML = '';
    tagSuggestions.style.display = 'block';
    
    filtered.forEach(tag => {
        const item = document.createElement('div');
        item.className = 'tag-suggestion-item';
        item.innerHTML = `<span class="tag-chip" style="background-color: ${tag.color}; width: 12px; height: 12px; border-radius: 50%; display: inline-block;"></span> <span>${escapeHtml(tag.name)}</span>`;
        item.addEventListener('click', () => {
            addModalTag(tag.name);
            contactTagInput.value = '';
            hideTagSuggestions();
            contactTagInput.focus();
        });
        tagSuggestions.appendChild(item);
    });
}

function hideTagSuggestions() {
    if (tagSuggestions) {
        tagSuggestions.style.display = 'none';
        tagSuggestions.innerHTML = '';
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
        birthday: contactBirthdayInput.value,
        notes: contactNotesInput.value.trim(),
        favorite: contactFavoriteInput.checked,
        tags: state.modalSelectedTags
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

    if (data.birthday) {
        try {
            const dateObj = new Date(data.birthday);
            if (isNaN(dateObj.getTime())) {
                showFieldError(contactBirthdayInput, 'birthday', 'Invalid date format.');
                hasClientErrors = true;
            }
        } catch(e) {
            showFieldError(contactBirthdayInput, 'birthday', 'Invalid date format.');
            hasClientErrors = true;
        }
    }
    
    if (hasClientErrors) {
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
        
        // Refresh tags cache and contacts deck
        fetchTags();
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
    
    contactForm.scrollTop = 0;
    showToast('Filing failed. Check errors below.', 'danger');
}

function clearFormErrors() {
    formErrorBox.style.display = 'none';
    formErrorList.innerHTML = '';
    
    const inputs = [contactNameInput, contactPhoneInput, contactEmailInput, contactAddressInput, contactBirthdayInput, contactNotesInput];
    inputs.forEach(input => {
        if (input) {
            input.classList.remove('is-invalid');
            const errorSpan = document.getElementById(`error-${input.name}`);
            if (errorSpan) errorSpan.textContent = '';
        }
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

// Session-only theme toggle
function toggleTheme() {
    state.theme = (state.theme === 'light') ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', state.theme);
    
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
        if (state.theme === 'dark') {
            themeBtn.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
            `;
            themeBtn.setAttribute('aria-label', 'Switch to Reading Room light theme');
            showToast('After Hours theme active', 'success');
        } else {
            themeBtn.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
            `;
            themeBtn.setAttribute('aria-label', 'Switch to After Hours dark theme');
            showToast('Reading Room theme active', 'success');
        }
    }
}

// CSV import execution
async function handleImportCsv(e) {
    const file = e.target.files[0];
    if (!file) return;

    const inputElement = e.target;
    const formData = new FormData();
    formData.append('file', file);

    showToast('Parsing CSV upload...', 'success');

    try {
        const response = await fetch('/api/contacts/import', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        inputElement.value = '';

        if (!response.ok) {
            const errors = data.errors || ['Import processing failed.'];
            showToast(`Import failed: ${errors.join(', ')}`, 'danger');
            return;
        }

        const summary = `Imported ${data.imported} cards, skipped ${data.skipped} duplicates.`;
        showToast(summary, 'success');

        if (data.errors && data.errors.length > 0) {
            showToast(`Import warnings present. Check console.`, 'danger');
            console.warn('CSV Row Warnings:', data.errors);
        }

        fetchTags();
        fetchContacts();
    } catch (err) {
        console.error('Import upload error:', err);
        inputElement.value = '';
        showToast('Filing failed. Server error occurred.', 'danger');
    }
}

// --- Phase 2: Select Mode & Bulk Operations ---

function toggleSelectMode() {
    state.isSelectMode = !state.isSelectMode;
    state.selectedContactIds = [];
    
    if (state.isSelectMode) {
        selectModeBtn.classList.add('active');
        selectModeBtn.querySelector('span').textContent = 'Exit Selection';
    } else {
        selectModeBtn.classList.remove('active');
        selectModeBtn.querySelector('span').textContent = 'Select Mode';
    }
    
    updateBulkActionBar();
    renderUI();
}

function updateBulkActionBar() {
    if (!bulkActionBar) return;
    
    if (state.isSelectMode && state.selectedContactIds.length > 0) {
        bulkActionBar.style.display = 'block';
        bulkSelectedCount.textContent = `${state.selectedContactIds.length} item${state.selectedContactIds.length > 1 ? 's' : ''} selected`;
    } else {
        bulkActionBar.style.display = 'none';
        if (bulkTagInput) bulkTagInput.value = '';
    }
}

async function applyBulkTag() {
    const tname = bulkTagInput.value.trim();
    if (!tname) {
        showToast('Please enter a tag name.', 'danger');
        return;
    }
    
    try {
        const response = await fetch('/api/contacts/bulk-tag', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                ids: state.selectedContactIds,
                tag: tname
            })
        });
        
        if (!response.ok) throw new Error('Bulk tag failed.');
        
        showToast(`Tag "${tname}" applied to selected cards.`, 'success');
        
        toggleSelectMode(); // Exit select mode
        fetchTags();
        fetchContacts();
    } catch (e) {
        console.error(e);
        showToast('Filing failed. Could not apply bulk tag.', 'danger');
    }
}

async function applyBulkDelete() {
    const count = state.selectedContactIds.length;
    if (count === 0) return;
    
    if (!confirm(`Are you absolutely sure you want to permanently purge all ${count} selected records?`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/contacts/bulk-delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                ids: state.selectedContactIds
            })
        });
        
        if (!response.ok) throw new Error('Bulk delete failed.');
        
        showToast(`Purged ${count} records from database.`, 'success');
        toggleSelectMode(); // Exit select mode
        fetchContacts();
    } catch (e) {
        console.error(e);
        showToast('Filing failed. Could not delete records.', 'danger');
    }
}

function applyBulkExport() {
    const ids = state.selectedContactIds.join(',');
    if (!ids) return;
    window.location.href = `/api/contacts/export?ids=${ids}`;
    toggleSelectMode();
}
