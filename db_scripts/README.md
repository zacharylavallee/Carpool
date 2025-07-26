# Database Scripts

This folder contains essential database management and maintenance scripts for the Carpool Bot.

## Scripts Overview

### `validate_database.py`
**Purpose**: Comprehensive database validation and health check
- Validates database schema matches codebase expectations
- Checks table structures, constraints, and relationships
- Verifies data integrity and business logic compliance
- Generates detailed validation reports
- **Usage**: `python validate_database.py`

### `reset_database.py`
**Purpose**: Clean database reset for development/troubleshooting
- Safely removes all carpool data (trips, cars, memberships, requests)
- Maintains table structure and constraints
- Includes confirmation prompts for safety
- Verifies empty state after reset
- **Usage**: `python reset_database.py`
- **⚠️ WARNING**: This deletes ALL data - use with caution!

### `db_sync_checker.py`
**Purpose**: Schema synchronization analysis
- Analyzes codebase to understand expected database schema
- Compares expected vs actual database structure
- Detects mismatches between code and database
- Identifies missing tables, columns, or constraints
- **Usage**: `python db_sync_checker.py`

### `fix_database_schema.py`
**Purpose**: Database schema migration and fixes
- Applies schema changes to match current codebase
- Handles constraint modifications and data migrations
- Fixes common schema issues and inconsistencies
- Safe migration with rollback capabilities
- **Usage**: `python fix_database_schema.py`

## When to Use These Scripts

### Development
- Use `validate_database.py` regularly to ensure database health
- Use `db_sync_checker.py` when adding new features to verify schema alignment

### Troubleshooting
- Use `validate_database.py` to diagnose database issues
- Use `fix_database_schema.py` to resolve schema mismatches
- Use `reset_database.py` as a last resort for clean slate testing

### Production Deployment
- Run `validate_database.py` before and after deployments
- Use `fix_database_schema.py` for production schema updates
- **Never** use `reset_database.py` in production

## Prerequisites

All scripts require:
- Python 3.x with required dependencies
- Database connection configured via `DATABASE_URL` environment variable
- Proper database permissions for schema modifications

## Safety Notes

- Always backup your database before running migration scripts
- Test scripts in development environment first
- The `reset_database.py` script is destructive - use with extreme caution
- Validate changes with `validate_database.py` after running any migration
