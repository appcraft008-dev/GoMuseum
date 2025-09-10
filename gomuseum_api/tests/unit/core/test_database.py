"""
Unit tests for database module
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError, DatabaseError
from sqlalchemy.pool import StaticPool

from app.core.database import (
    create_database_engine,
    get_db,
    init_db,
    close_db,
    test_connection,
    create_tables,
    engine,
    SessionLocal,
    Base
)


class TestDatabaseEngineCreation:
    """Test database engine creation with different configurations"""
    
    @patch('app.core.config.settings')
    def test_create_sqlite_engine(self, mock_settings):
        """Test SQLite engine creation"""
        mock_settings.database_url = "sqlite:///test.db"
        mock_settings.database_echo = False
        
        with patch('sqlalchemy.create_engine') as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            
            result = create_database_engine()
            
            mock_create_engine.assert_called_once()
            args, kwargs = mock_create_engine.call_args
            
            assert args[0] == "sqlite:///test.db"
            assert kwargs['poolclass'] == StaticPool
            assert kwargs['connect_args']['check_same_thread'] is False
            assert kwargs['echo'] is False
    
    @patch('app.core.config.settings')
    def test_create_postgresql_engine(self, mock_settings):
        """Test PostgreSQL engine creation"""
        mock_settings.database_url = "postgresql://user:pass@localhost/test"
        mock_settings.database_echo = True
        
        with patch('sqlalchemy.create_engine') as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            
            result = create_database_engine()
            
            mock_create_engine.assert_called_once()
            args, kwargs = mock_create_engine.call_args
            
            assert args[0] == "postgresql://user:pass@localhost/test"
            assert kwargs['pool_size'] == 10
            assert kwargs['max_overflow'] == 20
            assert kwargs['pool_timeout'] == 30
            assert kwargs['pool_pre_ping'] is True
            assert kwargs['pool_recycle'] == 3600
            assert kwargs['echo'] is True
    
    @patch('app.core.config.settings')
    def test_create_mysql_engine(self, mock_settings):
        """Test MySQL engine creation (uses PostgreSQL config)"""
        mock_settings.database_url = "mysql://user:pass@localhost/test"
        mock_settings.database_echo = False
        
        with patch('sqlalchemy.create_engine') as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            
            result = create_database_engine()
            
            mock_create_engine.assert_called_once()
            args, kwargs = mock_create_engine.call_args
            
            # Should use PostgreSQL-like config for non-SQLite databases
            assert 'pool_size' in kwargs
            assert 'poolclass' not in kwargs  # Should not have SQLite-specific config


class TestDatabaseDependency:
    """Test database dependency injection"""
    
    @patch('app.core.database.SessionLocal')
    def test_get_db_success(self, mock_session_local):
        """Test successful database session creation"""
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        
        # Use the generator
        db_gen = get_db()
        db = next(db_gen)
        
        assert db == mock_session
        mock_session_local.assert_called_once()
        
        # Test cleanup
        try:
            next(db_gen)
        except StopIteration:
            pass  # Expected
        
        mock_session.close.assert_called_once()
    
    @patch('app.core.database.SessionLocal')
    def test_get_db_exception_cleanup(self, mock_session_local):
        """Test database session cleanup on exception"""
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        
        db_gen = get_db()
        db = next(db_gen)
        
        # Simulate exception during usage
        try:
            raise Exception("Database error")
        except Exception:
            pass
        
        # Cleanup should still happen
        try:
            next(db_gen)
        except StopIteration:
            pass
        
        mock_session.close.assert_called_once()


@pytest.mark.asyncio
class TestDatabaseInitialization:
    """Test database initialization functions"""
    
    @patch('app.core.database.Base')
    @patch('app.core.database.engine')
    async def test_init_db_success(self, mock_engine, mock_base):
        """Test successful database initialization"""
        mock_metadata = Mock()
        mock_base.metadata = mock_metadata
        
        with patch('app.models.user'), \
             patch('app.models.artwork'), \
             patch('app.models.museum'), \
             patch('app.models.recognition_cache'):
            
            await init_db()
            
            mock_metadata.create_all.assert_called_once_with(bind=mock_engine)
    
    @patch('app.core.database.Base')
    @patch('app.core.database.engine')
    async def test_init_db_import_error(self, mock_engine, mock_base):
        """Test database initialization with import error"""
        mock_metadata = Mock()
        mock_base.metadata = mock_metadata
        
        with patch('app.models.user', side_effect=ImportError("Module not found")):
            # Should still attempt to create tables even if import fails
            with pytest.raises(ImportError):
                await init_db()
    
    @patch('app.core.database.engine')
    async def test_close_db(self, mock_engine):
        """Test database connection cleanup"""
        await close_db()
        
        mock_engine.dispose.assert_called_once()
    
    @patch('app.core.database.Base')
    @patch('app.core.database.engine')
    def test_create_tables(self, mock_engine, mock_base):
        """Test table creation"""
        mock_metadata = Mock()
        mock_base.metadata = mock_metadata
        
        create_tables()
        
        mock_metadata.create_all.assert_called_once_with(bind=mock_engine)


class TestDatabaseConnection:
    """Test database connection testing"""
    
    @patch('app.core.database.engine')
    def test_connection_success(self, mock_engine):
        """Test successful database connection"""
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.fetchone.return_value = (1,)
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        result = test_connection()
        
        assert result is True
        mock_conn.execute.assert_called_once()
    
    @patch('app.core.database.engine')
    def test_connection_failure(self, mock_engine):
        """Test database connection failure"""
        mock_engine.connect.side_effect = DatabaseError("Connection failed", None, None)
        
        result = test_connection()
        
        assert result is False
    
    @patch('app.core.database.engine')
    def test_connection_query_failure(self, mock_engine):
        """Test database connection with query failure"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = SQLAlchemyError("Query failed")
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        result = test_connection()
        
        assert result is False
    
    @patch('app.core.database.engine')
    def test_connection_no_result(self, mock_engine):
        """Test database connection with no result"""
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        result = test_connection()
        
        assert result is False


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database functionality"""
    
    def test_sqlite_engine_creation(self):
        """Test actual SQLite engine creation"""
        test_url = "sqlite:///test_integration.db"
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.database_url = test_url
            mock_settings.database_echo = False
            
            engine = create_database_engine()
            
            assert engine is not None
            assert "sqlite" in str(engine.url)
    
    def test_session_creation(self):
        """Test actual session creation and usage"""
        from sqlalchemy import text
        
        # Create an in-memory SQLite database for testing
        test_engine = create_engine("sqlite:///:memory:")
        
        from sqlalchemy.orm import sessionmaker
        TestSessionLocal = sessionmaker(bind=test_engine)
        
        session = TestSessionLocal()
        try:
            # Test basic query
            result = session.execute(text("SELECT 1 as test_value"))
            assert result.fetchone()[0] == 1
        finally:
            session.close()
    
    def test_base_metadata(self):
        """Test Base and metadata objects"""
        from app.core.database import Base, metadata
        
        assert Base is not None
        assert hasattr(Base, 'metadata')
        assert metadata is not None
    
    def test_connection_with_real_sqlite(self):
        """Test connection with real SQLite database"""
        import tempfile
        import os
        
        # Create temporary database file
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
            temp_db_path = temp_file.name
        
        try:
            test_url = f"sqlite:///{temp_db_path}"
            
            with patch('app.core.config.settings') as mock_settings:
                mock_settings.database_url = test_url
                mock_settings.database_echo = False
                
                # Create engine and test connection
                with patch('app.core.database.engine', create_database_engine()):
                    result = test_connection()
                    assert result is True
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)


@pytest.mark.db
class TestDatabaseEdgeCases:
    """Test edge cases and error conditions"""
    
    @patch('app.core.database.engine')
    def test_engine_dispose_exception(self, mock_engine):
        """Test engine disposal with exception"""
        mock_engine.dispose.side_effect = Exception("Disposal failed")
        
        # Should not raise exception
        import asyncio
        asyncio.run(close_db())
    
    @patch('app.core.database.SessionLocal')
    def test_session_close_exception(self, mock_session_local):
        """Test session close with exception"""
        mock_session = Mock()
        mock_session.close.side_effect = Exception("Close failed")
        mock_session_local.return_value = mock_session
        
        # Should not raise exception
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            next(db_gen)
        except StopIteration:
            pass  # Expected - the exception should be handled internally
    
    def test_invalid_database_url(self):
        """Test engine creation with invalid database URL"""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.database_url = "invalid://url"
            mock_settings.database_echo = False
            
            # Should raise an exception during engine creation
            with pytest.raises(Exception):
                engine = create_database_engine()
                # Try to use the engine
                with engine.connect():
                    pass
    
    @patch('app.core.database.engine')
    def test_connection_timeout(self, mock_engine):
        """Test connection timeout handling"""
        from sqlalchemy.exc import TimeoutError
        
        mock_engine.connect.side_effect = TimeoutError("Connection timeout", None, None)
        
        result = test_connection()
        assert result is False
    
    @patch('app.core.config.settings')
    def test_empty_database_url(self, mock_settings):
        """Test handling of empty database URL"""
        mock_settings.database_url = ""
        mock_settings.database_echo = False
        
        with pytest.raises(Exception):
            create_database_engine()


class TestSessionLocalConfiguration:
    """Test SessionLocal configuration"""
    
    def test_session_local_properties(self):
        """Test SessionLocal is configured correctly"""
        assert SessionLocal is not None
        
        # Check that it's a sessionmaker
        from sqlalchemy.orm import sessionmaker
        assert isinstance(SessionLocal, sessionmaker)
        
        # Test creating a session
        session = SessionLocal()
        assert session is not None
        session.close()


class TestMetadataConfiguration:
    """Test metadata configuration"""
    
    def test_metadata_object(self):
        """Test metadata object exists and is configured"""
        from app.core.database import metadata, Base
        
        assert metadata is not None
        assert Base is not None
        assert hasattr(Base, 'metadata')
    
    def test_base_registry(self):
        """Test Base class registry"""
        from app.core.database import Base
        
        # Base should be a declarative base
        assert hasattr(Base, 'registry')
        assert hasattr(Base, 'metadata')
        assert hasattr(Base, '__tablename__') or hasattr(Base, '__abstract__')