-- Migration 034: Add proximity tracking to round_correlations
-- Tracks whether proximity engagement data has arrived for each round
-- Part of making proximity a first-class citizen in the correlation system

ALTER TABLE round_correlations ADD COLUMN IF NOT EXISTS has_r1_proximity BOOLEAN DEFAULT FALSE;
ALTER TABLE round_correlations ADD COLUMN IF NOT EXISTS has_r2_proximity BOOLEAN DEFAULT FALSE;
