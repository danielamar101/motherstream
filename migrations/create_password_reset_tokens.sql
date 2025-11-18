-- Migration: Add password_reset_tokens table
-- Date: 2025-11-18
-- Description: Adds support for password reset functionality

-- Create the password_reset_tokens table
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    
    -- Foreign key constraint
    CONSTRAINT fk_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_password_reset_token 
ON password_reset_tokens(token);

CREATE INDEX IF NOT EXISTS idx_password_reset_user_id 
ON password_reset_tokens(user_id);

CREATE INDEX IF NOT EXISTS idx_password_reset_expires_at 
ON password_reset_tokens(expires_at);

-- Add a comment to the table
COMMENT ON TABLE password_reset_tokens IS 'Stores password reset tokens for user password recovery';

-- Verify table creation
SELECT 
    'password_reset_tokens table created successfully' AS status,
    COUNT(*) as initial_count 
FROM password_reset_tokens;

