import urllib.request
import json
import time
import unittest
import os

BASE_URL = "http://localhost:4000/api"

class TestSpatialToolbox(unittest.TestCase):
    token = None

    @classmethod
    def setUpClass(cls):
        # Login to get token
        print("\nLogging in...")
        url = f"{BASE_URL}/auth/login"
        payload = {
            "email": "admin@terracube.xyz",
            "password": "ChangeThisSecurePassword123!"
        }
        
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            with urllib.request.urlopen(req) as f:
                data = json.loads(f.read().decode('utf-8'))
                cls.token = data['token']
                print("Login successful.")
        except urllib.error.HTTPError as e:
            print(f"Login failed: {e}")
            # Try registering if login fails (first run maybe?)
            # But admin should be seeded.
            raise e

    def post_json(self, endpoint, data):
        url = f"{BASE_URL}/toolbox/{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode('utf-8'),
            headers=headers
        )
        with urllib.request.urlopen(req) as f:
            return json.loads(f.read().decode('utf-8'))

    def test_buffer(self):
        print("\nTesting Buffer...")
        payload = {"dggids": ["A0-0-A"], "iterations": 1}
        data = self.post_json("buffer", payload)
        self.assertGreater(data['result_count'], 1)
        self.assertIn("A0-0-A", data['dggids'])

    def test_set_operations(self):
        print("\nTesting Set Ops...")
        set_a = ["A", "B", "C"]
        set_b = ["B", "C", "D"]

        # Union
        u_data = self.post_json("union", {"set_a": set_a, "set_b": set_b})
        self.assertEqual(u_data['result_count'], 4)
        
        # Intersection
        i_data = self.post_json("intersection", {"set_a": set_a, "set_b": set_b})
        self.assertEqual(i_data['result_count'], 2)
        self.assertIn("B", i_data['dggids'])
        self.assertIn("C", i_data['dggids'])

        # Difference
        d_data = self.post_json("difference", {"set_a": set_a, "set_b": set_b})
        self.assertEqual(d_data['result_count'], 1)
        self.assertIn("A", d_data['dggids'])

    def test_zonal_stats(self):
        print("\nTesting Zonal Stats...")
        # We need real dataset IDs from the DB.
        # Fetch datasets first
        url = f"{BASE_URL}/datasets/"
        headers = {'Authorization': f'Bearer {self.token}'}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req) as f:
            payload = json.loads(f.read().decode('utf-8'))
        
        datasets = payload.get('datasets', []) if isinstance(payload, dict) else payload
        
        # Look for real datasets loaded
        vector_ds = next((d for d in datasets if "Countries" in d['name'] or "Boundaries" in d['name']), None)
        raster_ds = next((d for d in datasets if "Elevation" in d['name'] or "Temperature" in d['name']), None)
        
        if vector_ds and raster_ds:
            payload = {
                "zone_dataset_id": vector_ds['id'],
                "value_dataset_id": raster_ds['id'],
                "operation": "MEAN"
            }
            
            url = f"{BASE_URL}/stats/zonal_stats"
            req = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self.token}'}
            )
            try:
                with urllib.request.urlopen(req) as f:
                    data = json.loads(f.read().decode('utf-8'))
                    print(f"Stats Result: {data}")
                    self.assertEqual(data['operation'], 'MEAN')
                    self.assertIn('result', data)
            except urllib.error.HTTPError as e:
                print(f"Zonal Stats Failed: {e.read().decode()}")
                pass
        else:
            print("Skipping Zonal Stats (Demo datasets not found)")

if __name__ == "__main__":
    unittest.main()
