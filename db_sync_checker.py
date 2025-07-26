#!/usr/bin/env python3
"""
Database Sync Checker
Analyzes codebase to understand expected database schema and compares against actual database
Detects mismatches between available commands/features and database structure
"""

import os
import ast
import re
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import json
from datetime import datetime
from pathlib import Path

# Load environment variables
load_dotenv()

class CodebaseAnalyzer:
    """Analyzes the codebase to understand expected database schema"""
    
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.expected_schema = {
            "tables": {},
            "relationships": [],
            "commands": [],
            "database_operations": []
        }
    
    def analyze_codebase(self):
        """Analyze all Python files to understand database expectations"""
        print("🔍 Analyzing codebase for database expectations...")
        
        # Find all Python files
        python_files = list(self.project_root.glob("**/*.py"))
        
        for file_path in python_files:
            if file_path.name.startswith('.') or 'venv' in str(file_path) or '__pycache__' in str(file_path):
                continue
                
            try:
                self._analyze_file(file_path)
            except Exception as e:
                print(f"   ⚠️  Warning: Could not analyze {file_path}: {e}")
        
        self._infer_schema_from_operations()
        return self.expected_schema
    
    def _analyze_file(self, file_path):
        """Analyze a single Python file"""
        # Skip database management scripts to avoid false positives
        filename = file_path.name.lower()
        if any(skip_name in filename for skip_name in [
            'validate_database', 'fix_database', 'db_sync_checker', 
            'migration', 'schema', 'backup', 'restore'
        ]):
            return
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse AST for detailed analysis
        try:
            tree = ast.parse(content)
            self._analyze_ast(tree, file_path)
        except SyntaxError:
            pass  # Skip files with syntax errors
        
        # Look for SQL operations using regex
        self._find_sql_operations(content, file_path)
        
        # Look for Discord commands
        self._find_discord_commands(content, file_path)
    
    def _analyze_ast(self, tree, file_path):
        """Analyze AST for database operations"""
        for node in ast.walk(tree):
            # Look for function calls that might be database operations
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    method_name = node.func.attr
                    if method_name in ['execute', 'fetchone', 'fetchall', 'commit']:
                        # This is likely a database operation
                        if node.args and isinstance(node.args[0], ast.Constant):
                            sql = node.args[0].value
                            if isinstance(sql, str):
                                self._parse_sql_operation(sql, file_path)
    
    def _find_sql_operations(self, content, file_path):
        """Find SQL operations using more precise patterns"""
        # Look for SQL operations in execute() calls or triple-quoted strings
        # More precise patterns that look for actual SQL context
        
        # Find execute() calls with SQL
        execute_pattern = r'execute\s*\(\s*["\'\']{1,3}([^"\'\']*(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|SELECT.*?FROM|CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE)[^"\'\']*)["\'\']{1,3}'
        
        matches = re.finditer(execute_pattern, content, re.IGNORECASE | re.DOTALL)
        for match in matches:
            sql_content = match.group(1)
            self._parse_sql_content(sql_content, file_path)
        
        # Also look for multi-line SQL strings (triple quotes)
        multiline_sql_pattern = r'["\'\']{3}([^"\'\']*(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|SELECT.*?FROM|CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE)[^"\'\']*)["\'\']{3}'
        
        matches = re.finditer(multiline_sql_pattern, content, re.IGNORECASE | re.DOTALL)
        for match in matches:
            sql_content = match.group(1)
            self._parse_sql_content(sql_content, file_path)
    
    def _parse_sql_content(self, sql_content, file_path):
        """Parse SQL content to extract table operations"""
        # Skip if this looks like a system query (contains system table references)
        if any(sys_ref in sql_content.lower() for sys_ref in [
            'information_schema', 'pg_sequences', 'pg_catalog', 'pg_class'
        ]):
            return
        
        # More precise table extraction from actual SQL
        sql_patterns = [
            (r'INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)', 'INSERT'),
            (r'UPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)', 'UPDATE'),
            (r'DELETE\s+FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', 'DELETE'),
            (r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', 'SELECT'),
            (r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)', 'CREATE'),
            (r'ALTER\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)', 'ALTER'),
            (r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)', 'DROP')
        ]
        
        for pattern, operation in sql_patterns:
            matches = re.finditer(pattern, sql_content, re.IGNORECASE)
            for match in matches:
                table_name = match.group(1).lower()
                
                # Filter out obvious non-table names
                if self._is_valid_table_name(table_name):
                    self.expected_schema["database_operations"].append({
                        "file": str(file_path.relative_to(self.project_root)),
                        "table": table_name,
                        "operation": operation,
                        "sql_snippet": sql_content[:100].replace('\n', ' ')
                    })
    
    def _is_valid_table_name(self, name):
        """Check if a name looks like a valid table name"""
        # Filter out common false positives and system tables
        invalid_names = {
            # PostgreSQL system schemas and tables
            'information_schema', 'pg_sequences', 'pg_catalog', 'pg_class',
            'pg_namespace', 'pg_attribute', 'pg_constraint', 'pg_index',
            'pg_stat_user_tables', 'pg_tables', 'pg_views', 'pg_indexes',
            
            # SQL keywords and common words
            'current_timestamp', 'not', 'null', 'true', 'false',
            'and', 'or', 'where', 'order', 'by', 'group', 'having',
            'limit', 'offset', 'distinct', 'all', 'any', 'some',
            'exists', 'in', 'like', 'between', 'is', 'as', 'on',
            'join', 'inner', 'outer', 'left', 'right', 'full',
            'union', 'intersect', 'except', 'case', 'when', 'then',
            'else', 'end', 'if', 'else', 'elsif', 'while', 'for',
            'do', 'begin', 'commit', 'rollback', 'transaction',
            
            # Common English words that might appear in comments
            'it', 'your', 'their', 'seat', 'statements', 'failed',
            'sequence', 'the', 'these', 'carid', 'a', 'an', 'to',
            'from', 'with', 'without', 'into', 'onto', 'upon', 'this',
            'that', 'which', 'what', 'who', 'when', 'where', 'why',
            'how', 'can', 'will', 'would', 'should', 'could', 'may',
            'might', 'must', 'shall', 'have', 'has', 'had', 'been',
            'being', 'are', 'was', 'were', 'am', 'is', 'be'
        }
        
        # Must be a valid identifier and not in the invalid list
        # Also exclude anything that starts with pg_ (PostgreSQL system objects)
        return (name.isidentifier() and 
                len(name) > 1 and 
                name.lower() not in invalid_names and
                not name.lower().startswith('pg_') and
                not name.isdigit())
    
    def _parse_sql_operation(self, sql, file_path):
        """Parse individual SQL operations"""
        sql_upper = sql.upper().strip()
        
        # Extract table names from common operations
        table_patterns = [
            (r'INSERT\s+INTO\s+(\w+)', 'INSERT'),
            (r'UPDATE\s+(\w+)', 'UPDATE'),
            (r'DELETE\s+FROM\s+(\w+)', 'DELETE'),
            (r'SELECT.*FROM\s+(\w+)', 'SELECT'),
            (r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)', 'CREATE'),
            (r'ALTER\s+TABLE\s+(\w+)', 'ALTER'),
            (r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(\w+)', 'DROP')
        ]
        
        for pattern, operation in table_patterns:
            match = re.search(pattern, sql_upper)
            if match:
                table_name = match.group(1).lower()
                
                self.expected_schema["database_operations"].append({
                    "file": str(file_path.relative_to(self.project_root)),
                    "table": table_name,
                    "operation": operation,
                    "sql_snippet": sql[:100]
                })
                
                # If it's a CREATE TABLE, try to parse columns
                if operation == 'CREATE':
                    self._parse_create_table(sql, table_name)
                
                break
    
    def _parse_create_table(self, sql, table_name):
        """Parse CREATE TABLE statements to understand expected schema"""
        # Basic column extraction (this could be enhanced)
        column_pattern = r'(\w+)\s+(TEXT|INTEGER|TIMESTAMP|BOOLEAN|SERIAL)(?:\s+(NOT\s+NULL|PRIMARY\s+KEY|UNIQUE))?'
        matches = re.findall(column_pattern, sql, re.IGNORECASE)
        
        if table_name not in self.expected_schema["tables"]:
            self.expected_schema["tables"][table_name] = {"columns": [], "constraints": []}
        
        for match in matches:
            column_name, data_type, constraint = match
            self.expected_schema["tables"][table_name]["columns"].append({
                "name": column_name.lower(),
                "type": data_type.upper(),
                "constraint": constraint.upper() if constraint else None
            })
    
    def _find_discord_commands(self, content, file_path):
        """Find Discord bot commands more precisely"""
        commands_found = set()  # Avoid duplicates
        
        # Look for @bot.command() or @commands.command() decorators
        decorator_patterns = [
            r'@(?:bot|commands)\.command\(\s*name\s*=\s*["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']',
            r'@(?:bot|commands)\.command\(\s*["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']',
            r'@(?:bot|commands)\.command\(\s*\)\s*\n\s*async\s+def\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        ]
        
        for pattern in decorator_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            for match in matches:
                command_name = match.group(1)
                if self._is_valid_command_name(command_name):
                    commands_found.add(command_name)
        
        # Look for async functions that take ctx as first parameter (likely commands)
        ctx_function_pattern = r'async\s+def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*ctx\s*[,)]'
        matches = re.finditer(ctx_function_pattern, content, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            command_name = match.group(1)
            if self._is_valid_command_name(command_name):
                # Only add if it's not already found and looks like a command
                if command_name not in commands_found:
                    # Check if there's a decorator above this function
                    func_start = match.start()
                    lines_before = content[:func_start].split('\n')[-5:]  # Check 5 lines before
                    has_decorator = any('@' in line and ('command' in line or 'bot.' in line) for line in lines_before)
                    if has_decorator:
                        commands_found.add(command_name)
        
        # Add all found commands to the schema
        for command_name in commands_found:
            self.expected_schema["commands"].append({
                "name": command_name,
                "file": str(file_path.relative_to(self.project_root))
            })
    
    def _is_valid_command_name(self, name):
        """Check if a name looks like a valid Discord command"""
        # Filter out common non-command function names
        invalid_command_names = {
            '__init__', 'setup', 'teardown', 'on_ready', 'on_message',
            'on_error', 'on_command_error', 'main', 'run', 'start',
            'stop', 'close', 'connect', 'disconnect', 'login', 'logout',
            'get_connection', 'execute', 'fetchone', 'fetchall', 'commit',
            'rollback', 'cursor', 'analyze_codebase', 'check_sync'
        }
        
        return (name.isidentifier() and 
                len(name) > 1 and 
                name.lower() not in invalid_command_names and
                not name.startswith('_'))
    
    def _infer_schema_from_operations(self):
        """Infer expected schema from database operations found in code"""
        # Group operations by table
        table_operations = {}
        for op in self.expected_schema["database_operations"]:
            table = op["table"]
            if table not in table_operations:
                table_operations[table] = []
            table_operations[table].append(op)
        
        # For each table, infer what columns/features are expected
        for table_name, operations in table_operations.items():
            if table_name not in self.expected_schema["tables"]:
                self.expected_schema["tables"][table_name] = {
                    "columns": [],
                    "constraints": [],
                    "inferred_from_operations": True
                }
            
            # Look for column references in SQL operations only
            # Be more conservative about column inference
            for op in operations:
                sql_snippet = op["sql_snippet"].lower()
                
                # Only infer columns from INSERT/UPDATE/SELECT operations
                if op["operation"] in ["INSERT", "UPDATE", "SELECT"]:
                    # Look for explicit column patterns like "column_name =" or "(column_name,"
                    if re.search(r'\bchannels?_id\s*[=,)]', sql_snippet):
                        self._add_inferred_column(table_name, "channel_id", "TEXT")
                    if re.search(r'\busers?_id\s*[=,)]', sql_snippet) and table_name != "cars":
                        self._add_inferred_column(table_name, "user_id", "TEXT")
                    if re.search(r'\bcars?_id\s*[=,)]', sql_snippet) and table_name != "cars":
                        self._add_inferred_column(table_name, "car_id", "INTEGER")
                    if re.search(r'\btrip\s*[=,)]', sql_snippet) and table_name == "cars":
                        self._add_inferred_column(table_name, "trip", "TEXT")
                    if re.search(r'\bseats\s*[=,)]', sql_snippet):
                        self._add_inferred_column(table_name, "seats", "INTEGER")
                    if re.search(r'\bname\s*[=,)]', sql_snippet):
                        self._add_inferred_column(table_name, "name", "TEXT")
    
    def _add_inferred_column(self, table_name, column_name, data_type):
        """Add an inferred column if it doesn't already exist"""
        existing_columns = [col["name"] for col in self.expected_schema["tables"][table_name]["columns"]]
        if column_name not in existing_columns:
            self.expected_schema["tables"][table_name]["columns"].append({
                "name": column_name,
                "type": data_type,
                "inferred": True
            })

class DatabaseSyncChecker:
    """Main sync checker that compares expected vs actual database schema"""
    
    def __init__(self, project_root):
        self.project_root = project_root
        self.analyzer = CodebaseAnalyzer(project_root)
    
    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(os.getenv("DATABASE_URL"))
    
    def check_sync(self):
        """Perform comprehensive sync check"""
        print("🔄 Starting database sync check...")
        print(f"📅 Sync check run at: {datetime.now().isoformat()}")
        print("=" * 60)
        
        # Analyze codebase
        expected_schema = self.analyzer.analyze_codebase()
        
        # Get actual database schema
        actual_schema = self._get_actual_schema()
        
        # Compare and find mismatches
        mismatches = self._compare_schemas(expected_schema, actual_schema)
        
        # Generate report
        report = self._generate_report(expected_schema, actual_schema, mismatches)
        
        return report
    
    def _get_actual_schema(self):
        """Get actual database schema"""
        print("\n📋 Reading actual database schema...")
        
        with self.get_connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get all tables
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            tables = [row['table_name'] for row in cur.fetchall()]
            
            schema = {"tables": {}, "constraints": {}}
            
            for table_name in tables:
                # Get columns
                cur.execute("""
                    SELECT 
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns 
                    WHERE table_name = %s 
                    ORDER BY ordinal_position
                """, (table_name,))
                
                columns = [dict(col) for col in cur.fetchall()]
                schema["tables"][table_name] = {"columns": columns}
                
                # Get constraints
                cur.execute("""
                    SELECT 
                        constraint_name,
                        constraint_type
                    FROM information_schema.table_constraints 
                    WHERE table_name = %s
                """, (table_name,))
                
                constraints = [dict(const) for const in cur.fetchall()]
                schema["tables"][table_name]["constraints"] = constraints
        
        return schema
    
    def _compare_schemas(self, expected, actual):
        """Compare expected vs actual schemas and find mismatches"""
        print("\n🔍 Comparing expected vs actual schemas...")
        
        mismatches = {
            "missing_tables": [],
            "extra_tables": [],
            "missing_columns": [],
            "extra_columns": [],
            "type_mismatches": [],
            "missing_commands_support": [],
            "summary": {}
        }
        
        expected_tables = set(expected["tables"].keys())
        actual_tables = set(actual["tables"].keys())
        
        # Check for missing/extra tables
        mismatches["missing_tables"] = list(expected_tables - actual_tables)
        mismatches["extra_tables"] = list(actual_tables - expected_tables)
        
        # Check columns for common tables
        common_tables = expected_tables & actual_tables
        
        for table_name in common_tables:
            expected_cols = {col["name"]: col for col in expected["tables"][table_name]["columns"]}
            actual_cols = {col["column_name"]: col for col in actual["tables"][table_name]["columns"]}
            
            expected_col_names = set(expected_cols.keys())
            actual_col_names = set(actual_cols.keys())
            
            # Missing columns
            missing_cols = expected_col_names - actual_col_names
            for col_name in missing_cols:
                mismatches["missing_columns"].append({
                    "table": table_name,
                    "column": col_name,
                    "expected_type": expected_cols[col_name].get("type", "UNKNOWN")
                })
            
            # Extra columns
            extra_cols = actual_col_names - expected_col_names
            for col_name in extra_cols:
                mismatches["extra_columns"].append({
                    "table": table_name,
                    "column": col_name,
                    "actual_type": actual_cols[col_name]["data_type"]
                })
        
        # Check if commands have database support
        for command in expected["commands"]:
            command_name = command["name"]
            # Basic heuristic: check if command operations have corresponding tables
            if command_name in ["trip", "car", "member"] and command_name + "s" not in actual_tables:
                mismatches["missing_commands_support"].append({
                    "command": command_name,
                    "file": command["file"],
                    "missing_table": command_name + "s"
                })
        
        # Generate summary
        total_issues = (len(mismatches["missing_tables"]) + 
                       len(mismatches["extra_tables"]) + 
                       len(mismatches["missing_columns"]) + 
                       len(mismatches["extra_columns"]) + 
                       len(mismatches["missing_commands_support"]))
        
        mismatches["summary"] = {
            "total_issues": total_issues,
            "status": "SYNC" if total_issues == 0 else "MISMATCH",
            "tables_analyzed": len(common_tables),
            "commands_found": len(expected["commands"])
        }
        
        return mismatches
    
    def _generate_report(self, expected, actual, mismatches):
        """Generate comprehensive sync report"""
        print("\n📊 Generating sync report...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "expected_schema": expected,
            "actual_schema": actual,
            "mismatches": mismatches,
            "recommendations": []
        }
        
        # Print console report
        print("=" * 60)
        print("📊 DATABASE SYNC REPORT")
        print("=" * 60)
        
        status = mismatches["summary"]["status"]
        print(f"Status: {'✅ IN SYNC' if status == 'SYNC' else '⚠️  MISMATCH DETECTED'}")
        print(f"Tables analyzed: {mismatches['summary']['tables_analyzed']}")
        print(f"Commands found: {mismatches['summary']['commands_found']}")
        print(f"Issues found: {mismatches['summary']['total_issues']}")
        
        if mismatches["missing_tables"]:
            print(f"\n❌ Missing Tables ({len(mismatches['missing_tables'])}):")
            for table in mismatches["missing_tables"]:
                print(f"   - {table}")
                report["recommendations"].append(f"Create table: {table}")
        
        if mismatches["extra_tables"]:
            print(f"\n⚠️  Extra Tables ({len(mismatches['extra_tables'])}):")
            for table in mismatches["extra_tables"]:
                print(f"   - {table}")
                report["recommendations"].append(f"Review if table {table} is still needed")
        
        if mismatches["missing_columns"]:
            print(f"\n❌ Missing Columns ({len(mismatches['missing_columns'])}):")
            for col in mismatches["missing_columns"]:
                print(f"   - {col['table']}.{col['column']} ({col['expected_type']})")
                report["recommendations"].append(f"Add column {col['table']}.{col['column']}")
        
        if mismatches["extra_columns"]:
            print(f"\n⚠️  Extra Columns ({len(mismatches['extra_columns'])}):")
            for col in mismatches["extra_columns"]:
                print(f"   - {col['table']}.{col['column']} ({col['actual_type']})")
        
        if mismatches["missing_commands_support"]:
            print(f"\n❌ Commands Missing DB Support ({len(mismatches['missing_commands_support'])}):")
            for cmd in mismatches["missing_commands_support"]:
                print(f"   - {cmd['command']} (in {cmd['file']}) needs table: {cmd['missing_table']}")
                report["recommendations"].append(f"Create table {cmd['missing_table']} for command {cmd['command']}")
        
        if status == "SYNC":
            print("\n✅ Database and codebase are in sync!")
        else:
            print(f"\n⚠️  Found {mismatches['summary']['total_issues']} sync issues that need attention.")
        
        # Save detailed report
        with open('db_sync_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n💾 Detailed sync report saved to: db_sync_report.json")
        
        return report

def main():
    """Main function"""
    project_root = os.getcwd()
    checker = DatabaseSyncChecker(project_root)
    
    try:
        report = checker.check_sync()
        exit_code = 0 if report["mismatches"]["summary"]["status"] == "SYNC" else 1
        exit(exit_code)
    except Exception as e:
        print(f"❌ Sync check failed with error: {e}")
        exit(1)

if __name__ == "__main__":
    main()
