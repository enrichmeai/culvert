"""
LOA (Application B Application) Deployment.
Single entity pipeline: Applications -> ODP -> 2 FDP tables (SPLIT).
Key Characteristics:
- System ID: LOA
- Source Entities: 1 (Applications)
- ODP Tables: 1 (odp_loa.applications)
- FDP Tables: 2 (event_transaction_excess, portfolio_account_excess)
- Transformation: SPLIT 1 source -> 2 targets
- Dependency: No wait - immediate trigger after ODP load
"""
__version__ = "1.0.0"
