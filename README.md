# Contact Book Management System

An elegant Contact Book Management System featuring two interfaces:
1. 💻 **Terminal CLI App** — A beautiful command-line tool built using the `rich` library and stored in `contacts.json`.
2. 🌐 **Rolodex Web App** — A full-stack single-page application built with Flask, SQLite, and a custom CSS frontend themed as a classic library card catalog/rolodex.

On the first run of the Web App, it automatically performs a **one-time migration** importing any existing contacts from the CLI's `contacts.json` file into the SQLite database.

---

## Technical Stack & Layout

### Web Application (`/contact_book_web/`)
- **Backend**: Python, Flask, Flask-SQLAlchemy, SQLite
- **Frontend**: Single-Page App using semantic HTML5, Vanilla JavaScript (`fetch()`), and custom CSS.
- **Theme**: "Card Catalog / Rolodex" (utilizes custom Google Fonts like *Special Elite*, *Inter*, and *JetBrains Mono* with a warm paper card aesthetic).
- **Data Location**: SQLite database stored locally in `contact_book_web/contacts.db`.

### CLI Application (`/`)
- **Core Script**: `contact_book.py`
- **TUI Framework**: `rich` (beautiful progress reporting and menus).
- **Data Location**: JSON database stored in the root folder as `contacts.json`.

---

## Data Model (Web Database)

The database schema of the `contacts` table in `contacts.db` comprises:

| Column Name | Data Type | Constraint | Description |
|---|---|---|---|
| `id` | Integer | Primary Key, Autoincrement | Unique identifier |
| `name` | String(120) | Required, Case-insensitive Unique | Contact's full name |
| `phone` | String(40) | Optional, Loose Format Validation | Telephone number |
| `email` | String(160) | Optional, Basic Email Validation | Email address |
| `address` | String(300) | Optional | Physical address |
| `notes` | Text | Optional, Max 2000 chars | Memoranda and additional context |
| `favorite` | Boolean | Default `False`, Not Null | Pin contact cards to the top of lists |
| `created_at` | DateTime | Auto-managed, UTC | Timestamp when entry was created |
| `updated_at` | DateTime | Auto-managed, UTC | Timestamp when entry was last edited |

---

## Installation & Setup

Ensure Python 3.8+ is installed on your computer.

### 1. System Dependencies Setup
To install dependencies for either or both applications:

#### For the CLI Application:
Install requirements from the root directory:
```bash
pip install -r requirements.txt
```

#### For the Web Application:
Install requirements from the subfolder directory:
```bash
pip install -r contact_book_web/requirements.txt
```

---

## Running the Applications

### 💻 Running the Terminal CLI
To launch the command-line application, run from the root directory:
```bash
python contact_book.py
```
This updates and maintains your records locally in `contacts.json`.

### 🌐 Running the Web Application
To start the Flask backend web server:
1. Navigate into the web folder:
   ```bash
   cd contact_book_web
   ```
2. Launch the backend server:
   ```bash
   python app.py
   ```
3. Open your browser and navigate to:
   **[http://localhost:5000](http://localhost:5000)**

---

## REST API Documentation (`/api/*`)

All API payloads and response bodies exchange data in JSON format. Validation errors return `400 Bad Request` or `409 Conflict` (for duplicates) with the structure: `{"errors": ["Error description string"]}`.

### 1. List Contacts
- **Route**: `GET /api/contacts`
- **Query Parameters**:
  - `q` (string, optional) — Filter matches across name, phone, email, or address (case-insensitive).
  - `sort` (string, optional) — Sort by `name` (A-Z alphabetical, default) or `recent` (last modified date descending).
- **Behavior**: Contacts with `favorite = true` are pinned and sort to the top of the selected order.
- **Response** (`200 OK`):
  ```json
  {
    "contacts": [
      {
        "id": 1,
        "name": "Jane Doe",
        "phone": "555-0199",
        "email": "jane@example.com",
        "address": "123 Main St",
        "notes": "Book editor",
        "favorite": true,
        "created_at": "2026-07-04T02:00:00Z",
        "updated_at": "2026-07-04T03:00:00Z"
      }
    ],
    "total_count": 1,
    "initials": ["D", "M", "S"]
  }
  ```

### 2. Create Contact
- **Route**: `POST /api/contacts`
- **Payload**:
  ```json
  {
    "name": "Alex Bell",
    "phone": "555-1876",
    "email": "alex@telegraph.net",
    "address": "Boston, MA",
    "notes": "Invention log",
    "favorite": false
  }
  ```
- **Response** (`201 Created` or errors with `400`/`409`): Returns the newly created contact object.

### 3. Fetch Single Contact
- **Route**: `GET /api/contacts/<id>`
- **Response** (`200 OK` or `404 Not Found`): Returns the contact object matching the ID.

### 4. Update Contact
- **Route**: `PUT /api/contacts/<id>` or `PATCH /api/contacts/<id>`
- **Behavior**: Updates the specified fields. Runs validation and duplicate name checks (ignoring the entry's own ID).
- **Response** (`200 OK` or errors): Returns the updated contact object.

### 5. Delete Contact
- **Route**: `DELETE /api/contacts/<id>`
- **Response** (`200 OK`): `{"message": "Contact deleted successfully."}`

### 6. Toggle Favorite
- **Route**: `POST /api/contacts/<id>/favorite`
- **Response** (`200 OK`): Toggles the favorite status of the contact and returns the updated contact object.

### 7. Export Contacts to CSV
- **Route**: `GET /api/contacts/export`
- **Response** (`200 OK`): Returns a downloadable CSV file named `contacts.csv` containing all contacts (sorted A-Z).
  - **CSV Columns**: `name`, `phone`, `email`, `address`, `notes`, `favorite`, `created_at`, `updated_at`.

### 8. Import Contacts from CSV
- **Route**: `POST /api/contacts/import`
- **Payload** (`multipart/form-data`): A CSV file upload.
- **Behavior**: Parses row data and validates constraints.
  - Automatically skips rows with duplicate contact names (case-insensitive) to prevent database collisions.
  - Skips empty rows and logs other parsing warnings in the returned JSON.
- **Response** (`200 OK`):
  ```json
  {
    "imported": 12,
    "skipped": 2,
    "errors": ["Row 14 (Invalid Name): Name is required."]
  }
  ```

---

## Web App Layout & Rolodex Features
- **After Hours / Reading Room Theme Toggle**: An icon toggle in the cabinet brand header switches between the light "Reading Room" theme and the dark walnut wood "After Hours" theme, persisting the setting in memory during the active session.
- **A-Z Tab Rail**: Left-hand navigation divider tabs. Lists all letters. Letters that have active contact entries are clickable to filter the grid, while empty initials are disabled/muted.
- **Search bar**: Lives at the top of the interface. Dynamically debounces keystrokes and searches fields instantly.
- **Index-Card Tiles**: Renders contacts like physical cards inside a drawer, including a circular "punch hole" cut-out detail at the card bottom where drawer guide rods belong.
- **Inline Card Purge Overlay**: Clicking delete prompts a slide-up confirmation banner directly on the card itself, avoiding modal fatigue and aligning with the catalog physical context.
- **Notes Field Preview**: Surface contact memoranda/notes as a subtle, muted, smaller text snippet (first 60 characters with ellipsis `...` fallback) separated by a thin dashed divider below the address.
- **Save Notifications**: Fires subtle toast updates using active verbs (e.g. "Card inserted", "Changes saved", "Record purged", "Imported 12 cards, skipped 2 duplicates").

---

## Known Limitations
- **Single-User / Local Design**: Designed for single-user local access (SQLite & local file JSON databases). No user authentication, session tokens, or concurrent multi-user database transactions are implemented.
- **Session-Only Theme State**: The active theme preference is kept in client application memory and reset upon reloading the page.
- **Syncing CLI & Web Databases**: The one-time migration occurs on the initial boot of the Web app. Future updates in the CLI app `contacts.json` or Web app database `contacts.db` are kept independent and do not synchronize live.

