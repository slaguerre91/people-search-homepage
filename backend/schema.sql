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
    company VARCHAR(100) NOT NULL,
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
CREATE INDEX idx_profiles_company ON profiles USING gin(to_tsvector('english', company));
CREATE INDEX idx_profiles_role ON profiles USING gin(to_tsvector('english', role));
CREATE INDEX idx_profiles_location ON profiles USING gin(to_tsvector('english', location));
CREATE INDEX idx_reviews_profile_id ON reviews(profile_id);

-- Seed data with many people and companies
INSERT INTO profiles (name, company, role, location, bio) VALUES
    -- Tech Giants
    ('John Smith', 'Oracle', 'Senior Software Engineer', 'Austin, TX', 'Database specialist with 15 years experience.'),
    ('Sarah Johnson', 'Oracle', 'Product Manager', 'Redwood City, CA', 'Leading cloud infrastructure products.'),
    ('Michael Chen', 'Oracle', 'Data Architect', 'Seattle, WA', 'Designing enterprise data solutions.'),
    ('Emily Davis', 'Google', 'Staff Engineer', 'Mountain View, CA', 'Working on search algorithms.'),
    ('David Kim', 'Google', 'UX Designer', 'New York, NY', 'Material Design contributor.'),
    ('Jessica Wang', 'Google', 'Engineering Manager', 'San Francisco, CA', 'Leading Google Cloud teams.'),
    ('Robert Brown', 'Microsoft', 'Principal Engineer', 'Redmond, WA', 'Azure infrastructure expert.'),
    ('Amanda Miller', 'Microsoft', 'Program Manager', 'Seattle, WA', 'Microsoft 365 product development.'),
    ('James Wilson', 'Microsoft', 'Senior Developer', 'Austin, TX', 'TypeScript and VS Code contributor.'),
    ('Lisa Anderson', 'Apple', 'iOS Engineer', 'Cupertino, CA', 'Building next-gen mobile experiences.'),
    ('Christopher Lee', 'Apple', 'Hardware Engineer', 'Cupertino, CA', 'M-series chip development.'),
    ('Jennifer Taylor', 'Apple', 'Design Lead', 'San Francisco, CA', 'Human interface guidelines author.'),
    ('Daniel Martinez', 'Amazon', 'Solutions Architect', 'Seattle, WA', 'AWS enterprise solutions.'),
    ('Michelle Garcia', 'Amazon', 'Senior SDE', 'New York, NY', 'Prime Video backend systems.'),
    ('Kevin Robinson', 'Amazon', 'Data Scientist', 'Boston, MA', 'ML-powered recommendations.'),
    ('Rachel Thompson', 'Meta', 'Research Scientist', 'Menlo Park, CA', 'AI and machine learning research.'),
    ('Brian White', 'Meta', 'Production Engineer', 'New York, NY', 'Infrastructure reliability.'),
    ('Nicole Harris', 'Meta', 'Product Designer', 'Seattle, WA', 'Instagram design systems.'),
    
    -- Enterprise Software
    ('Steven Clark', 'Salesforce', 'Technical Architect', 'San Francisco, CA', 'CRM platform specialist.'),
    ('Karen Lewis', 'Salesforce', 'Success Manager', 'Chicago, IL', 'Enterprise customer success.'),
    ('Jason Young', 'SAP', 'Consultant', 'New York, NY', 'ERP implementation expert.'),
    ('Laura Hall', 'SAP', 'Developer', 'Philadelphia, PA', 'ABAP and Fiori development.'),
    ('Mark Allen', 'IBM', 'Distinguished Engineer', 'Austin, TX', 'Quantum computing research.'),
    ('Sandra King', 'IBM', 'Data Engineer', 'Raleigh, NC', 'Watson AI platform.'),
    ('Paul Wright', 'Workday', 'Engineering Lead', 'Pleasanton, CA', 'HR tech innovation.'),
    ('Angela Scott', 'ServiceNow', 'Platform Architect', 'San Diego, CA', 'Workflow automation.'),
    
    -- Startups & Scale-ups
    ('Thomas Green', 'Stripe', 'Backend Engineer', 'San Francisco, CA', 'Payments infrastructure.'),
    ('Maria Adams', 'Stripe', 'Frontend Developer', 'New York, NY', 'Dashboard and developer tools.'),
    ('William Baker', 'Airbnb', 'Staff Engineer', 'San Francisco, CA', 'Search and discovery.'),
    ('Elizabeth Nelson', 'Airbnb', 'Data Scientist', 'Seattle, WA', 'Pricing algorithms.'),
    ('Ryan Carter', 'Uber', 'Senior Engineer', 'San Francisco, CA', 'Real-time systems.'),
    ('Samantha Mitchell', 'Uber', 'Product Manager', 'New York, NY', 'Uber Eats growth.'),
    ('Andrew Perez', 'Lyft', 'Mobile Engineer', 'San Francisco, CA', 'iOS app development.'),
    ('Stephanie Roberts', 'DoorDash', 'Engineering Manager', 'San Francisco, CA', 'Logistics platform.'),
    ('Joshua Turner', 'Coinbase', 'Security Engineer', 'San Francisco, CA', 'Crypto security.'),
    ('Ashley Phillips', 'Robinhood', 'Backend Developer', 'Menlo Park, CA', 'Trading systems.'),
    
    -- Finance & Consulting
    ('Brandon Campbell', 'Goldman Sachs', 'Quant Developer', 'New York, NY', 'Algorithmic trading.'),
    ('Megan Parker', 'Goldman Sachs', 'VP Engineering', 'New York, NY', 'Technology leadership.'),
    ('Justin Evans', 'JPMorgan Chase', 'Software Engineer', 'New York, NY', 'Banking platforms.'),
    ('Heather Edwards', 'Morgan Stanley', 'Data Analyst', 'New York, NY', 'Financial analytics.'),
    ('Kyle Collins', 'McKinsey', 'Digital Consultant', 'Chicago, IL', 'Digital transformation.'),
    ('Amber Stewart', 'Deloitte', 'Tech Consultant', 'Atlanta, GA', 'Cloud strategy.'),
    ('Jeremy Sanchez', 'Accenture', 'Managing Director', 'San Francisco, CA', 'Technology consulting.'),
    
    -- Healthcare & Biotech
    ('Christina Morris', 'Pfizer', 'Research Scientist', 'Cambridge, MA', 'Drug discovery.'),
    ('Derek Rogers', 'Johnson & Johnson', 'Software Engineer', 'New Brunswick, NJ', 'Healthcare IT systems.'),
    ('Vanessa Reed', 'Epic Systems', 'Implementation Lead', 'Madison, WI', 'EHR deployment.'),
    ('Nathan Cook', 'Moderna', 'Bioinformatics Engineer', 'Cambridge, MA', 'mRNA research.'),
    
    -- Retail & E-commerce
    ('Tiffany Morgan', 'Walmart', 'Tech Lead', 'Bentonville, AR', 'E-commerce platform.'),
    ('Sean Bell', 'Target', 'Senior Developer', 'Minneapolis, MN', 'Digital experiences.'),
    ('Brittany Murphy', 'Shopify', 'Staff Engineer', 'Ottawa, Canada', 'Merchant tools.'),
    ('Eric Bailey', 'Etsy', 'Backend Engineer', 'Brooklyn, NY', 'Marketplace systems.'),
    
    -- Additional diverse entries
    ('John Williams', 'Netflix', 'Senior Engineer', 'Los Gatos, CA', 'Streaming infrastructure.'),
    ('John Davis', 'Spotify', 'ML Engineer', 'New York, NY', 'Recommendation systems.'),
    ('John Miller', 'Tesla', 'Autopilot Engineer', 'Palo Alto, CA', 'Self-driving technology.'),
    ('John Anderson', 'SpaceX', 'Software Engineer', 'Hawthorne, CA', 'Flight software.'),
    ('Sarah Smith', 'Adobe', 'Principal Designer', 'San Jose, CA', 'Creative Cloud UX.'),
    ('Sarah Williams', 'Figma', 'Design Engineer', 'San Francisco, CA', 'Design tools.'),
    ('Michael Johnson', 'Slack', 'Platform Engineer', 'San Francisco, CA', 'Enterprise messaging.'),
    ('Michael Brown', 'Zoom', 'Video Engineer', 'San Jose, CA', 'Real-time video.'),
    ('Emily Wilson', 'Pinterest', 'ML Scientist', 'San Francisco, CA', 'Visual search.'),
    ('Emily Chen', 'Twitter', 'Backend Engineer', 'San Francisco, CA', 'Timeline systems.');

