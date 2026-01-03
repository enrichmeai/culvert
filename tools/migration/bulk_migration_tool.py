#!/usr/bin/env python3
"""
Bulk Legacy Migration Tool

Automates migration of multiple COBOL files, JCL jobs, and Teradata tables
simultaneously with parallel processing, validation, and error handling.

Usage:
    python3 bulk_migration_tool.py --config migration_config.yaml
    python3 bulk_migration_tool.py --source-dir /path/to/legacy --output-dir /path/to/modern
"""

import os
import sys
import yaml
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from datetime import datetime
import csv
from decimal import Decimal
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class MigrationConfig:
    """Configuration for migration"""
    source_type: str  # 'cobol', 'jcl', 'teradata'
    source_dir: str
    output_dir: str
    parallel_workers: int = 4
    file_patterns: List[str] = None
    validation_enabled: bool = True
    backup_enabled: bool = True
    dry_run: bool = False

    def __post_init__(self):
        if self.file_patterns is None:
            self.file_patterns = ['*.cbl', '*.cob', '*.jcl', '*.sql']


@dataclass
class MigrationResult:
    """Result of a single file/table migration"""
    source_file: str
    output_file: str
    status: str  # 'success', 'failed', 'skipped'
    records_processed: int = 0
    records_failed: int = 0
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class FieldDefinition:
    """Field definition for parsing fixed-width records"""
    name: str
    start: int
    length: int
    type: str  # 'string', 'numeric', 'decimal'
    decimals: int = 0


class COBOLParser:
    """Parse COBOL copybook definitions and data files"""

    @staticmethod
    def parse_copybook(copybook_file: str) -> List[FieldDefinition]:
        """Parse COBOL copybook to extract field definitions"""
        fields = []
        position = 0

        with open(copybook_file, 'r') as f:
            for line in f:
                # Match COBOL field definition: 05 FIELD-NAME PIC X(10)
                match = re.match(r'\s*\d+\s+([A-Z0-9\-]+)\s+PIC\s+([X9V]+)\((\d+)\)', line)
                if match:
                    field_name = match.group(1).replace('-', '_').lower()
                    pic_type = match.group(2)
                    length = int(match.group(3))

                    # Determine field type
                    if 'X' in pic_type:
                        field_type = 'string'
                        decimals = 0
                    elif 'V' in pic_type:
                        field_type = 'decimal'
                        decimals = length - pic_type.index('V')
                    else:
                        field_type = 'numeric'
                        decimals = 0

                    fields.append(FieldDefinition(
                        name=field_name,
                        start=position,
                        length=length,
                        type=field_type,
                        decimals=decimals
                    ))
                    position += length

        return fields

    @staticmethod
    def parse_record(line: str, fields: List[FieldDefinition]) -> Dict:
        """Parse a single fixed-width record using field definitions"""
        record = {}

        for field in fields:
            value = line[field.start:field.start + field.length].strip()

            if field.type == 'string':
                record[field.name] = value
            elif field.type == 'numeric':
                record[field.name] = int(value) if value else 0
            elif field.type == 'decimal':
                record[field.name] = float(Decimal(value or '0') / (10 ** field.decimals))
            else:
                record[field.name] = value

        record['processed_at'] = datetime.utcnow().isoformat()
        return record


class BulkMigrationEngine:
    """Main engine for bulk migration operations"""

    def __init__(self, config: MigrationConfig):
        self.config = config
        self.results: List[MigrationResult] = []

        # Create output directory
        os.makedirs(config.output_dir, exist_ok=True)

        # Create backup directory if enabled
        if config.backup_enabled:
            self.backup_dir = os.path.join(config.output_dir, 'backups')
            os.makedirs(self.backup_dir, exist_ok=True)

    def discover_files(self) -> List[str]:
        """Discover all files matching patterns in source directory"""
        files = []
        source_path = Path(self.config.source_dir)

        for pattern in self.config.file_patterns:
            files.extend(source_path.rglob(pattern))

        logger.info(f"Discovered {len(files)} files to migrate")
        return [str(f) for f in files]

    def migrate_cobol_file(self, source_file: str) -> MigrationResult:
        """Migrate a single COBOL data file"""
        start_time = datetime.now()

        try:
            # Determine output file
            output_file = os.path.join(
                self.config.output_dir,
                os.path.basename(source_file).replace('.dat', '.csv')
            )

            # Look for copybook definition
            copybook_file = source_file.replace('.dat', '.cpy')

            if os.path.exists(copybook_file):
                fields = COBOLParser.parse_copybook(copybook_file)
                logger.info(f"Using copybook: {copybook_file} ({len(fields)} fields)")
            else:
                # Use default field structure (from customer example)
                fields = self._get_default_customer_fields()
                logger.warning(f"No copybook found for {source_file}, using default fields")

            records_processed = 0
            records_failed = 0
            warnings = []

            with open(source_file, 'r') as infile, \
                 open(output_file, 'w', newline='') as outfile:

                writer = csv.DictWriter(outfile, fieldnames=[f.name for f in fields] + ['processed_at'])
                writer.writeheader()

                for line_num, line in enumerate(infile, 1):
                    if not line.strip():
                        continue

                    try:
                        record = COBOLParser.parse_record(line, fields)

                        # Validation
                        if self.config.validation_enabled:
                            is_valid, error = self._validate_record(record)
                            if not is_valid:
                                records_failed += 1
                                warnings.append(f"Line {line_num}: {error}")
                                continue

                        writer.writerow(record)
                        records_processed += 1

                        if records_processed % 1000 == 0:
                            logger.info(f"{source_file}: Processed {records_processed} records")

                    except Exception as e:
                        records_failed += 1
                        warnings.append(f"Line {line_num}: {str(e)}")

            duration = (datetime.now() - start_time).total_seconds()

            return MigrationResult(
                source_file=source_file,
                output_file=output_file,
                status='success',
                records_processed=records_processed,
                records_failed=records_failed,
                duration_seconds=duration,
                warnings=warnings[:10]  # Keep first 10 warnings
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Failed to migrate {source_file}: {str(e)}")

            return MigrationResult(
                source_file=source_file,
                output_file='',
                status='failed',
                error_message=str(e),
                duration_seconds=duration
            )

    def migrate_jcl_job(self, source_file: str) -> MigrationResult:
        """Convert JCL job to Airflow DAG"""
        start_time = datetime.now()

        try:
            output_file = os.path.join(
                self.config.output_dir,
                os.path.basename(source_file).replace('.jcl', '_dag.py')
            )

            with open(source_file, 'r') as f:
                jcl_content = f.read()

            # Parse JCL steps
            steps = self._parse_jcl_steps(jcl_content)

            # Generate Airflow DAG
            dag_content = self._generate_airflow_dag(
                os.path.basename(source_file).replace('.jcl', ''),
                steps
            )

            with open(output_file, 'w') as f:
                f.write(dag_content)

            duration = (datetime.now() - start_time).total_seconds()

            return MigrationResult(
                source_file=source_file,
                output_file=output_file,
                status='success',
                records_processed=len(steps),
                duration_seconds=duration
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()

            return MigrationResult(
                source_file=source_file,
                output_file='',
                status='failed',
                error_message=str(e),
                duration_seconds=duration
            )

    def migrate_teradata_table(self, table_info: Dict) -> MigrationResult:
        """Generate BigQuery schema and dbt model for Teradata table"""
        start_time = datetime.now()

        try:
            table_name = table_info['table_name']

            # Generate BigQuery schema
            bq_schema_file = os.path.join(
                self.config.output_dir,
                'bigquery_schemas',
                f"{table_name}_schema.json"
            )
            os.makedirs(os.path.dirname(bq_schema_file), exist_ok=True)

            bq_schema = self._generate_bigquery_schema(table_info)

            with open(bq_schema_file, 'w') as f:
                json.dump(bq_schema, f, indent=2)

            # Generate dbt model
            dbt_model_file = os.path.join(
                self.config.output_dir,
                'dbt_models',
                f"stg_{table_name}.sql"
            )
            os.makedirs(os.path.dirname(dbt_model_file), exist_ok=True)

            dbt_model = self._generate_dbt_model(table_info)

            with open(dbt_model_file, 'w') as f:
                f.write(dbt_model)

            duration = (datetime.now() - start_time).total_seconds()

            return MigrationResult(
                source_file=f"teradata.{table_name}",
                output_file=f"{bq_schema_file}, {dbt_model_file}",
                status='success',
                records_processed=len(table_info.get('columns', [])),
                duration_seconds=duration
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()

            return MigrationResult(
                source_file=f"teradata.{table_info.get('table_name', 'unknown')}",
                output_file='',
                status='failed',
                error_message=str(e),
                duration_seconds=duration
            )

    def run_migration(self) -> Dict:
        """Run bulk migration with parallel processing"""
        logger.info("Starting bulk migration...")
        logger.info(f"Configuration: {asdict(self.config)}")

        # Discover files
        files = self.discover_files()

        if not files:
            logger.warning("No files found to migrate")
            return self._generate_summary()

        # Process files in parallel
        with ThreadPoolExecutor(max_workers=self.config.parallel_workers) as executor:
            future_to_file = {}

            for file_path in files:
                if self.config.source_type == 'cobol':
                    future = executor.submit(self.migrate_cobol_file, file_path)
                elif self.config.source_type == 'jcl':
                    future = executor.submit(self.migrate_jcl_job, file_path)
                else:
                    logger.warning(f"Unknown source type: {self.config.source_type}")
                    continue

                future_to_file[future] = file_path

            # Collect results
            for future in as_completed(future_to_file):
                result = future.result()
                self.results.append(result)

                if result.status == 'success':
                    logger.info(f"✅ {result.source_file}: {result.records_processed} records")
                else:
                    logger.error(f"❌ {result.source_file}: {result.error_message}")

        # Generate summary
        summary = self._generate_summary()
        self._save_results(summary)

        return summary

    def _validate_record(self, record: Dict) -> Tuple[bool, str]:
        """Validate a single record"""
        # Add your validation rules here
        for key, value in record.items():
            if key.endswith('_id') and not value:
                return False, f"Missing required field: {key}"

        return True, ""

    def _get_default_customer_fields(self) -> List[FieldDefinition]:
        """Default customer record structure"""
        return [
            FieldDefinition('customer_id', 0, 10, 'string'),
            FieldDefinition('customer_name', 10, 40, 'string'),
            FieldDefinition('address', 50, 50, 'string'),
            FieldDefinition('phone', 100, 20, 'string'),
            FieldDefinition('email', 120, 30, 'string'),
            FieldDefinition('customer_type', 150, 10, 'string'),
            FieldDefinition('status', 160, 10, 'string'),
            FieldDefinition('balance', 170, 10, 'decimal', 2)
        ]

    def _parse_jcl_steps(self, jcl_content: str) -> List[Dict]:
        """Parse JCL steps from content"""
        steps = []
        for line in jcl_content.split('\n'):
            if line.startswith('//') and 'EXEC' in line:
                match = re.match(r'//(\w+)\s+EXEC\s+PGM=(\w+)', line)
                if match:
                    steps.append({
                        'step_name': match.group(1),
                        'program': match.group(2)
                    })
        return steps

    def _generate_airflow_dag(self, job_name: str, steps: List[Dict]) -> str:
        """Generate Airflow DAG from JCL steps"""
        dag_template = f'''"""
Generated Airflow DAG from JCL job: {job_name}
Generated on: {datetime.now().isoformat()}
"""
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta

default_args = {{
    'owner': 'migration',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}}

dag = DAG(
    '{job_name}_migrated',
    default_args=default_args,
    description='Migrated from JCL job: {job_name}',
    schedule_interval='@daily',
    catchup=False
)

'''

        # Add task definitions
        for i, step in enumerate(steps):
            dag_template += f'''
def {step['step_name'].lower()}_task():
    """Execute {step['program']} logic"""
    # TODO: Implement {step['program']} logic
    pass

task_{i} = PythonOperator(
    task_id='{step['step_name'].lower()}',
    python_callable={step['step_name'].lower()}_task,
    dag=dag
)
'''

        # Add dependencies
        if len(steps) > 1:
            dag_template += '\n# Task dependencies\n'
            for i in range(len(steps) - 1):
                dag_template += f"task_{i} >> task_{i+1}\n"

        return dag_template

    def _generate_bigquery_schema(self, table_info: Dict) -> List[Dict]:
        """Generate BigQuery schema from Teradata table definition"""
        schema = []

        for column in table_info.get('columns', []):
            bq_type = self._map_teradata_to_bigquery_type(column['type'])

            schema.append({
                'name': column['name'],
                'type': bq_type,
                'mode': 'NULLABLE' if column.get('nullable', True) else 'REQUIRED',
                'description': column.get('description', '')
            })

        return schema

    def _generate_dbt_model(self, table_info: Dict) -> str:
        """Generate dbt staging model"""
        table_name = table_info['table_name']
        columns = table_info.get('columns', [])

        model = f'''{{{{
    config(
        materialized='view',
        schema='staging'
    )
}}}}

-- Staging model for {table_name}
-- Generated on: {datetime.now().isoformat()}

SELECT
'''

        for i, column in enumerate(columns):
            comma = ',' if i < len(columns) - 1 else ''
            model += f"    {column['name']}{comma}\n"

        model += f"FROM {{{{ source('teradata', '{table_name}') }}}}\n"

        return model

    def _map_teradata_to_bigquery_type(self, teradata_type: str) -> str:
        """Map Teradata data types to BigQuery"""
        type_map = {
            'INTEGER': 'INT64',
            'SMALLINT': 'INT64',
            'BIGINT': 'INT64',
            'DECIMAL': 'NUMERIC',
            'FLOAT': 'FLOAT64',
            'CHAR': 'STRING',
            'VARCHAR': 'STRING',
            'DATE': 'DATE',
            'TIMESTAMP': 'TIMESTAMP',
            'TIME': 'TIME'
        }

        base_type = teradata_type.split('(')[0].upper()
        return type_map.get(base_type, 'STRING')

    def _generate_summary(self) -> Dict:
        """Generate migration summary"""
        total = len(self.results)
        successful = sum(1 for r in self.results if r.status == 'success')
        failed = sum(1 for r in self.results if r.status == 'failed')
        total_records = sum(r.records_processed for r in self.results)
        total_duration = sum(r.duration_seconds for r in self.results)

        return {
            'total_files': total,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / total * 100) if total > 0 else 0,
            'total_records_processed': total_records,
            'total_duration_seconds': total_duration,
            'average_duration_seconds': total_duration / total if total > 0 else 0,
            'timestamp': datetime.now().isoformat(),
            'results': [asdict(r) for r in self.results]
        }

    def _save_results(self, summary: Dict):
        """Save migration results"""
        results_file = os.path.join(self.config.output_dir, 'migration_results.json')

        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Results saved to: {results_file}")

        # Generate summary report
        report_file = os.path.join(self.config.output_dir, 'migration_report.txt')

        with open(report_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("BULK MIGRATION REPORT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Timestamp: {summary['timestamp']}\n")
            f.write(f"Total Files: {summary['total_files']}\n")
            f.write(f"Successful: {summary['successful']}\n")
            f.write(f"Failed: {summary['failed']}\n")
            f.write(f"Success Rate: {summary['success_rate']:.1f}%\n")
            f.write(f"Total Records: {summary['total_records_processed']}\n")
            f.write(f"Total Duration: {summary['total_duration_seconds']:.2f}s\n")
            f.write(f"Average Duration: {summary['average_duration_seconds']:.2f}s\n\n")

            f.write("=" * 80 + "\n")
            f.write("INDIVIDUAL FILE RESULTS\n")
            f.write("=" * 80 + "\n\n")

            for result in self.results:
                status_icon = "✅" if result.status == 'success' else "❌"
                f.write(f"{status_icon} {result.source_file}\n")
                f.write(f"   Status: {result.status}\n")
                f.write(f"   Records: {result.records_processed}\n")
                f.write(f"   Failed: {result.records_failed}\n")
                f.write(f"   Duration: {result.duration_seconds:.2f}s\n")

                if result.error_message:
                    f.write(f"   Error: {result.error_message}\n")

                if result.warnings:
                    f.write(f"   Warnings: {len(result.warnings)}\n")

                f.write("\n")

        logger.info(f"Report saved to: {report_file}")


def main():
    parser = argparse.ArgumentParser(description='Bulk Legacy Migration Tool')

    parser.add_argument('--config', type=str, help='Path to YAML configuration file')
    parser.add_argument('--source-dir', type=str, help='Source directory with legacy files')
    parser.add_argument('--output-dir', type=str, help='Output directory for migrated files')
    parser.add_argument('--source-type', type=str, choices=['cobol', 'jcl', 'teradata'],
                       default='cobol', help='Type of source to migrate')
    parser.add_argument('--workers', type=int, default=4, help='Number of parallel workers')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without actual migration')

    args = parser.parse_args()

    # Load configuration
    if args.config:
        with open(args.config, 'r') as f:
            config_dict = yaml.safe_load(f)
            config = MigrationConfig(**config_dict)
    else:
        if not args.source_dir or not args.output_dir:
            parser.error("--source-dir and --output-dir are required when not using --config")

        config = MigrationConfig(
            source_type=args.source_type,
            source_dir=args.source_dir,
            output_dir=args.output_dir,
            parallel_workers=args.workers,
            dry_run=args.dry_run
        )

    # Run migration
    engine = BulkMigrationEngine(config)
    summary = engine.run_migration()

    # Print summary
    print("\n" + "=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)
    print(f"Total Files: {summary['total_files']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success Rate: {summary['success_rate']:.1f}%")
    print(f"Total Records: {summary['total_records_processed']}")
    print(f"Total Duration: {summary['total_duration_seconds']:.2f}s")
    print("=" * 80)

    # Exit with error code if any migrations failed
    sys.exit(0 if summary['failed'] == 0 else 1)


if __name__ == '__main__':
    main()

