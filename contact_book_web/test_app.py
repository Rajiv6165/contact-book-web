import os
import sys
import unittest
import json
import io

# Ensure the contact_book_web directory is on the path
sys.path.append(os.path.dirname(__file__))

from app import app, db, Contact, User

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
        self.assertIn('name,phone,email,address,notes,favorite,created_at,updated_at', csv_data)
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

if __name__ == '__main__':
    unittest.main()
