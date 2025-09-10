#!/usr/bin/env python3
"""
Quick verification test for GoMuseum API
Tests core functionality after fixes
"""

import sys
import os
import time

# Ensure we're in the right directory
if not os.path.exists('gomuseum_api'):
    print("Error: gomuseum_api directory not found")
    sys.exit(1)

os.chdir('gomuseum_api')
sys.path.insert(0, '.')

def test_core_functionality():
    """Test core functionality"""
    print("🚀 Quick Verification Test for GoMuseum API")
    print("=" * 50)
    
    # Test 1: Core imports
    try:
        from app.core.config import settings
        from app.core.database import get_db, engine
        from app.core.auth import create_access_token, verify_password, get_password_hash
        from app.models.user import User
        print("✅ Core imports successful")
    except Exception as e:
        print(f"❌ Core imports failed: {e}")
        return False
    
    # Test 2: Database connection
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone() is not None
        print("✅ Database connection working")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    # Test 3: Authentication
    try:
        # Test password hashing
        password = "testpassword123"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed)
        
        # Test token creation
        token = create_access_token({"sub": "test", "email": "test@example.com"})
        assert isinstance(token, str) and len(token) > 50
        print("✅ Authentication system working")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False
    
    # Test 4: Database operations
    try:
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            # Create test user
            test_user = User(
                email="quicktest@example.com",
                username="quicktest",
                password_hash=get_password_hash("testpass123"),
                is_active=True
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            
            # Verify user
            retrieved = db.query(User).filter(User.email == "quicktest@example.com").first()
            assert retrieved is not None
            assert retrieved.email == "quicktest@example.com"
            
            # Cleanup
            db.delete(retrieved)
            db.commit()
            print("✅ Database CRUD operations working")
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Database operations failed: {e}")
        return False
    
    # Test 5: FastAPI app creation
    try:
        from app.main import create_app
        app = create_app()
        assert app is not None
        print("✅ FastAPI app creation working")
    except Exception as e:
        print(f"❌ App creation failed: {e}")
        return False
    
    # Test 6: API endpoint test
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        print("✅ API endpoints working")
    except Exception as e:
        print(f"❌ API endpoints failed: {e}")
        return False
    
    print("\n🎉 ALL CORE TESTS PASSED!")
    print("✅ GoMuseum API is ready for deployment")
    return True

if __name__ == "__main__":
    success = test_core_functionality()
    sys.exit(0 if success else 1)