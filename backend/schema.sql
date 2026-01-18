-- People Search Database Schema
-- Run this to set up the database in production:
--   psql -d people_search -f schema.sql

-- Drop tables if they exist (for clean rebuild)
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS profiles CASCADE;

-- Profiles table
CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    role VARCHAR(100) NOT NULL,
    location VARCHAR(100) NOT NULL,
    bio VARCHAR(500) DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Reviews table
CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    author VARCHAR(100) NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment VARCHAR(1000) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_profiles_name ON profiles USING gin(to_tsvector('english', name));
CREATE INDEX idx_profiles_role ON profiles USING gin(to_tsvector('english', role));
CREATE INDEX idx_profiles_location ON profiles USING gin(to_tsvector('english', location));
CREATE INDEX idx_reviews_profile_id ON reviews(profile_id);

-- Seed data (optional, remove in production)
INSERT INTO profiles (name, role, location, bio) VALUES
    ('Alice Monroe', 'Product Designer', 'New York, NY', 'Passionate about user-centered design.'),
    ('Bob Chen', 'Software Engineer', 'San Francisco, CA', 'Full-stack developer with 10 years experience.'),
    ('Carlos Ruiz', 'Data Scientist', 'Austin, TX', 'ML enthusiast and Python advocate.'),
    ('Denise Patel', 'Marketing Lead', 'Seattle, WA', 'Growth marketing specialist.'),
    ('Ethan Li', 'CTO', 'Boston, MA', 'Building scalable systems since 2010.'),
    ('Fiona Gomez', 'UX Researcher', 'Denver, CO', 'Qualitative research expert.'),
    ('Grace Park', 'Designer', 'Brooklyn, NY', 'Visual design and branding.'),
    ('Hassan Ali', 'Frontend Engineer', 'Chicago, IL', 'React and TypeScript specialist.');
