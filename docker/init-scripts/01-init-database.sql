-- Initialize GoMuseum Database
-- This script sets up the basic database structure

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enum types
CREATE TYPE subscription_type_enum AS ENUM ('free', 'premium', 'annual');
CREATE TYPE sync_status_enum AS ENUM ('synced', 'pending', 'failed');

-- Indexes will be created automatically by SQLAlchemy
-- This is just for reference of what will be created

-- Performance indexes that might be useful
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email ON users(email);
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artworks_search ON artworks USING gin(to_tsvector('english', name || ' ' || artist));
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_recognition_cache_expires ON recognition_cache(expires_at) WHERE expires_at IS NOT NULL;

-- Insert some sample data for development
-- INSERT INTO museums (id, name, city, country, metadata) VALUES 
-- (uuid_generate_v4(), '卢浮宫', '巴黎', '法国', '{"description": "世界最大的艺术博物馆"}'),
-- (uuid_generate_v4(), '大英博物馆', '伦敦', '英国', '{"description": "世界上历史最悠久的公共博物馆之一"}'),
-- (uuid_generate_v4(), '故宫博物院', '北京', '中国', '{"description": "中国明清两代的皇家宫殿"}');

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE gomuseum TO gomuseum;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gomuseum;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gomuseum;

-- Set up connection limits
ALTER ROLE gomuseum CONNECTION LIMIT 20;

COMMIT;