import os
import sys
import unittest
import json
import io
from datetime import datetime, timezone, timedelta
from PIL import Image

# Ensure the contact_book_web directory is on the path
sys.path.append(os.path.dirname(__file__))

from app import app, db, Contact, User, Tag

class ContactBookTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SECRET_KEY'] = 'test-secret'
        
        self.client = app.test_client()
        
        with app.app_context():
            db.create_all()
            
            # Create a test user
            from werkzeug.security import generate_password_hash
            self.user = User(
                username='testuser',
                email='testuser@example.com',
                password_hash=generate_password_hash('testpassword')
            )
            db.session.add(self.user)
            db.session.commit()
            self.user_id = self.user.id
            
        # Log in the user by injecting the user_id into the session
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_create_contact(self):
        payload = {
            "name": "Test Contact",
            "phone": "+1 (555) 123-4567",
            "email": "test@example.com",
            "address": "123 Test St",
            "notes": "Some test notes",
            "favorite": True
        }
        response = self.client.post('/api/contacts', json=payload)
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['name'], "Test Contact")
        self.assertEqual(data['phone'], "+1 (555) 123-4567")
        self.assertEqual(data['email'], "test@example.com")
        self.assertEqual(data['address'], "123 Test St")
        self.assertEqual(data['notes'], "Some test notes")
        self.assertTrue(data['favorite'])

    def test_create_duplicate_contact(self):
        payload = {"name": "Duplicate Contact"}
        # First creation
        response1 = self.client.post('/api/contacts', json=payload)
        self.assertEqual(response1.status_code, 201)
        
        # Second creation (should fail)
        response2 = self.client.post('/api/contacts', json=payload)
        self.assertEqual(response2.status_code, 409)

    def test_get_contacts(self):
        payload = {"name": "Alice"}
        self.client.post('/api/contacts', json=payload)
        
        response = self.client.get('/api/contacts')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['total_count'], 1)
        self.assertEqual(data['contacts'][0]['name'], "Alice")

    def test_update_contact(self):
        payload = {"name": "Bob", "phone": "+1 (555) 111-2222"}
        res = self.client.post('/api/contacts', json=payload)
        c_id = json.loads(res.data)['id']
        
        update_payload = {"phone": "+1 (555) 333-4444"}
        response = self.client.patch(f'/api/contacts/{c_id}', json=update_payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['phone'], "+1 (555) 333-4444")

    def test_delete_contact(self):
        payload = {"name": "Charlie"}
        res = self.client.post('/api/contacts', json=payload)
        c_id = json.loads(res.data)['id']
        
        response = self.client.delete(f'/api/contacts/{c_id}')
        self.assertEqual(response.status_code, 200)
        
        response_get = self.client.get(f'/api/contacts/{c_id}')
        self.assertEqual(response_get.status_code, 404)

    def test_invalid_email_phone(self):
        # Invalid email format
        payload = {"name": "Invalid Email", "email": "not-an-email"}
        response = self.client.post('/api/contacts', json=payload)
        self.assertEqual(response.status_code, 400)
        
        # Invalid phone format
        payload = {"name": "Invalid Phone", "phone": "12"} # too short or wrong pattern
        response = self.client.post('/api/contacts', json=payload)
        self.assertEqual(response.status_code, 400)

    def test_export_contacts(self):
        # Insert two contacts
        self.client.post('/api/contacts', json={"name": "Alice", "phone": "+1 (555) 111-2222"})
        self.client.post('/api/contacts', json={"name": "Bob", "phone": "+1 (555) 333-4444", "favorite": True})
        
        response = self.client.get('/api/contacts/export')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename=contacts.csv', response.headers['Content-Disposition'])
        
        csv_data = response.data.decode('utf-8')
        self.assertIn('name,phone,email,address,notes,favorite,birthday,tags,created_at,updated_at', csv_data)
        self.assertIn('Alice', csv_data)
        self.assertIn('Bob', csv_data)

    def test_import_contacts(self):
        csv_content = (
            "name,phone,email,address,notes,favorite\n"
            "Dave,+1 (555) 555-5555,dave@example.com,Address D,Notes D,true\n"
            "Eve,+1 (555) 777-7777,eve@example.com,Address E,Notes E,false\n"
        )
        
        data = {
            'file': (io.BytesIO(csv_content.encode('utf-8')), 'contacts.csv')
        }
        
        response = self.client.post(
            '/api/contacts/import',
            data=data,
            content_type='multipart/form-data'
        )
        
        self.assertEqual(response.status_code, 200)
        resp_data = json.loads(response.data)
        self.assertEqual(resp_data['imported'], 2)
        self.assertEqual(resp_data['skipped'], 0)
        self.assertEqual(len(resp_data['errors']), 0)
        
        # Check if contacts are created
        get_res = self.client.get('/api/contacts')
        contacts_data = json.loads(get_res.data)['contacts']
        self.assertEqual(len(contacts_data), 2)
        self.assertEqual(contacts_data[0]['name'], 'Dave')
        self.assertTrue(contacts_data[0]['favorite'])

    def test_health_check_bypasses_auth(self):
        anonymous_client = app.test_client()
        response = anonymous_client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')

    def test_unauthenticated_api_returns_401(self):
        anonymous_client = app.test_client()
        response = anonymous_client.get('/api/contacts')
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn("Unauthorized. Please login.", data['errors'])

    def test_unauthenticated_html_redirects_to_login(self):
        anonymous_client = app.test_client()
        response = anonymous_client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['Location'].endswith('/login'))

    def test_registration_and_login_flow(self):
        anonymous_client = app.test_client()
        
        # Test password strength validation (less than 8 chars)
        reg_payload = {
            "username": "newlibrarian",
            "email": "new@example.com",
            "password": "short",
            "confirm_password": "short"
        }
        response = anonymous_client.post('/register', data=reg_payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Password must be at least 8 characters long.", response.data)
        
        # Test password mismatch
        reg_payload["password"] = "securepassword"
        reg_payload["confirm_password"] = "mismatchpassword"
        response = anonymous_client.post('/register', data=reg_payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Passwords do not match.", response.data)
        
        # Successful registration
        reg_payload["confirm_password"] = "securepassword"
        response = anonymous_client.post('/register', data=reg_payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['Location'].endswith('/login?registered=true'))
        
        # Test login failure
        login_payload = {
            "username": "newlibrarian",
            "password": "wrongpassword"
        }
        response = anonymous_client.post('/login', data=login_payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password.", response.data)
        
        # Test login success
        login_payload["password"] = "securepassword"
        response = anonymous_client.post('/login', data=login_payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['Location'].endswith('/'))

    def test_user_contact_isolation(self):
        # Create a contact as the default logged in testuser (self.user)
        payload = {"name": "User A Contact"}
        res = self.client.post('/api/contacts', json=payload)
        self.assertEqual(res.status_code, 201)
        contact_id = json.loads(res.data)['id']
        
        # Create a second user B
        with app.app_context():
            from werkzeug.security import generate_password_hash
            user_b = User(
                username='user_b',
                email='userb@example.com',
                password_hash=generate_password_hash('passwordB')
            )
            db.session.add(user_b)
            db.session.commit()
            user_b_id = user_b.id
            
        # Create a client for user B
        client_b = app.test_client()
        with client_b.session_transaction() as sess:
            sess['user_id'] = user_b_id
            
        # User B should not see User A's contact in listing
        response = client_b.get('/api/contacts')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['total_count'], 0)
        
        # User B should get 404 when trying to get User A's contact directly
        response = client_b.get(f'/api/contacts/{contact_id}')
        self.assertEqual(response.status_code, 404)
        
        # User B should get 404 when trying to update User A's contact
        response = client_b.patch(f'/api/contacts/{contact_id}', json={"phone": "12345678"})
        self.assertEqual(response.status_code, 404)
        
        # User B should get 404 when trying to delete User A's contact
        response = client_b.delete(f'/api/contacts/{contact_id}')
        self.assertEqual(response.status_code, 404)

    # --- Phase 2: Contact Organization Tests ---

    def test_create_tag_and_association(self):
        payload = {
            "name": "Tagged Contact",
            "tags": ["Work", "Personal", "Work"]  # tests deduplication and creation
        }
        response = self.client.post('/api/contacts', json=payload)
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(len(data['tags']), 2)
        tag_names = [t['name'] for t in data['tags']]
        self.assertIn("Work", tag_names)
        self.assertIn("Personal", tag_names)
        
        # Check colors are assigned
        for t in data['tags']:
            self.assertTrue(t['color'].startswith('#'))
        
        # Verify tags list API
        response_tags = self.client.get('/api/tags')
        self.assertEqual(response_tags.status_code, 200)
        tags_data = json.loads(response_tags.data)['tags']
        self.assertEqual(len(tags_data), 2)
        
        # Test filtering contacts by tag
        response_filter = self.client.get('/api/contacts?tag=Work')
        self.assertEqual(response_filter.status_code, 200)
        filter_data = json.loads(response_filter.data)
        self.assertEqual(filter_data['total_count'], 1)
        self.assertEqual(filter_data['contacts'][0]['name'], "Tagged Contact")

    def test_tag_user_isolation(self):
        # Create tag for User A
        self.client.post('/api/contacts', json={"name": "Alice", "tags": ["SecretTag"]})
        
        # Create User B
        with app.app_context():
            from werkzeug.security import generate_password_hash
            user_b = User(
                username='user_b',
                email='userb@example.com',
                password_hash=generate_password_hash('passwordB')
            )
            db.session.add(user_b)
            db.session.commit()
            user_b_id = user_b.id
            
        client_b = app.test_client()
        with client_b.session_transaction() as sess:
            sess['user_id'] = user_b_id
            
        # User B should have 0 tags
        response = client_b.get('/api/tags')
        self.assertEqual(response.status_code, 200)
        tags_data = json.loads(response.data)['tags']
        self.assertEqual(len(tags_data), 0)

        # User B tries filtering by User A's tag name
        response_filter = client_b.get('/api/contacts?tag=SecretTag')
        self.assertEqual(response_filter.status_code, 200)
        self.assertEqual(json.loads(response_filter.data)['total_count'], 0)

    def test_birthday_validation_and_upcoming(self):
        # Test invalid date formatting
        payload = {"name": "Bad Bday", "birthday": "1980-44-88"}
        response = self.client.post('/api/contacts', json=payload)
        self.assertEqual(response.status_code, 400)
        
        # Calculate dates for upcoming checks
        from datetime import date, timedelta
        today = date.today()
        bday_upcoming = today + timedelta(days=10)
        bday_far = today + timedelta(days=45)
        
        bday_upcoming_str = f"1985-{bday_upcoming.month:02d}-{bday_upcoming.day:02d}"
        bday_far_str = f"1985-{bday_far.month:02d}-{bday_far.day:02d}"
        
        self.client.post('/api/contacts', json={"name": "Upcoming Contact", "birthday": bday_upcoming_str})
        self.client.post('/api/contacts', json={"name": "Far Contact", "birthday": bday_far_str})
        
        # Verify upcoming birthdays returned in main list endpoint
        response = self.client.get('/api/contacts')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        upcoming_names = [c['name'] for c in data['upcoming_birthdays']]
        self.assertIn("Upcoming Contact", upcoming_names)
        self.assertNotIn("Far Contact", upcoming_names)

    def test_bulk_delete(self):
        # User A contacts
        c1 = self.client.post('/api/contacts', json={"name": "C1"}).get_json()
        c2 = self.client.post('/api/contacts', json={"name": "C2"}).get_json()
        
        # User B setup
        with app.app_context():
            from werkzeug.security import generate_password_hash
            user_b = User(
                username='user_b',
                email='userb@example.com',
                password_hash=generate_password_hash('passwordB')
            )
            db.session.add(user_b)
            db.session.commit()
            user_b_id = user_b.id
            
        client_b = app.test_client()
        with client_b.session_transaction() as sess:
            sess['user_id'] = user_b_id
        c3 = client_b.post('/api/contacts', json={"name": "C3"}).get_json()
        
        # User B bulk deletes c1 (belonging to A) and c3 (belonging to B)
        payload = {"ids": [c1['id'], c3['id']]}
        response = client_b.post('/api/contacts/bulk-delete', json=payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("Successfully moved 1 contacts to Trash.", data['message']) # only c3 soft deleted
        
        # Verify c1 still exists for User A
        response_a = self.client.get(f'/api/contacts/{c1["id"]}')
        self.assertEqual(response_a.status_code, 200)
        
        # Verify c3 is deleted for User B
        response_b = client_b.get(f'/api/contacts/{c3["id"]}')
        self.assertEqual(response_b.status_code, 404)

    def test_bulk_tag(self):
        c1 = self.client.post('/api/contacts', json={"name": "C1"}).get_json()
        
        with app.app_context():
            from werkzeug.security import generate_password_hash
            user_b = User(
                username='user_b',
                email='userb@example.com',
                password_hash=generate_password_hash('passwordB')
            )
            db.session.add(user_b)
            db.session.commit()
            user_b_id = user_b.id
            
        client_b = app.test_client()
        with client_b.session_transaction() as sess:
            sess['user_id'] = user_b_id
        c3 = client_b.post('/api/contacts', json={"name": "C3"}).get_json()
        
        # User B bulk tags c1 and c3
        payload = {"ids": [c1['id'], c3['id']], "tag": "Work"}
        response = client_b.post('/api/contacts/bulk-tag', json=payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("Successfully added tag 'Work' to 1 contacts.", data['message'])
        
        # User A's c1 should not be tagged
        c1_updated = self.client.get(f'/api/contacts/{c1["id"]}').get_json()
        self.assertEqual(len(c1_updated['tags']), 0)
        
        # User B's c3 should be tagged
        c3_updated = client_b.get(f'/api/contacts/{c3["id"]}').get_json()
        self.assertEqual(len(c3_updated['tags']), 1)
        self.assertEqual(c3_updated['tags'][0]['name'], "Work")

    def test_bulk_export(self):
        c1 = self.client.post('/api/contacts', json={"name": "Alice"}).get_json()
        c2 = self.client.post('/api/contacts', json={"name": "Bob"}).get_json()
        c3 = self.client.post('/api/contacts', json={"name": "Charlie"}).get_json()
        
        response = self.client.get(f'/api/contacts/export?ids={c1["id"]},{c3["id"]}')
        self.assertEqual(response.status_code, 200)
        csv_data = response.data.decode('utf-8')
        self.assertIn('Alice', csv_data)
        self.assertIn('Charlie', csv_data)
        self.assertNotIn('Bob', csv_data)

    def test_avatar_upload_validations(self):
        # Create a contact
        contact_json = self.client.post('/api/contacts', json={"name": "Photo User"}).get_json()
        c_id = contact_json['id']
        
        # Test 1: Upload non-image file type (should fail)
        data = {
            'file': (io.BytesIO(b"dummy text content"), "test.txt")
        }
        response = self.client.post(
            f'/api/contacts/{c_id}/avatar',
            data=data,
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid file type", json.loads(response.data)['errors'][0])
        
        # Test 2: Upload oversized image (> 3MB) (should fail)
        large_content = b"0" * (3 * 1024 * 1024 + 100) # just over 3MB of raw bytes
        data = {
            'file': (io.BytesIO(large_content), "large.png")
        }
        response = self.client.post(
            f'/api/contacts/{c_id}/avatar',
            data=data,
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("File size exceeds 3MB limit", json.loads(response.data)['errors'][0])

        # Test 3: Upload valid image and verify resizing + saving
        from PIL import Image
        img_io = io.BytesIO()
        # Create a large image to test resizing
        img = Image.new('RGB', (600, 600), color='blue')
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        data = {
            'file': (img_io, "valid.png")
        }
        response = self.client.post(
            f'/api/contacts/{c_id}/avatar',
            data=data,
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, 200)
        res_data = json.loads(response.data)
        self.assertTrue(res_data['avatar_url'].startswith('/static/avatars/'))
        
        # Check that file exists on disk
        from app import AVATAR_UPLOAD_FOLDER
        filename = res_data['avatar_url'].split('/')[-1]
        saved_path = os.path.join(AVATAR_UPLOAD_FOLDER, filename)
        self.assertTrue(os.path.exists(saved_path))
        
        # Check that saved image is resized to <= 400x400
        with Image.open(saved_path) as saved_img:
            self.assertTrue(saved_img.size[0] <= 400)
            self.assertTrue(saved_img.size[1] <= 400)

        # Test 4: Replace avatar and confirm old file is deleted
        old_path = saved_path
        
        img_io2 = io.BytesIO()
        img2 = Image.new('RGB', (100, 100), color='green')
        img2.save(img_io2, 'JPEG')
        img_io2.seek(0)
        
        data2 = {
            'file': (img_io2, "valid2.jpg")
        }
        response2 = self.client.post(
            f'/api/contacts/{c_id}/avatar',
            data=data2,
            content_type='multipart/form-data'
        )
        self.assertEqual(response2.status_code, 200)
        res_data2 = json.loads(response2.data)
        
        # Verify old file is deleted from disk
        self.assertFalse(os.path.exists(old_path))
        
        # Verify new file exists on disk
        filename2 = res_data2['avatar_url'].split('/')[-1]
        saved_path2 = os.path.join(AVATAR_UPLOAD_FOLDER, filename2)
        self.assertTrue(os.path.exists(saved_path2))

        # Test 5: Delete contact (soft delete) should keep the file, but permanent delete should purge it
        soft_delete_response = self.client.delete(f'/api/contacts/{c_id}')
        self.assertEqual(soft_delete_response.status_code, 200)
        self.assertTrue(os.path.exists(saved_path2)) # file still exists because soft deleted
        
        # Permanent delete
        delete_response = self.client.delete(f'/api/contacts/{c_id}/permanent')
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(os.path.exists(saved_path2)) # file is now purged

    def test_soft_delete_and_restore(self):
        # Create contact
        contact_json = self.client.post('/api/contacts', json={"name": "Soft Delete Target"}).get_json()
        c_id = contact_json['id']
        
        # Soft delete
        response = self.client.delete(f'/api/contacts/{c_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['message'], "Contact moved to Trash.")
        
        # Verify excluded from main list
        response_list = self.client.get('/api/contacts')
        self.assertEqual(response_list.status_code, 200)
        list_data = json.loads(response_list.data)
        self.assertEqual(list_data['total_count'], 0)
        self.assertEqual(list_data['trash_count'], 1)
        
        # Verify visible in trash list
        response_trash = self.client.get('/api/contacts/trash')
        self.assertEqual(response_trash.status_code, 200)
        trash_data = json.loads(response_trash.data)
        self.assertEqual(trash_data['total_count'], 1)
        self.assertEqual(trash_data['contacts'][0]['name'], "Soft Delete Target")
        
        # Restore
        response_restore = self.client.post(f'/api/contacts/{c_id}/restore')
        self.assertEqual(response_restore.status_code, 200)
        
        # Verify restored to main list
        response_list2 = self.client.get('/api/contacts')
        self.assertEqual(response_list2.status_code, 200)
        self.assertEqual(json.loads(response_list2.data)['total_count'], 1)

    def test_permanent_delete_and_file_cleanup(self):
        # Create contact and upload avatar
        contact_json = self.client.post('/api/contacts', json={"name": "Perm Target"}).get_json()
        c_id = contact_json['id']
        
        img_io = io.BytesIO()
        img = Image.new('RGB', (10, 10), color='red')
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        self.client.post(
            f'/api/contacts/{c_id}/avatar',
            data={'file': (img_io, "valid.png")},
            content_type='multipart/form-data'
        )
        
        contact_updated = self.client.get(f'/api/contacts/{c_id}').get_json()
        avatar_url = contact_updated['avatar_url']
        
        from app import AVATAR_UPLOAD_FOLDER
        filename = avatar_url.split('/')[-1]
        saved_path = os.path.join(AVATAR_UPLOAD_FOLDER, filename)
        self.assertTrue(os.path.exists(saved_path))
        
        # Soft delete first
        self.client.delete(f'/api/contacts/{c_id}')
        
        # Permanent delete
        response_perm = self.client.delete(f'/api/contacts/{c_id}/permanent')
        self.assertEqual(response_perm.status_code, 200)
        
        # Check database is clean
        with app.app_context():
            self.assertIsNone(db.session.get(Contact, c_id))
            
        # Check disk file is cleaned up
        self.assertFalse(os.path.exists(saved_path))

    def test_auto_purge_30_days(self):
        # Create contact
        contact_json = self.client.post('/api/contacts', json={"name": "Old Trash"}).get_json()
        c_id = contact_json['id']
        
        # Soft delete it
        self.client.delete(f'/api/contacts/{c_id}')
        
        # Manipulate deleted_at timestamp in database to be 31 days ago
        with app.app_context():
            from datetime import timedelta
            contact_db = db.session.get(Contact, c_id)
            contact_db.deleted_at = datetime.now(timezone.utc) - timedelta(days=31)
            db.session.commit()
            
        # Trigger auto purge function
        from app import purge_old_deleted_contacts
        purge_old_deleted_contacts()
        
        # Verify contact is completely deleted
        with app.app_context():
            self.assertIsNone(db.session.get(Contact, c_id))

    def test_vcard_export(self):
        # Create contact
        contact_json = self.client.post(
            '/api/contacts',
            json={
                "name": "vCard User",
                "phone": "+1 (555) 999-8888",
                "email": "vcard@example.com",
                "address": "123 Street; Apt 4",
                "birthday": "1990-05-15"
            }
        ).get_json()
        c_id = contact_json['id']
        
        # Test 1: Single export
        response = self.client.get(f'/api/contacts/{c_id}/vcard')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'text/vcard')
        vcard_data = response.data.decode('utf-8')
        
        self.assertIn('BEGIN:VCARD', vcard_data)
        self.assertIn('FN:vCard User', vcard_data)
        self.assertIn('TEL;TYPE=CELL:+1 (555) 999-8888', vcard_data)
        self.assertIn('EMAIL;TYPE=INTERNET:vcard@example.com', vcard_data)
        self.assertIn('ADR;TYPE=HOME:;;123 Street\\; Apt 4;;;;', vcard_data)
        self.assertIn('BDAY:1990-05-15', vcard_data)
        self.assertIn('END:VCARD', vcard_data)
        
        # Test 2: Bulk export
        response_bulk = self.client.get(f'/api/contacts/vcard/export?ids={c_id}')
        self.assertEqual(response_bulk.status_code, 200)
        self.assertEqual(response_bulk.headers['Content-Type'], 'text/vcard')
        self.assertIn('FN:vCard User', response_bulk.data.decode('utf-8'))

if __name__ == '__main__':
    unittest.main()
