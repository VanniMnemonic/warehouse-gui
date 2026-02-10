import os
import shutil
import zipfile
import tempfile
import unittest

class TestBackupMechanism(unittest.TestCase):
    def setUp(self):
        # Create a test environment
        self.test_dir = tempfile.mkdtemp()
        self.base_path = os.path.join(self.test_dir, "app_base")
        os.makedirs(self.base_path)
        
        # Create dummy DB
        self.db_file = os.path.join(self.base_path, "warehouse.db")
        with open(self.db_file, "w") as f:
            f.write("DUMMY DB CONTENT")
            
        # Create dummy Images
        self.images_dir = os.path.join(self.base_path, "images")
        os.makedirs(self.images_dir)
        self.img_file = os.path.join(self.images_dir, "test.png")
        with open(self.img_file, "w") as f:
            f.write("DUMMY IMAGE CONTENT")
            
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_export_logic(self):
        backup_zip = os.path.join(self.test_dir, "backup.zip")
        
        # LOGIC FROM export_db
        with zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add DB
            if os.path.exists(self.db_file):
                zipf.write(self.db_file, "warehouse.db")
            
            # Add Images
            if os.path.exists(self.images_dir):
                for root, dirs, files in os.walk(self.images_dir):
                    for file in files:
                        abs_path = os.path.join(root, file)
                        rel_path = os.path.relpath(abs_path, self.base_path)
                        zipf.write(abs_path, rel_path)
        
        # VERIFY
        self.assertTrue(os.path.exists(backup_zip))
        with zipfile.ZipFile(backup_zip, 'r') as zipf:
            names = zipf.namelist()
            print(f"Zip contents: {names}")
            self.assertIn("warehouse.db", names)
            self.assertIn(os.path.join("images", "test.png"), names)

    def test_import_logic(self):
        # 1. Prepare Backup
        backup_zip = os.path.join(self.test_dir, "backup.zip")
        with zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(self.db_file, "warehouse.db")
            zipf.write(self.img_file, os.path.join("images", "test.png"))
            
        # 2. Corrupt/Clear Current State
        os.remove(self.db_file)
        shutil.rmtree(self.images_dir)
        self.assertFalse(os.path.exists(self.db_file))
        self.assertFalse(os.path.exists(self.images_dir))
        
        # 3. LOGIC FROM import_db
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(backup_zip, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Check for DB file in extracted root
            extracted_db = os.path.join(temp_dir, "warehouse.db")
            self.assertTrue(os.path.exists(extracted_db))
            
            # Replace DB
            shutil.copy2(extracted_db, self.db_file)
            
            # Replace Images
            extracted_images = os.path.join(temp_dir, "images")
            if os.path.exists(extracted_images):
                # Ensure parent dir exists (app base) - in real app it exists
                # shutil.rmtree(self.images_dir) # It's already gone in this test
                if os.path.exists(self.images_dir):
                    shutil.rmtree(self.images_dir)
                shutil.copytree(extracted_images, self.images_dir)
        
        # 4. VERIFY RESTORATION
        self.assertTrue(os.path.exists(self.db_file))
        with open(self.db_file, "r") as f:
            self.assertEqual(f.read(), "DUMMY DB CONTENT")
            
        self.assertTrue(os.path.exists(self.img_file))
        with open(self.img_file, "r") as f:
            self.assertEqual(f.read(), "DUMMY IMAGE CONTENT")

if __name__ == '__main__':
    unittest.main()
