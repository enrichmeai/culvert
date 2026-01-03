#!/usr/bin/env python3
"""
BigQuery Direct Bulk Migration Tool

Migrates 100s-1000s of tables directly from Teradata/Oracle to BigQuery
using Google Cloud's Data Transfer Service and Datastream.

NO intermediate files needed - direct database-to-database migration!

Usage:
    # Migrate all Teradata tables
    python3 bigquery_bulk_migrator.py --source teradata --config teradata_config.yaml

    # Migrate specific tables
    python3 bigquery_bulk_migrator.py --source teradata --tables CUSTOMER ORDERS PRODUCTS

    # Dry run to see what would be migrated
    python3 bigquery_bulk_migrator.py --source teradata --dry-run
"""

import os
import sys
import yaml
import json
import argparse
import logging
import time
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from google.cloud import bigquery
from google.cloud import bigquery_datatransfer_v1
from google.cloud import storage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bigquery_migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class SourceConfig:
    """Source database configuration"""
    source_type: str  # 'teradata', 'oracle', 'mysql', 'postgresql'
    host: str
    database: str
    user: str
    password: str
    port: Optional[int] = None


@dataclass
class BigQueryConfig:
    """BigQuery destination configuration"""
    project_id: str
    dataset_id: str
    location: str = "US"
    create_dataset: bool = True


@dataclass
class MigrationConfig:
    """Complete migration configuration"""
    source: SourceConfig
    bigquery: BigQueryConfig
    tables: List[str] = None  # None = migrate all tables
    exclude_tables: List[str] = None
    parallel_transfers: int = 50
    dry_run: bool = False
    incremental_mode: bool = False
    schedule: Optional[str] = None  # e.g., "every day 00:00"


class TableDiscovery:
    """Discover tables from source databases"""

    @staticmethod
    def discover_teradata_tables(config: SourceConfig) -> List[Dict]:
        """Query Teradata to get all tables and metadata"""
        try:
            import teradatasql
        except ImportError:
            logger.error("teradatasql package not installed. Run: pip install teradatasql")
            return []

        logger.info(f"Connecting to Teradata: {config.host}")

        conn = teradatasql.connect(
            host=config.host,
            user=config.user,
            password=config.password,
            database=config.database
        )

        cursor = conn.cursor()

        # Get all tables with metadata
        query = """
            SELECT 
                t.DatabaseName,
                t.TableName,
                t.CreateTimeStamp,
                t.LastAlterTimeStamp,
                SUM(s.CurrentPerm) / 1024 / 1024 / 1024 as Size_GB,
                COUNT(c.ColumnName) as Column_Count
            FROM DBC.TablesV t
            LEFT JOIN DBC.TableSizeV s 
                ON t.DatabaseName = s.DatabaseName 
                AND t.TableName = s.TableName
            LEFT JOIN DBC.ColumnsV c 
                ON t.DatabaseName = c.DatabaseName 
                AND t.TableName = c.TableName
            WHERE t.DatabaseName = ?
            AND t.TableKind = 'T'
            GROUP BY 
                t.DatabaseName,
                t.TableName,
                t.CreateTimeStamp,
                t.LastAlterTimeStamp
            ORDER BY Size_GB DESC
        """

        cursor.execute(query, [config.database])

        tables = []
        for row in cursor:
            tables.append({
                'database': row[0],
                'table': row[1],
                'created': str(row[2]) if row[2] else None,
                'modified': str(row[3]) if row[3] else None,
                'size_gb': float(row[4]) if row[4] else 0.0,
                'column_count': int(row[5]) if row[5] else 0
            })

        conn.close()

        logger.info(f"Discovered {len(tables)} tables in {config.database}")
        logger.info(f"Total size: {sum(t['size_gb'] for t in tables):.2f} GB")

        return tables

    @staticmethod
    def discover_oracle_tables(config: SourceConfig) -> List[Dict]:
        """Query Oracle to get all tables"""
        try:
            import oracledb
        except ImportError:
            logger.error("oracledb package not installed. Run: pip install oracledb")
            return []

        conn = oracledb.connect(
            user=config.user,
            password=config.password,
            dsn=f"{config.host}:{config.port or 1521}/{config.database}"
        )

        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                owner,
                table_name,
                num_rows,
                blocks * 8192 / 1024 / 1024 / 1024 as size_gb
            FROM all_tables
            WHERE owner = :owner
            ORDER BY num_rows DESC
        """, owner=config.user.upper())

        tables = []
        for row in cursor:
            tables.append({
                'schema': row[0],
                'table': row[1],
                'rows': row[2] or 0,
                'size_gb': float(row[3]) if row[3] else 0.0
            })

        conn.close()
        return tables


class BigQueryBulkMigrator:
    """Main migration engine using BigQuery Data Transfer Service"""

    def __init__(self, config: MigrationConfig):
        self.config = config
        self.bq_client = bigquery.Client(project=config.bigquery.project_id)
        self.transfer_client = bigquery_datatransfer_v1.DataTransferServiceClient()
        self.results = []

        # Setup BigQuery dataset
        if config.bigquery.create_dataset:
            self._create_dataset()

    def _create_dataset(self):
        """Create BigQuery dataset if it doesn't exist"""
        dataset_id = f"{self.config.bigquery.project_id}.{self.config.bigquery.dataset_id}"
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = self.config.bigquery.location

        try:
            self.bq_client.create_dataset(dataset, exists_ok=True)
            logger.info(f"✅ Dataset ready: {dataset_id}")
        except Exception as e:
            logger.error(f"Failed to create dataset: {e}")
            raise

    def discover_tables(self) -> List[Dict]:
        """Discover all tables from source"""
        if self.config.source.source_type == 'teradata':
            tables = TableDiscovery.discover_teradata_tables(self.config.source)
        elif self.config.source.source_type == 'oracle':
            tables = TableDiscovery.discover_oracle_tables(self.config.source)
        else:
            logger.error(f"Unsupported source type: {self.config.source.source_type}")
            return []

        # Filter tables
        if self.config.tables:
            tables = [t for t in tables if t['table'] in self.config.tables]

        if self.config.exclude_tables:
            tables = [t for t in tables if t['table'] not in self.config.exclude_tables]

        return tables

    def create_transfer_config(self, table_info: Dict) -> Dict:
        """Create BigQuery Data Transfer Service config for a table"""
        table_name = table_info['table']

        # Map source type to data source ID
        data_source_map = {
            'teradata': 'teradata',
            'oracle': 'oracle',
            'mysql': 'mysql',
            'postgresql': 'postgresql'
        }

        data_source_id = data_source_map.get(self.config.source.source_type)
        if not data_source_id:
            raise ValueError(f"Unsupported source: {self.config.source.source_type}")

        # Create transfer config
        parent = self.transfer_client.common_project_path(self.config.bigquery.project_id)

        params = {
            "hostname": self.config.source.host,
            "database": self.config.source.database,
            "table": table_name,
            "write_disposition": "WRITE_TRUNCATE"  # or WRITE_APPEND for incremental
        }

        if self.config.source.port:
            params["port"] = str(self.config.source.port)

        transfer_config = bigquery_datatransfer_v1.TransferConfig(
            destination_dataset_id=self.config.bigquery.dataset_id,
            display_name=f"Migrate_{table_name}",
            data_source_id=data_source_id,
            params=params,
            schedule=self.config.schedule or "",
            disabled=False
        )

        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would create transfer for: {table_name}")
            return {
                'table': table_name,
                'status': 'dry_run',
                'config_name': None
            }

        try:
            response = self.transfer_client.create_transfer_config(
                parent=parent,
                transfer_config=transfer_config
            )

            logger.info(f"✅ Transfer config created: {table_name}")

            return {
                'table': table_name,
                'status': 'configured',
                'config_name': response.name,
                'size_gb': table_info.get('size_gb', 0)
            }

        except Exception as e:
            logger.error(f"❌ Failed to create config for {table_name}: {e}")
            return {
                'table': table_name,
                'status': 'failed',
                'error': str(e)
            }

    def start_transfer(self, config_name: str, table_name: str) -> Dict:
        """Start immediate transfer run"""
        if self.config.dry_run:
            return {'table': table_name, 'status': 'dry_run'}

        try:
            # Start manual transfer run
            response = self.transfer_client.start_manual_transfer_runs(
                parent=config_name,
                requested_run_time={"seconds": int(time.time())}
            )

            logger.info(f"🚀 Transfer started: {table_name}")

            return {
                'table': table_name,
                'status': 'running',
                'run_name': response.runs[0].name if response.runs else None
            }

        except Exception as e:
            logger.error(f"❌ Failed to start transfer for {table_name}: {e}")
            return {
                'table': table_name,
                'status': 'failed',
                'error': str(e)
            }

    def migrate_all_tables(self) -> Dict:
        """Migrate all discovered tables in parallel"""
        logger.info("=" * 80)
        logger.info("BIGQUERY BULK MIGRATION")
        logger.info("=" * 80)
        logger.info(f"Source: {self.config.source.source_type} ({self.config.source.host})")
        logger.info(f"Destination: BigQuery ({self.config.bigquery.project_id}.{self.config.bigquery.dataset_id})")
        logger.info(f"Parallel transfers: {self.config.parallel_transfers}")
        logger.info("=" * 80)

        # Discover tables
        tables = self.discover_tables()

        if not tables:
            logger.warning("No tables found to migrate")
            return {'total_tables': 0}

        logger.info(f"\n📋 Found {len(tables)} tables to migrate")
        total_size = sum(t.get('size_gb', 0) for t in tables)
        logger.info(f"📊 Total data size: {total_size:.2f} GB")

        if self.config.dry_run:
            logger.info("\n[DRY RUN MODE] - No actual migration will occur")

        # Print table list
        logger.info("\n📋 Tables to migrate:")
        for i, table in enumerate(tables[:20], 1):  # Show first 20
            size = table.get('size_gb', 0)
            logger.info(f"  {i}. {table['table']} ({size:.2f} GB)")

        if len(tables) > 20:
            logger.info(f"  ... and {len(tables) - 20} more tables")

        input("\n⏸️  Press Enter to continue with migration (or Ctrl+C to cancel)...")

        logger.info("\n🚀 Starting migration...\n")

        # Phase 1: Create transfer configs in parallel
        logger.info("Phase 1: Creating transfer configurations...")
        configs = []

        with ThreadPoolExecutor(max_workers=self.config.parallel_transfers) as executor:
            future_to_table = {
                executor.submit(self.create_transfer_config, table): table
                for table in tables
            }

            for future in as_completed(future_to_table):
                result = future.result()
                configs.append(result)

        successful_configs = [c for c in configs if c['status'] == 'configured']
        logger.info(f"\n✅ Created {len(successful_configs)} transfer configurations")

        # Phase 2: Start transfers in parallel
        if not self.config.dry_run:
            logger.info("\nPhase 2: Starting data transfers...")

            with ThreadPoolExecutor(max_workers=self.config.parallel_transfers) as executor:
                future_to_config = {
                    executor.submit(self.start_transfer, config['config_name'], config['table']): config
                    for config in successful_configs
                }

                for future in as_completed(future_to_config):
                    result = future.result()
                    self.results.append(result)

            logger.info(f"\n✅ Started {len(self.results)} transfers")

        # Generate summary
        summary = self._generate_summary(tables, configs)
        self._save_results(summary)

        return summary

    def monitor_transfers(self, config_names: List[str]):
        """Monitor progress of transfers"""
        logger.info("\n📊 Monitoring transfer progress...")

        while True:
            all_complete = True

            for config_name in config_names:
                runs = self.transfer_client.list_transfer_runs(parent=config_name)

                for run in runs:
                    if run.state in [
                        bigquery_datatransfer_v1.TransferState.PENDING,
                        bigquery_datatransfer_v1.TransferState.RUNNING
                    ]:
                        all_complete = False
                        logger.info(f"⏳ {run.name}: {run.state.name}")
                    elif run.state == bigquery_datatransfer_v1.TransferState.SUCCEEDED:
                        logger.info(f"✅ {run.name}: SUCCEEDED")
                    elif run.state == bigquery_datatransfer_v1.TransferState.FAILED:
                        logger.error(f"❌ {run.name}: FAILED - {run.error_status.message}")

            if all_complete:
                break

            time.sleep(30)  # Check every 30 seconds

        logger.info("\n✅ All transfers complete!")

    def _generate_summary(self, tables: List[Dict], configs: List[Dict]) -> Dict:
        """Generate migration summary"""
        total_tables = len(tables)
        configured = len([c for c in configs if c['status'] == 'configured'])
        failed = len([c for c in configs if c['status'] == 'failed'])
        total_size = sum(t.get('size_gb', 0) for t in tables)

        return {
            'timestamp': datetime.now().isoformat(),
            'source': self.config.source.source_type,
            'destination': f"{self.config.bigquery.project_id}.{self.config.bigquery.dataset_id}",
            'total_tables': total_tables,
            'configured': configured,
            'failed': failed,
            'success_rate': (configured / total_tables * 100) if total_tables > 0 else 0,
            'total_size_gb': total_size,
            'dry_run': self.config.dry_run,
            'tables': tables,
            'configs': configs
        }

    def _save_results(self, summary: Dict):
        """Save migration results"""
        output_file = f"migration_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"\n📄 Results saved to: {output_file}")

        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Tables: {summary['total_tables']}")
        logger.info(f"Configured: {summary['configured']}")
        logger.info(f"Failed: {summary['failed']}")
        logger.info(f"Success Rate: {summary['success_rate']:.1f}%")
        logger.info(f"Total Size: {summary['total_size_gb']:.2f} GB")
        logger.info("=" * 80)


def load_config(config_file: str) -> MigrationConfig:
    """Load configuration from YAML file"""
    with open(config_file, 'r') as f:
        config_dict = yaml.safe_load(f)

    # Replace environment variables
    for key in ['user', 'password']:
        if key in config_dict.get('source', {}):
            value = config_dict['source'][key]
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                config_dict['source'][key] = os.environ.get(env_var, '')

    source = SourceConfig(**config_dict['source'])
    bigquery = BigQueryConfig(**config_dict['bigquery'])

    return MigrationConfig(
        source=source,
        bigquery=bigquery,
        tables=config_dict.get('tables'),
        exclude_tables=config_dict.get('exclude_tables'),
        parallel_transfers=config_dict.get('parallel_transfers', 50),
        dry_run=config_dict.get('dry_run', False),
        incremental_mode=config_dict.get('incremental_mode', False),
        schedule=config_dict.get('schedule')
    )


def main():
    parser = argparse.ArgumentParser(
        description='BigQuery Bulk Migration Tool - Direct database-to-database migration'
    )

    parser.add_argument('--config', required=True, help='Path to configuration YAML file')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    parser.add_argument('--monitor', action='store_true', help='Monitor existing transfers')

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    if args.dry_run:
        config.dry_run = True

    # Run migration
    migrator = BigQueryBulkMigrator(config)
    summary = migrator.migrate_all_tables()

    # Exit with appropriate code
    sys.exit(0 if summary['failed'] == 0 else 1)


if __name__ == '__main__':
    main()

