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
        """Find SQL operations using regex patterns"""
        # Common SQL patterns
        sql_patterns = [
            r'(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|SELECT.*FROM)\s+(\w+)',
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)',
            r'ALTER\s+TABLE\s+(\w+)',
            r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(\w+)'
        ]
        
        for pattern in sql_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                table_name = match.group(1)
                operation_type = match.group(0).split()[0].upper()
                
                self.expected_schema["database_operations"].append({
                    "file": str(file_path.relative_to(self.project_root)),
                    "table": table_name,
                    "operation": operation_type,
                    "sql_snippet": match.group(0)[:100]
                })
    
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
        """Find Discord bot commands"""
        # Look for @bot.command or @commands.command decorators
        command_patterns = [
            r'@(?:bot\.)?command\(["\']?(\w+)["\']?\)',
            r'@(?:bot\.)?command\(\s*name\s*=\s*["\'](\w+)["\']',
            r'async\s+def\s+(\w+)\s*\([^)]*ctx[^)]*\):',  # Discord command functions
        ]
        
        for pattern in command_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                command_name = match.group(1)
                if command_name not in ['__init__', 'setup', 'teardown']:  # Skip common non-command functions
                    self.expected_schema["commands"].append({
                        "name": command_name,
                        "file": str(file_path.relative_to(self.project_root))
                    })
    
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
            
            # Look for column references in operations
            for op in operations:
                if "channel_id" in op["sql_snippet"].lower():
                    self._add_inferred_column(table_name, "channel_id", "TEXT")
                if "user_id" in op["sql_snippet"].lower():
                    self._add_inferred_column(table_name, "user_id", "TEXT")
                if "car_id" in op["sql_snippet"].lower():
                    self._add_inferred_column(table_name, "car_id", "INTEGER")
                if "trip" in op["sql_snippet"].lower() and table_name == "cars":
                    self._add_inferred_column(table_name, "trip", "TEXT")
                if "seats" in op["sql_snippet"].lower():
                    self._add_inferred_column(table_name, "seats", "INTEGER")
                if "name" in op["sql_snippet"].lower():
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
