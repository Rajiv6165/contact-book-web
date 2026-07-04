import os
import sys
import unittest
import json
import io

# Ensure the contact_book_web directory is on the path
sys.path.append(os.path.dirname(__file__))

from app import app, db, Contact

class ContactBookTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        self.client = app.test_client()
        
        with app.app_context():
            db.create_all()

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
        import app as app_module
        app_module.BASIC_AUTH_USERNAME = 'testuser'
        app_module.BASIC_AUTH_PASSWORD = 'testpassword'
        
        try:
            response = self.client.get('/health')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['status'], 'healthy')
        finally:
            app_module.BASIC_AUTH_USERNAME = None
            app_module.BASIC_AUTH_PASSWORD = None

    def test_basic_auth_required_when_configured(self):
        import app as app_module
        app_module.BASIC_AUTH_USERNAME = 'testuser'
        app_module.BASIC_AUTH_PASSWORD = 'testpassword'
        
        try:
            # Request without credentials (should return 401)
            response = self.client.get('/api/contacts')
            self.assertEqual(response.status_code, 401)
            self.assertIn('WWW-Authenticate', response.headers)
            
            # Request with incorrect credentials (should return 401)
            import base64
            headers = {
                'Authorization': 'Basic ' + base64.b64encode(b'wrong:credentials').decode('utf-8')
            }
            response = self.client.get('/api/contacts', headers=headers)
            self.assertEqual(response.status_code, 401)
            
            # Request with correct credentials (should return 200)
            headers = {
                'Authorization': 'Basic ' + base64.b64encode(b'testuser:testpassword').decode('utf-8')
            }
            response = self.client.get('/api/contacts', headers=headers)
            self.assertEqual(response.status_code, 200)
        finally:
            app_module.BASIC_AUTH_USERNAME = None
            app_module.BASIC_AUTH_PASSWORD = None

if __name__ == '__main__':
    unittest.main()
